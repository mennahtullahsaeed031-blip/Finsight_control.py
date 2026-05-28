"""
FP&A Budget Builder Engine
بيبني كل الميزانيات من Assumptions بسيطة
"""

# ══════════════════════════════════════════
# DEFAULT ASSUMPTIONS
# ══════════════════════════════════════════
DEFAULT_ASSUMPTIONS = {
    # Revenue
    "base_revenue":        1_000_000,
    "revenue_growth":      0.10,       # 10% YoY
    "seasonality": [
        0.07, 0.07, 0.08, 0.08, 0.09, 0.09,
        0.09, 0.09, 0.08, 0.09, 0.09, 0.08
    ],  # توزيع المبيعات على 12 شهر (مجموعها 1.0)

    # Costs
    "cogs_pct":            0.38,       # 38% of revenue
    "inflation_rate":      0.07,       # 7% inflation

    # Operating Expenses
    "base_headcount":      50,
    "avg_salary_monthly":  15_000,
    "salary_growth":       0.05,
    "marketing_pct":       0.08,       # 8% of revenue
    "rd_pct":              0.06,
    "ga_pct":              0.04,
    "rent_monthly":        20_000,
    "depreciation_monthly":10_000,

    # Production
    "units_sold":          10_000,
    "price_per_unit":      100,
    "material_per_unit":   30,
    "labor_hours_per_unit":2,
    "labor_rate_per_hour": 25,
    "overhead_per_unit":   10,

    # CapEx
    "capex_annual":        500_000,

    # Finance
    "loan_balance":        2_000_000,
    "interest_rate":       0.12,       # 12% سنوي
    "tax_rate":            0.22,

    # Working Capital
    "receivables_days":    45,
    "payables_days":       30,
    "inventory_days":      60,

    # Cash
    "opening_cash":        500_000,
}

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]


# ══════════════════════════════════════════
# REVENUE BUDGET
# ══════════════════════════════════════════
def build_revenue_budget(a: dict) -> dict:
    base    = a["base_revenue"] * (1 + a["revenue_growth"])
    monthly = []
    for i, season in enumerate(a["seasonality"]):
        rev = base * season
        monthly.append({
            "month":   MONTHS[i],
            "revenue": round(rev, 0),
            "units":   round(rev / a["price_per_unit"], 0) if a["price_per_unit"] else 0,
        })
    total = sum(m["revenue"] for m in monthly)
    return {
        "type":    "Revenue Budget",
        "monthly": monthly,
        "annual":  round(total, 0),
        "growth":  a["revenue_growth"],
    }


# ══════════════════════════════════════════
# PRODUCTION BUDGET
# ══════════════════════════════════════════
def build_production_budget(a: dict, revenue_budget: dict) -> dict:
    monthly = []
    for m in revenue_budget["monthly"]:
        units_sold     = m["units"]
        ending_inv     = units_sold * (a["inventory_days"] / 30)
        beginning_inv  = ending_inv * 0.8  # تقدير
        units_to_prod  = units_sold + ending_inv - beginning_inv
        monthly.append({
            "month":          m["month"],
            "units_sold":     round(units_sold, 0),
            "ending_inv":     round(ending_inv, 0),
            "beginning_inv":  round(beginning_inv, 0),
            "units_to_produce": round(units_to_prod, 0),
        })
    total_units = sum(m["units_to_produce"] for m in monthly)
    return {
        "type":        "Production Budget",
        "monthly":     monthly,
        "total_units": round(total_units, 0),
    }


# ══════════════════════════════════════════
# DIRECT MATERIALS BUDGET
# ══════════════════════════════════════════
def build_materials_budget(a: dict, production_budget: dict) -> dict:
    mat_cost = a["material_per_unit"] * (1 + a["inflation_rate"])
    monthly  = []
    for m in production_budget["monthly"]:
        qty_needed = m["units_to_produce"] * a["material_per_unit"]
        cost       = m["units_to_produce"] * mat_cost
        monthly.append({
            "month":         m["month"],
            "units_to_prod": m["units_to_produce"],
            "qty_needed":    round(qty_needed, 0),
            "cost_per_unit": round(mat_cost, 2),
            "total_cost":    round(cost, 0),
        })
    total = sum(m["total_cost"] for m in monthly)
    return {
        "type":       "Direct Materials Budget",
        "monthly":    monthly,
        "annual":     round(total, 0),
        "unit_cost":  round(mat_cost, 2),
    }


# ══════════════════════════════════════════
# DIRECT LABOR BUDGET
# ══════════════════════════════════════════
def build_labor_budget(a: dict, production_budget: dict) -> dict:
    rate    = a["labor_rate_per_hour"] * (1 + a["salary_growth"])
    monthly = []
    for m in production_budget["monthly"]:
        hours = m["units_to_produce"] * a["labor_hours_per_unit"]
        cost  = hours * rate
        monthly.append({
            "month":        m["month"],
            "hours_needed": round(hours, 0),
            "rate_per_hour":round(rate, 2),
            "total_cost":   round(cost, 0),
        })
    total = sum(m["total_cost"] for m in monthly)
    return {
        "type":    "Direct Labor Budget",
        "monthly": monthly,
        "annual":  round(total, 0),
    }


# ══════════════════════════════════════════
# OVERHEAD BUDGET
# ══════════════════════════════════════════
def build_overhead_budget(a: dict, production_budget: dict) -> dict:
    monthly = []
    for m in production_budget["monthly"]:
        variable = m["units_to_produce"] * a["overhead_per_unit"]
        fixed    = a["rent_monthly"] + a["depreciation_monthly"]
        total    = variable + fixed
        monthly.append({
            "month":    m["month"],
            "variable": round(variable, 0),
            "fixed":    round(fixed, 0),
            "total":    round(total, 0),
        })
    annual = sum(m["total"] for m in monthly)
    return {
        "type":    "Production Overhead Budget",
        "monthly": monthly,
        "annual":  round(annual, 0),
    }


# ══════════════════════════════════════════
# COGS BUDGET
# ══════════════════════════════════════════
def build_cogs_budget(
    materials_budget: dict,
    labor_budget: dict,
    overhead_budget: dict,
) -> dict:
    monthly = []
    for i in range(12):
        mat  = materials_budget["monthly"][i]["total_cost"]
        lab  = labor_budget["monthly"][i]["total_cost"]
        ovh  = overhead_budget["monthly"][i]["total"]
        total = mat + lab + ovh
        monthly.append({
            "month":     MONTHS[i],
            "materials": mat,
            "labor":     lab,
            "overhead":  ovh,
            "total":     round(total, 0),
        })
    annual = sum(m["total"] for m in monthly)
    return {
        "type":    "COGS Budget",
        "monthly": monthly,
        "annual":  round(annual, 0),
    }


# ══════════════════════════════════════════
# SG&A BUDGET
# ══════════════════════════════════════════
def build_sga_budget(a: dict, revenue_budget: dict) -> dict:
    monthly = []
    for m in revenue_budget["monthly"]:
        rev       = m["revenue"]
        salaries  = (a["base_headcount"] * a["avg_salary_monthly"]
                     * (1 + a["salary_growth"]))
        marketing = rev * a["marketing_pct"]
        rd        = rev * a["rd_pct"]
        ga        = rev * a["ga_pct"]
        rent      = a["rent_monthly"]
        dep       = a["depreciation_monthly"]
        total     = salaries + marketing + rd + ga + rent + dep
        monthly.append({
            "month":     m["month"],
            "salaries":  round(salaries, 0),
            "marketing": round(marketing, 0),
            "rd":        round(rd, 0),
            "ga":        round(ga, 0),
            "rent":      round(rent, 0),
            "depreciation": round(dep, 0),
            "total":     round(total, 0),
        })
    annual = sum(m["total"] for m in monthly)
    return {
        "type":    "SG&A Budget",
        "monthly": monthly,
        "annual":  round(annual, 0),
    }


# ══════════════════════════════════════════
# CAPEX BUDGET
# ══════════════════════════════════════════
def build_capex_budget(a: dict) -> dict:
    quarterly = a["capex_annual"] / 4
    monthly   = []
    for i, m in enumerate(MONTHS):
        # CapEx بيتنفق في أول كل ربع غالباً
        capex = quarterly if i % 3 == 0 else 0
        monthly.append({
            "month": m,
            "capex": round(capex, 0),
            "cumulative": round(quarterly * ((i // 3) + 1)
                                if i % 3 == 0
                                else quarterly * (i // 3), 0),
        })
    return {
        "type":    "CapEx Budget",
        "monthly": monthly,
        "annual":  round(a["capex_annual"], 0),
    }


# ══════════════════════════════════════════
# BUDGETED INCOME STATEMENT
# ══════════════════════════════════════════
def build_income_statement(
    revenue_budget: dict,
    cogs_budget:    dict,
    sga_budget:     dict,
    a:              dict,
) -> dict:
    monthly = []
    for i in range(12):
        rev  = revenue_budget["monthly"][i]["revenue"]
        cogs = cogs_budget["monthly"][i]["total"]
        sga  = sga_budget["monthly"][i]["total"]
        gp   = rev - cogs
        ebit = gp - sga
        int_ = a["loan_balance"] * a["interest_rate"] / 12
        ebt  = ebit - int_
        tax  = max(ebt * a["tax_rate"], 0)
        net  = ebt - tax
        monthly.append({
            "month":        MONTHS[i],
            "revenue":      round(rev, 0),
            "cogs":         round(cogs, 0),
            "gross_profit": round(gp, 0),
            "gross_margin": round(gp / rev * 100, 1) if rev else 0,
            "sga":          round(sga, 0),
            "ebit":         round(ebit, 0),
            "interest":     round(int_, 0),
            "tax":          round(tax, 0),
            "net_income":   round(net, 0),
            "net_margin":   round(net / rev * 100, 1) if rev else 0,
        })
    annual_rev = sum(m["revenue"]    for m in monthly)
    annual_net = sum(m["net_income"] for m in monthly)
    annual_gp  = sum(m["gross_profit"] for m in monthly)
    return {
        "type":           "Budgeted Income Statement",
        "monthly":        monthly,
        "annual_revenue": round(annual_rev, 0),
        "annual_gp":      round(annual_gp, 0),
        "annual_net":     round(annual_net, 0),
        "avg_gm":         round(annual_gp / annual_rev * 100, 1) if annual_rev else 0,
        "avg_nm":         round(annual_net / annual_rev * 100, 1) if annual_rev else 0,
    }


# ══════════════════════════════════════════
# CASH FLOW BUDGET
# ══════════════════════════════════════════
def build_cash_budget(
    income_statement: dict,
    capex_budget:     dict,
    a:                dict,
) -> dict:
    cash     = a["opening_cash"]
    monthly  = []
    for i in range(12):
        is_m    = income_statement["monthly"][i]
        cap_m   = capex_budget["monthly"][i]

        # Collections (مع تأخير الـ receivables)
        collections = is_m["revenue"] * (1 - a["receivables_days"] / 30 * 0.3)

        # Payments
        cogs_paid   = is_m["cogs"] * (1 - a["payables_days"] / 30 * 0.2)
        sga_paid    = is_m["sga"]
        tax_paid    = is_m["tax"]
        interest    = is_m["interest"]
        capex       = cap_m["capex"]

        # Net Cash
        operating   = collections - cogs_paid - sga_paid - tax_paid - interest
        investing   = -capex
        net         = operating + investing
        cash       += net

        monthly.append({
            "month":      MONTHS[i],
            "collections":round(collections, 0),
            "payments":   round(cogs_paid + sga_paid + tax_paid + interest, 0),
            "operating":  round(operating, 0),
            "investing":  round(investing, 0),
            "net_cash":   round(net, 0),
            "closing_cash":round(cash, 0),
        })

    return {
        "type":    "Cash Flow Budget",
        "monthly": monthly,
        "closing": round(cash, 0),
        "min_cash":round(min(m["closing_cash"] for m in monthly), 0),
    }


# ══════════════════════════════════════════
# WORKING CAPITAL BUDGET
# ══════════════════════════════════════════
def build_working_capital_budget(
    revenue_budget: dict,
    cogs_budget:    dict,
    a:              dict,
) -> dict:
    monthly = []
    for i in range(12):
        rev  = revenue_budget["monthly"][i]["revenue"]
        cogs = cogs_budget["monthly"][i]["total"]

        receivables = rev  * (a["receivables_days"] / 30)
        inventory   = cogs * (a["inventory_days"]   / 30)
        payables    = cogs * (a["payables_days"]     / 30)
        wc          = receivables + inventory - payables

        monthly.append({
            "month":       MONTHS[i],
            "receivables": round(receivables, 0),
            "inventory":   round(inventory, 0),
            "payables":    round(payables, 0),
            "working_capital": round(wc, 0),
        })
    return {
        "type":    "Working Capital Budget",
        "monthly": monthly,
        "avg_wc":  round(sum(m["working_capital"] for m in monthly) / 12, 0),
    }


# ══════════════════════════════════════════
# MASTER BUILDER — يبني كل حاجة مرة واحدة
# ══════════════════════════════════════════
def build_master_budget(assumptions: dict = None) -> dict:
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}

    # التأكد إن الـ seasonality مجموعها = 1
    total_season = sum(a["seasonality"])
    if abs(total_season - 1.0) > 0.01:
        a["seasonality"] = [s / total_season for s in a["seasonality"]]

    # بناء الميزانيات بالترتيب الصح
    revenue    = build_revenue_budget(a)
    production = build_production_budget(a, revenue)
    materials  = build_materials_budget(a, production)
    labor      = build_labor_budget(a, production)
    overhead   = build_overhead_budget(a, production)
    cogs       = build_cogs_budget(materials, labor, overhead)
    sga        = build_sga_budget(a, revenue)
    capex      = build_capex_budget(a)
    income_st  = build_income_statement(revenue, cogs, sga, a)
    cash       = build_cash_budget(income_st, capex, a)
    wc         = build_working_capital_budget(revenue, cogs, a)

    return {
        "assumptions":       a,
        "revenue":           revenue,
        "production":        production,
        "materials":         materials,
        "labor":             labor,
        "overhead":          overhead,
        "cogs":              cogs,
        "sga":               sga,
        "capex":             capex,
        "income_statement":  income_st,
        "cash_flow":         cash,
        "working_capital":   wc,
    }


# ══════════════════════════════════════════
# WHAT-IF SCENARIOS
# ══════════════════════════════════════════
def run_scenarios(base_assumptions: dict) -> dict:
    scenarios = {
        "Base Case": base_assumptions,
        "Optimistic": {
            **base_assumptions,
            "revenue_growth": base_assumptions["revenue_growth"] + 0.05,
            "cogs_pct":       base_assumptions["cogs_pct"] - 0.02,
        },
        "Pessimistic": {
            **base_assumptions,
            "revenue_growth": base_assumptions["revenue_growth"] - 0.05,
            "cogs_pct":       base_assumptions["cogs_pct"] + 0.03,
            "inflation_rate": base_assumptions["inflation_rate"] + 0.03,
        },
        "High Inflation": {
            **base_assumptions,
            "inflation_rate":      base_assumptions["inflation_rate"] + 0.05,
            "salary_growth":       base_assumptions["salary_growth"] + 0.03,
            "material_per_unit":   base_assumptions["material_per_unit"] * 1.10,
        },
    }

    results = {}
    for name, assum in scenarios.items():
        master  = build_master_budget(assum)
        is_data = master["income_statement"]
        results[name] = {
            "revenue":     is_data["annual_revenue"],
            "net_income":  is_data["annual_net"],
            "gross_margin":is_data["avg_gm"],
            "net_margin":  is_data["avg_nm"],
            "closing_cash":master["cash_flow"]["closing"],
        }
    return results


# ══════════════════════════════════════════
# AI EXPLANATION
# ══════════════════════════════════════════
def explain_budget(master_budget: dict) -> list:
    a  = master_budget["assumptions"]
    is_= master_budget["income_statement"]
    cf = master_budget["cash_flow"]
    insights = []

    insights.append(
        f"📈 Revenue projected at ${is_['annual_revenue']/1e6:.2f}M "
        f"({a['revenue_growth']*100:.0f}% growth assumption). "
        f"Peak month: {max(master_budget['revenue']['monthly'], key=lambda x: x['revenue'])['month']}."
    )

   
    insights.append(
        f"📊 Gross margin at {is_['avg_gm']:.1f}% — "
        f"{'healthy' if is_['avg_gm'] > 35 else 'needs improvement'}. "
        f"COGS driven by materials ({a['material_per_unit']} per unit) "
        f"+ {a['inflation_rate']*100:.0f}% inflation adjustment."
    )

    
    total_salaries = (a["base_headcount"] * a["avg_salary_monthly"]
                      * 12 * (1 + a["salary_growth"]))
    insights.append(
        f"👥 Payroll budget: ${total_salaries/1e6:.2f}M "
        f"({a['base_headcount']} employees × "
        f"${a['avg_salary_monthly']:,}/month + {a['salary_growth']*100:.0f}% growth)."
    )

   
    min_cash = cf["min_cash"]
    insights.append(
        f"💰 Minimum cash balance: ${min_cash/1e3:.0f}K. "
        f"{'Cash position healthy.' if min_cash > 100_000 else 'WARNING: Low cash — consider credit line.'}"
    )

    
    insights.append(
        f"🏗️ CapEx planned at ${a['capex_annual']/1e3:.0f}K annually "
        f"— impacts cash flow by ${a['capex_annual']/12/1e3:.0f}K/month."
    )

    return insights