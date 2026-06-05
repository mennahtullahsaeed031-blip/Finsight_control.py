"""
Module 1: Master Budget Builder
CMA Part 2 Standard — Academic Grade
Sales Forecast → Full Master Budget → Budgeted Financial Statements
"""

# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT ASSUMPTIONS
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_ASSUMPTIONS = {
    # Revenue
    "base_revenue":         1_000_000,
    "revenue_growth":       0.10,
    "price_per_unit":       100,
    "seasonality": [
        0.07, 0.07, 0.08, 0.08, 0.09, 0.09,
        0.09, 0.09, 0.08, 0.09, 0.09, 0.08
    ],

    # Production Costs (Variable)
    "material_per_unit":    30,        # 30% of price
    "labor_hours_per_unit": 2,
    "labor_rate_per_hour":  10,        # $10/hr

    # Manufacturing Overhead
    "variable_oh_per_unit": 5,         # Variable OH per unit
    "fixed_oh_monthly":     8_000,     # Fixed Manufacturing OH
    "depreciation_monthly": 2_000,     # ضمن Fixed OH

    # SG&A — designed so total SG&A ≈ 25-30% of revenue
    "base_headcount":       10,        # موظفين SG&A فقط (مش production)
    "avg_salary_monthly":   4_000,     # $4,000/شهر/موظف
    "salary_growth":        0.05,
    "marketing_pct":        0.05,      # 5% of revenue
    "rd_pct":               0.02,      # 2% of revenue
    "ga_pct":               0.02,      # 2% of revenue
    "office_rent_monthly":  4_000,
    "sga_depreciation_monthly": 1_000,

    # CapEx
    "capex_annual":         100_000,
    "asset_useful_life_yrs":5,

    # Finance
    "loan_balance":         500_000,
    "interest_rate":        0.12,
    "tax_rate":             0.22,

    # Working Capital Policy
    "receivables_days":     45,
    "payables_days":        30,
    "inventory_days":       60,
    "beginning_inventory_units": 200,

    # Balance Sheet Opening Balances
    "opening_cash":         100_000,
    "opening_ppe":          300_000,
    "opening_equity":       200_000,
    "opening_long_term_debt":500_000,

    # Inflation
    "inflation_rate":       0.07,
}

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: SALES BUDGET
# Input: Sales Forecast, Selling Price, Seasonality
# Output: Monthly Revenue & Units
# ══════════════════════════════════════════════════════════════════════════════
def build_revenue_budget(a: dict) -> dict:
    """
    CMA: Sales Budget = Foundation of Master Budget
    كل الميزانيات التانية بتنبني عليه
    """
    base   = a["base_revenue"] * (1 + a["revenue_growth"])
    monthly = []
    for i, season in enumerate(a["seasonality"]):
        rev   = round(base * season, 0)
        units = round(rev / a["price_per_unit"], 0) if a["price_per_unit"] else 0
        monthly.append({"month": MONTHS[i], "revenue": rev, "units": units})

    total_rev   = sum(m["revenue"] for m in monthly)
    total_units = sum(m["units"]   for m in monthly)

    return {
        "type":        "Sales Budget",
        "monthly":     monthly,
        "annual":      round(total_rev, 0),
        "total_units": round(total_units, 0),
        "growth":      a["revenue_growth"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: PRODUCTION BUDGET
# Input: Sales Budget, Inventory Policy
# Output: Units to Produce
# Formula: Units to Produce = Sales Units + Desired Ending Inv - Beginning Inv
# ══════════════════════════════════════════════════════════════════════════════
def build_production_budget(a: dict, revenue_budget: dict) -> dict:
    """
    CMA: Production Budget
    Units to Produce = Expected Sales + Desired Ending Inventory - Beginning Inventory
    """
    monthly = []
    prev_ending = a["beginning_inventory_units"]

    for i, m in enumerate(revenue_budget["monthly"]):
        units_sold    = m["units"]
        # Desired ending inventory = next month's sales * (inventory_days/30)
        if i < 11:
            next_sales  = revenue_budget["monthly"][i+1]["units"]
        else:
            next_sales  = units_sold  # December: assume same as current
        desired_ending  = round(next_sales * (a["inventory_days"] / 30), 0)
        units_to_produce = round(units_sold + desired_ending - prev_ending, 0)
        units_to_produce = max(units_to_produce, 0)

        monthly.append({
            "month":             MONTHS[i],
            "units_sold":        round(units_sold, 0),
            "beginning_inv":     round(prev_ending, 0),
            "desired_ending_inv":round(desired_ending, 0),
            "units_to_produce":  units_to_produce,
        })
        prev_ending = desired_ending

    return {
        "type":        "Production Budget",
        "monthly":     monthly,
        "total_units": round(sum(m["units_to_produce"] for m in monthly), 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: DIRECT MATERIALS BUDGET
# Input: Production Budget, Material Cost per Unit, Inflation
# Output: Quantity Needed + Purchase Cost
# Formula: Qty to Purchase = Production Needs + Desired Ending Mat - Beginning Mat
# ══════════════════════════════════════════════════════════════════════════════
def build_materials_budget(a: dict, production_budget: dict) -> dict:
    """
    CMA: Direct Materials Budget
    Adjusts for inflation on material prices
    """
    mat_cost_per_unit = a["material_per_unit"] * (1 + a["inflation_rate"])
    monthly = []

    for m in production_budget["monthly"]:
        qty_for_prod  = m["units_to_produce"] * a["material_per_unit"]
        purchase_cost = m["units_to_produce"] * mat_cost_per_unit
        monthly.append({
            "month":          m["month"],
            "units_to_prod":  m["units_to_produce"],
            "qty_needed":     round(qty_for_prod, 0),
            "cost_per_unit":  round(mat_cost_per_unit, 2),
            "total_cost":     round(purchase_cost, 0),
        })

    annual = sum(m["total_cost"] for m in monthly)
    return {
        "type":      "Direct Materials Budget",
        "monthly":   monthly,
        "annual":    round(annual, 0),
        "unit_cost": round(mat_cost_per_unit, 2),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: DIRECT LABOR BUDGET
# Input: Production Budget, Labor Hours/Unit, Rate/Hour
# Output: Hours Required + Labor Cost
# ══════════════════════════════════════════════════════════════════════════════
def build_labor_budget(a: dict, production_budget: dict) -> dict:
    """
    CMA: Direct Labor Budget
    Total Labor Cost = Units × Hours/Unit × Rate/Hour
    """
    rate = a["labor_rate_per_hour"] * (1 + a["salary_growth"])
    monthly = []

    for m in production_budget["monthly"]:
        hours = m["units_to_produce"] * a["labor_hours_per_unit"]
        cost  = hours * rate
        monthly.append({
            "month":         m["month"],
            "units_to_prod": m["units_to_produce"],
            "hours_needed":  round(hours, 0),
            "rate_per_hour": round(rate, 2),
            "total_cost":    round(cost, 0),
        })

    annual = sum(m["total_cost"] for m in monthly)
    return {
        "type":    "Direct Labor Budget",
        "monthly": monthly,
        "annual":  round(annual, 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: MANUFACTURING OVERHEAD BUDGET
# Fixed OH + Variable OH
# Fixed: Rent, Depreciation, Indirect Labor
# Variable: Utilities, Supplies (per unit)
# ══════════════════════════════════════════════════════════════════════════════
def build_overhead_budget(a: dict, production_budget: dict) -> dict:
    """
    CMA: Manufacturing Overhead Budget
    Total OH = Fixed OH + Variable OH
    Fixed OH: same every month regardless of volume
    Variable OH: changes with production units
    """
    monthly = []
    for m in production_budget["monthly"]:
        variable_oh = m["units_to_produce"] * a["variable_oh_per_unit"]
        fixed_oh    = a["fixed_oh_monthly"]
        total_oh    = variable_oh + fixed_oh

        monthly.append({
            "month":       m["month"],
            "units":       m["units_to_produce"],
            "variable_oh": round(variable_oh, 0),
            "fixed_oh":    round(fixed_oh, 0),
            "depreciation":round(a["depreciation_monthly"], 0),
            "total":       round(total_oh, 0),
        })

    annual       = sum(m["total"]       for m in monthly)
    annual_fixed = sum(m["fixed_oh"]    for m in monthly)
    annual_var   = sum(m["variable_oh"] for m in monthly)

    return {
        "type":         "Manufacturing Overhead Budget",
        "monthly":      monthly,
        "annual":       round(annual, 0),
        "annual_fixed": round(annual_fixed, 0),
        "annual_var":   round(annual_var, 0),
        "fixed_pct":    round(annual_fixed / annual * 100, 1) if annual else 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: COST OF GOODS SOLD (COGS) BUDGET
# = Direct Materials + Direct Labor + Manufacturing Overhead
# ══════════════════════════════════════════════════════════════════════════════
def build_cogs_budget(materials: dict, labor: dict, overhead: dict) -> dict:
    """
    CMA: COGS Budget
    Direct Materials + Direct Labor + Manufacturing OH = Total COGS
    """
    monthly = []
    for i in range(12):
        mat  = materials["monthly"][i]["total_cost"]
        lab  = labor["monthly"][i]["total_cost"]
        ovh  = overhead["monthly"][i]["total"]
        total = mat + lab + ovh
        monthly.append({
            "month":     MONTHS[i],
            "materials": round(mat, 0),
            "labor":     round(lab, 0),
            "overhead":  round(ovh, 0),
            "total":     round(total, 0),
        })

    annual = sum(m["total"] for m in monthly)
    return {
        "type":    "COGS Budget",
        "monthly": monthly,
        "annual":  round(annual, 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7: SG&A BUDGET
# Selling Expenses + General & Administrative Expenses
# مختلف عن Manufacturing Overhead — ده Period Cost مش Product Cost
# ══════════════════════════════════════════════════════════════════════════════
def build_sga_budget(a: dict, revenue_budget: dict) -> dict:
    """
    CMA: SG&A Budget — Period Costs
    NOT included in COGS — charged directly to Income Statement
    """
    monthly = []
    for m in revenue_budget["monthly"]:
        rev      = m["revenue"]
        salaries = a["base_headcount"] * a["avg_salary_monthly"] * (1 + a["salary_growth"])
        marketing = rev * a["marketing_pct"]
        rd        = rev * a["rd_pct"]
        ga        = rev * a["ga_pct"]
        rent      = a["office_rent_monthly"]
        dep       = a["sga_depreciation_monthly"]
        total     = salaries + marketing + rd + ga + rent + dep

        monthly.append({
            "month":        m["month"],
            "salaries":     round(salaries, 0),
            "marketing":    round(marketing, 0),
            "rd":           round(rd, 0),
            "ga":           round(ga, 0),
            "rent":         round(rent, 0),
            "depreciation": round(dep, 0),
            "total":        round(total, 0),
            "sga_pct_rev":  round(total / rev * 100, 1) if rev else 0,
        })

    annual = sum(m["total"] for m in monthly)
    return {
        "type":    "SG&A Budget",
        "monthly": monthly,
        "annual":  round(annual, 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 8: CAPEX BUDGET
# ══════════════════════════════════════════════════════════════════════════════
def build_capex_budget(a: dict) -> dict:
    quarterly = a["capex_annual"] / 4
    annual_dep = a["capex_annual"] / a.get("asset_useful_life_yrs", 5)
    monthly = []
    for i, m in enumerate(MONTHS):
        capex = quarterly if i % 3 == 0 else 0
        monthly.append({
            "month":      m,
            "capex":      round(capex, 0),
            "depreciation": round(annual_dep / 12, 0),
        })
    return {
        "type":           "CapEx Budget",
        "monthly":        monthly,
        "annual":         round(a["capex_annual"], 0),
        "annual_dep":     round(annual_dep, 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: BUDGETED INCOME STATEMENT
# Revenue - COGS = Gross Profit
# Gross Profit - SG&A = EBIT
# EBIT - Interest = EBT
# EBT - Tax = Net Income
# ══════════════════════════════════════════════════════════════════════════════
def build_income_statement(
    revenue_budget: dict,
    cogs_budget:    dict,
    sga_budget:     dict,
    a:              dict,
) -> dict:
    """
    CMA: Budgeted Income Statement
    The only statement where Gross Margin and Net Margin are calculated
    """
    monthly = []
    for i in range(12):
        rev  = revenue_budget["monthly"][i]["revenue"]
        cogs = cogs_budget["monthly"][i]["total"]
        sga  = sga_budget["monthly"][i]["total"]
        gp   = rev - cogs
        ebit = gp - sga
        interest = a["loan_balance"] * a["interest_rate"] / 12
        ebt  = ebit - interest
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
            "ebit_margin":  round(ebit / rev * 100, 1) if rev else 0,
            "interest":     round(interest, 0),
            "ebt":          round(ebt, 0),
            "tax":          round(tax, 0),
            "net_income":   round(net, 0),
            "net_margin":   round(net / rev * 100, 1) if rev else 0,
        })

    annual_rev = sum(m["revenue"]      for m in monthly)
    annual_gp  = sum(m["gross_profit"] for m in monthly)
    annual_net = sum(m["net_income"]   for m in monthly)

    return {
        "type":           "Budgeted Income Statement",
        "monthly":        monthly,
        "annual_revenue": round(annual_rev, 0),
        "annual_gp":      round(annual_gp, 0),
        "annual_net":     round(annual_net, 0),
        "avg_gm":         round(annual_gp  / annual_rev * 100, 1) if annual_rev else 0,
        "avg_nm":         round(annual_net / annual_rev * 100, 1) if annual_rev else 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: CASH BUDGET
# Collections + Payments based on Collection/Payment Policy
# ══════════════════════════════════════════════════════════════════════════════
def build_cash_budget(
    income_statement: dict,
    capex_budget:     dict,
    a:                dict,
) -> dict:
    """
    CMA: Cash Budget
    Operating + Investing + Financing Cash Flows
    Collection Policy → when revenue becomes cash
    Payment Policy → when costs become cash outflows
    """
    cash    = a["opening_cash"]
    monthly = []

    for i in range(12):
        is_m  = income_statement["monthly"][i]
        cap_m = capex_budget["monthly"][i]

        # Collections (receivables policy)
        collection_rate = 1 - (a["receivables_days"] / 30 * 0.3)
        collections     = is_m["revenue"] * collection_rate

        # Payments (payables policy)
        payment_rate    = 1 - (a["payables_days"] / 30 * 0.2)
        cogs_paid       = is_m["cogs"] * payment_rate
        sga_paid        = is_m["sga"]
        tax_paid        = is_m["tax"]
        interest_paid   = is_m["interest"]

        # Cash flows
        operating = collections - cogs_paid - sga_paid - tax_paid - interest_paid
        investing  = -cap_m["capex"]
        net        = operating + investing
        cash      += net

        monthly.append({
            "month":         MONTHS[i],
            "collections":   round(collections, 0),
            "cogs_paid":     round(cogs_paid, 0),
            "sga_paid":      round(sga_paid, 0),
            "tax_paid":      round(tax_paid, 0),
            "interest_paid": round(interest_paid, 0),
            "operating_cf":  round(operating, 0),
            "investing_cf":  round(investing, 0),
            "net_cash":      round(net, 0),
            "closing_cash":  round(cash, 0),
        })

    return {
        "type":     "Cash Budget",
        "monthly":  monthly,
        "closing":  round(cash, 0),
        "min_cash": round(min(m["closing_cash"] for m in monthly), 0),
        "total_operating": round(sum(m["operating_cf"] for m in monthly), 0),
        "total_investing": round(sum(m["investing_cf"] for m in monthly), 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 11: WORKING CAPITAL BUDGET
# AR + Inventory - AP
# ══════════════════════════════════════════════════════════════════════════════
def build_working_capital_budget(
    revenue_budget: dict,
    cogs_budget:    dict,
    a:              dict,
) -> dict:
    monthly = []
    for i in range(12):
        rev  = revenue_budget["monthly"][i]["revenue"]
        cogs = cogs_budget["monthly"][i]["total"]
        ar   = rev  * (a["receivables_days"] / 30)
        inv  = cogs * (a["inventory_days"]   / 30)
        ap   = cogs * (a["payables_days"]     / 30)
        wc   = ar + inv - ap
        ccc  = a["receivables_days"] + a["inventory_days"] - a["payables_days"]

        monthly.append({
            "month":           MONTHS[i],
            "accounts_receivable": round(ar, 0),
            "inventory":       round(inv, 0),
            "accounts_payable":round(ap, 0),
            "working_capital": round(wc, 0),
            "ccc_days":        round(ccc, 0),
        })

    avg_wc = sum(m["working_capital"] for m in monthly) / 12
    return {
        "type":    "Working Capital Budget",
        "monthly": monthly,
        "avg_wc":  round(avg_wc, 0),
        "dso":     a["receivables_days"],
        "dpo":     a["payables_days"],
        "dio":     a["inventory_days"],
        "ccc":     a["receivables_days"] + a["inventory_days"] - a["payables_days"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12: BUDGETED BALANCE SHEET
# Opening Balances + Movements from all budgets
# ══════════════════════════════════════════════════════════════════════════════
def build_balance_sheet(
    income_statement:  dict,
    cash_budget:       dict,
    capex_budget:      dict,
    working_capital:   dict,
    a:                 dict,
) -> dict:
    """
    CMA: Budgeted Balance Sheet
    Assets = Liabilities + Equity
    """
    # Assets
    closing_cash = cash_budget["closing"]

    last_wc      = working_capital["monthly"][-1]
    ar           = last_wc["accounts_receivable"]
    inventory    = last_wc["inventory"]

    opening_ppe  = a["opening_ppe"]
    capex_added  = capex_budget["annual"]
    total_dep    = (a["depreciation_monthly"] + a["sga_depreciation_monthly"]) * 12
    closing_ppe  = opening_ppe + capex_added - total_dep

    total_current_assets = closing_cash + ar + inventory
    total_assets         = total_current_assets + closing_ppe

    # Liabilities
    ap           = last_wc["accounts_payable"]
    long_term_debt = a["opening_long_term_debt"]   # simplified: no repayment modeled
    total_liabilities = ap + long_term_debt

    # Equity
    opening_equity = a["opening_equity"]
    net_income     = income_statement["annual_net"]
    closing_equity = opening_equity + net_income
    # Assets = Liabilities + Equity check
    check = total_assets - (total_liabilities + closing_equity)

    current_ratio  = total_current_assets / ap if ap else 0
    debt_to_equity = total_liabilities / closing_equity if closing_equity else 0

    return {
        "type": "Budgeted Balance Sheet",
        # Assets
        "cash":                 round(closing_cash, 0),
        "accounts_receivable":  round(ar, 0),
        "inventory":            round(inventory, 0),
        "total_current_assets": round(total_current_assets, 0),
        "net_ppe":              round(closing_ppe, 0),
        "total_assets":         round(total_assets, 0),
        # Liabilities
        "accounts_payable":     round(ap, 0),
        "long_term_debt":       round(long_term_debt, 0),
        "total_liabilities":    round(total_liabilities, 0),
        # Equity
        "opening_equity":       round(opening_equity, 0),
        "net_income":           round(net_income, 0),
        "closing_equity":       round(closing_equity, 0),
        # Ratios
        "current_ratio":        round(current_ratio, 2),
        "debt_to_equity":       round(debt_to_equity, 2),
        "balance_check":        round(check, 0),  # يجب = 0
    }


# ══════════════════════════════════════════════════════════════════════════════
# MASTER BUILDER — builds everything in CMA order
# ══════════════════════════════════════════════════════════════════════════════
def build_master_budget(assumptions: dict = None) -> dict:
    a = {**DEFAULT_ASSUMPTIONS, **(assumptions or {})}

    # Normalize seasonality
    total_s = sum(a["seasonality"])
    if abs(total_s - 1.0) > 0.01:
        a["seasonality"] = [s / total_s for s in a["seasonality"]]

    # CMA Order: Sales → Production → Materials → Labor → OH → COGS → SG&A → IS → Cash → WC → BS
    revenue    = build_revenue_budget(a)
    production = build_production_budget(a, revenue)
    materials  = build_materials_budget(a, production)
    labor      = build_labor_budget(a, production)
    overhead   = build_overhead_budget(a, production)
    cogs       = build_cogs_budget(materials, labor, overhead, revenue)
    sga        = build_sga_budget(a, revenue)
    capex      = build_capex_budget(a)
    income_st  = build_income_statement(revenue, cogs, sga, a)
    cash       = build_cash_budget(income_st, capex, a)
    wc         = build_working_capital_budget(revenue, cogs, a)
    bs         = build_balance_sheet(income_st, cash, capex, wc, a)

    return {
        "assumptions":      a,
        "revenue":          revenue,
        "production":       production,
        "materials":        materials,
        "labor":            labor,
        "overhead":         overhead,
        "cogs":             cogs,
        "sga":              sga,
        "capex":            capex,
        "income_statement": income_st,
        "cash_flow":        cash,
        "working_capital":  wc,
        "balance_sheet":    bs,
    }


# ══════════════════════════════════════════════════════════════════════════════
# WHAT-IF SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════
def run_scenarios(base_assumptions: dict) -> dict:
    scenarios = {
        "Base Case": base_assumptions,
        "Optimistic": {
            **base_assumptions,
            "revenue_growth":  base_assumptions.get("revenue_growth", 0.10) + 0.05,
            "cogs_pct":        base_assumptions.get("cogs_pct", 0.38)       - 0.02,
        },
        "Pessimistic": {
            **base_assumptions,
            "revenue_growth":  base_assumptions.get("revenue_growth", 0.10) - 0.05,
            "inflation_rate":  base_assumptions.get("inflation_rate", 0.07) + 0.03,
        },
        "High Inflation": {
            **base_assumptions,
            "inflation_rate":     base_assumptions.get("inflation_rate",  0.07) + 0.05,
            "salary_growth":      base_assumptions.get("salary_growth",   0.05) + 0.03,
            "material_per_unit":  base_assumptions.get("material_per_unit",30)  * 1.10,
        },
    }
    results = {}
    for name, assum in scenarios.items():
        master = build_master_budget(assum)
        is_d   = master["income_statement"]
        results[name] = {
            "revenue":      is_d["annual_revenue"],
            "net_income":   is_d["annual_net"],
            "gross_margin": is_d["avg_gm"],
            "net_margin":   is_d["avg_nm"],
            "closing_cash": master["cash_flow"]["closing"],
        }
    return results


# ══════════════════════════════════════════════════════════════════════════════
# BUDGET INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
def explain_budget(master_budget: dict) -> list:
    a   = master_budget["assumptions"]
    is_ = master_budget["income_statement"]
    cf  = master_budget["cash_flow"]
    bs  = master_budget["balance_sheet"]
    insights = []

    # Revenue
    peak = max(master_budget["revenue"]["monthly"], key=lambda x: x["revenue"])
    insights.append(
        f"📈 Revenue projected at ${is_['annual_revenue']/1e6:.2f}M "
        f"({a['revenue_growth']*100:.0f}% growth). Peak month: {peak['month']}."
    )
    # Gross Margin
    insights.append(
        f"📊 Gross Margin: {is_['avg_gm']:.1f}% — "
        f"{'healthy ✅' if is_['avg_gm'] > 35 else 'needs improvement ⚠️'}. "
        f"COGS driven by materials + {a['inflation_rate']*100:.0f}% inflation."
    )
    # Payroll
    annual_payroll = a["base_headcount"] * a["avg_salary_monthly"] * 12 * (1 + a["salary_growth"])
    insights.append(
        f"👥 Payroll: ${annual_payroll/1e6:.2f}M "
        f"({a['base_headcount']} employees × ${a['avg_salary_monthly']:,}/mo + "
        f"{a['salary_growth']*100:.0f}% growth)."
    )
    # Cash
    min_cash = cf["min_cash"]
    insights.append(
        f"💰 Min cash: ${min_cash/1e3:.0f}K. "
        f"{'Healthy ✅' if min_cash > 100_000 else '⚠️ Low — consider credit line.'}"
    )
    # Balance Sheet Check
    insights.append(
        f"🏦 Balance Sheet: Assets=${bs['total_assets']/1e6:.2f}M | "
        f"Equity=${bs['closing_equity']/1e6:.2f}M | "
        f"D/E={bs['debt_to_equity']:.2f}x | CR={bs['current_ratio']:.2f}x | "
        + ("Check=✅ Balanced." if abs(bs['balance_check']) < 1
           else f"Check=⚠️ Off by {bs['balance_check']:,.0f}.")
    )

    return insights
