"""
Root Cause Engine — Academic Grade
بيحلل الأسباب الجذرية حسب نوع الميزانية:
- P&L: Margin compression, Revenue gaps, Cost overruns
- Cost Budgets: Cost efficiency, variance from budget
- Working Capital: Liquidity, CCC issues
- Fixed Assets: CapEx vs Depreciation
- Balance Sheet: Leverage, Liquidity ratios
"""

EXPENSE_CATEGORIES = {"COGS", "OpEx", "Non-Operating"}

# ══════════════════════════════════════════════════════════════════════════════
# 1. P&L ROOT CAUSE — الوحيد اللي بيحلل Revenue/Margin/Profit issues
# ══════════════════════════════════════════════════════════════════════════════

def analyze_root_causes(variances, kpis, summary):
    """P&L-specific root cause analysis"""
    findings   = []
    gm         = summary.get("gross_margin", 0)
    net_margin = kpis.get("profitability", {}).get("net_margin", 0)
    opex_ratio = kpis.get("cost_efficiency", {}).get("opex_ratio", 0)

    # Revenue variance
    rev_var = _find_category_variance(variances, "Revenue")
    if rev_var and rev_var["variance_pct"] < -3:
        findings.append({
            "severity":   "Critical" if rev_var["variance_pct"] < -10 else "High",
            "category":   "Revenue",
            "title":      "Revenue Below Target",
            "icon":       "📉",
            "root_cause": "Revenue gap driven by market demand or pricing pressure. Review sales pipeline and pricing strategy.",
            "impact":     f"${abs(rev_var['variance_abs']):,.0f} revenue gap vs budget",
            "variance_pct": rev_var["variance_pct"],
        })

    # Gross Margin compression
    if gm < 0.30:
        findings.append({
            "severity":   "High",
            "category":   "Margin",
            "title":      "Gross Margin Compression",
            "icon":       "⚠️",
            "root_cause": "Gross margin below 30% threshold. Review COGS structure: direct materials, labor efficiency, and overhead absorption.",
            "impact":     f"Gross margin at {gm*100:.1f}% — below 30% threshold",
            "variance_pct": (gm - 0.35) * 100,
        })

    # Cost overruns per line item
    for item in variances:
        ytd = item.get("ytd_variance")
        if not ytd:
            continue
        cat = item.get("category", "")
        if cat in EXPENSE_CATEGORIES and not ytd["favorable"] and ytd["severity"] in ("High", "Critical"):
            findings.append({
                "severity":   ytd["severity"],
                "category":   cat,
                "icon":       "🔴",
                "title":      f"Cost Overrun: {item['name']}",
                "root_cause": f"{item['name']} is {ytd['variance_pct']:+.1f}% over budget. Conduct detailed cost review and identify root drivers.",
                "impact":     f"${abs(ytd['variance_abs']):,.0f} over budget ({ytd['variance_pct']:+.1f}%)",
                "variance_pct": ytd["variance_pct"],
            })

    # OpEx ratio
    if opex_ratio and opex_ratio > 60:
        findings.append({
            "severity":   "High",
            "category":   "Efficiency",
            "title":      "High Operating Expense Ratio",
            "icon":       "⚙️",
            "root_cause": "Operating expenses >60% of revenue. Review headcount costs, overhead allocation, and discretionary spending.",
            "impact":     f"OpEx at {opex_ratio:.1f}% of revenue — benchmark <55%",
            "variance_pct": opex_ratio - 55,
        })

    # Net margin
    if net_margin < 5:
        findings.append({
            "severity":   "Medium",
            "category":   "Profitability",
            "title":      "Low Net Profit Margin",
            "icon":       "💡",
            "root_cause": "Net margin below 5%. Combined pressure from COGS, OpEx, or revenue shortfall. Prioritize highest-impact cost reduction.",
            "impact":     f"Net margin at {net_margin:.1f}% — target >10%",
            "variance_pct": net_margin - 10,
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return findings


def _find_category_variance(variances, category):
    total_actual = sum(i.get("ytd_actual", 0) for i in variances if i.get("category") == category)
    total_budget = sum(i.get("ytd_budget", 0) for i in variances if i.get("category") == category)
    if not total_budget:
        return None
    var_abs = total_actual - total_budget
    return {"variance_abs": var_abs, "variance_pct": var_abs / total_budget * 100}


# ══════════════════════════════════════════════════════════════════════════════
# 2. COST BUDGET ROOT CAUSE (Materials, OH, SG&A, General Budget)
# بيحلل كفاءة المصاريف — مفيش Margin Analysis هنا
# ══════════════════════════════════════════════════════════════════════════════

def analyze_cost_root_causes(analysis_result):
    """
    للميزانيات المصروفية:
    - هل في بنود بتزيد عن المخطط؟
    - هل نسبة المصروف للإيراد منطقية؟
    """
    findings    = []
    budget_type = analysis_result.get("type", "BUDGET")
    summary     = analysis_result.get("summary", {})
    charts      = analysis_result.get("charts", {})
    top_items   = charts.get("top_assets") or charts.get("by_category") or []

    total_cost   = (summary.get("total_cost") or summary.get("total_sga") or
                    summary.get("total_oh")   or summary.get("total_budget") or 0)
    total_actual = summary.get("total_actual", total_cost)
    variance_pct = summary.get("variance_pct", 0)

    type_labels = {
        "DIRECT_MATERIALS": "Direct Materials",
        "OVERHEADS":        "Production Overheads",
        "SGA":              "SG&A Expenses",
        "BUDGET":           "Budget",
    }
    label = type_labels.get(budget_type, "Cost")

    # Variance from budget
    if abs(variance_pct) > 10:
        findings.append({
            "severity":   "Critical" if abs(variance_pct) > 20 else "High",
            "category":   "Cost Variance",
            "title":      f"{label} Over Budget" if variance_pct > 0 else f"{label} Under Budget",
            "icon":       "🔴" if variance_pct > 0 else "🟡",
            "root_cause": (
                f"{label} is {abs(variance_pct):.1f}% {'above' if variance_pct > 0 else 'below'} budget. "
                f"Review line items for {'unexpected cost drivers' if variance_pct > 0 else 'underspend or delayed activities'}."
            ),
            "impact":     f"Total variance: {variance_pct:+.1f}%",
            "variance_pct": variance_pct,
        })

    # Top concentration items
    if top_items:
        top = sorted(top_items, key=lambda x: abs(x.get("actual", x.get("value", 0))), reverse=True)
        if top:
            biggest     = top[0]
            biggest_val = abs(biggest.get("actual", biggest.get("value", 0)))
            biggest_pct = biggest_val / total_actual * 100 if total_actual else 0
            if biggest_pct > 40:
                findings.append({
                    "severity":   "High",
                    "category":   "Concentration",
                    "title":      f"High {label} Concentration",
                    "icon":       "⚠️",
                    "root_cause": f"'{biggest.get('name', 'Top item')}' represents {biggest_pct:.0f}% of total {label}. Review for cost reduction opportunities.",
                    "impact":     f"{biggest_pct:.0f}% of total budget",
                    "variance_pct": biggest_pct - 40,
                })

    # SG&A specific: ratio to revenue
    if budget_type == "SGA":
        sga_pct = summary.get("sga_pct", 0)
        if sga_pct > 25:
            findings.append({
                "severity":   "High" if sga_pct > 35 else "Medium",
                "category":   "SG&A Efficiency",
                "title":      "SG&A Ratio Above Benchmark",
                "icon":       "💼",
                "root_cause": f"SG&A is {sga_pct:.1f}% of revenue (benchmark: <25%). Review selling costs and admin overhead.",
                "impact":     f"SG&A = {sga_pct:.1f}% of revenue",
                "variance_pct": sga_pct - 25,
            })

    # Overheads specific: fixed vs variable balance
    if budget_type == "OVERHEADS":
        fixed_pct = summary.get("fixed_pct", 0)
        if fixed_pct > 80:
            findings.append({
                "severity":   "High",
                "category":   "Cost Structure",
                "title":      "Very High Fixed Overhead",
                "icon":       "🏭",
                "root_cause": f"Fixed OH is {fixed_pct:.0f}% of total overhead. High operating leverage — review fixed cost commitments.",
                "impact":     f"Fixed OH = {fixed_pct:.0f}% — high risk in low-volume periods",
                "variance_pct": fixed_pct - 60,
            })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))

    if not findings:
        findings.append({
            "severity":   "Low",
            "category":   label,
            "title":      f"{label} Within Normal Range",
            "icon":       "✅",
            "root_cause": f"No significant issues detected in {label} budget.",
            "impact":     "All metrics within acceptable range",
            "variance_pct": 0,
        })

    return findings


# ══════════════════════════════════════════════════════════════════════════════
# 3. WORKING CAPITAL ROOT CAUSE
# DSO/DPO/DIO/CCC issues
# ══════════════════════════════════════════════════════════════════════════════

def analyze_wc_root_causes(analysis_result):
    findings = []
    summary  = analysis_result.get("summary", {})

    dso = summary.get("dso", 0)
    dpo = summary.get("dpo", 0)
    dio = summary.get("dio", 0)
    ccc = summary.get("ccc", 0)
    wc  = summary.get("working_capital", 0)

    if dso > 45:
        findings.append({
            "severity":   "High" if dso > 60 else "Medium",
            "category":   "Receivables",
            "title":      f"High DSO: {dso:.0f} Days",
            "icon":       "📥",
            "root_cause": f"DSO of {dso:.0f} days exceeds 45-day benchmark. Customers are paying slowly — review credit policy and collection procedures.",
            "impact":     f"Delayed cash collection: every 1 extra day = trapped cash",
            "variance_pct": dso - 30,
        })

    if dpo < 25:
        findings.append({
            "severity":   "Medium",
            "category":   "Payables",
            "title":      f"Low DPO: {dpo:.0f} Days",
            "icon":       "📤",
            "root_cause": f"DPO of {dpo:.0f} days is below 30-day standard. Paying suppliers too quickly — negotiate longer payment terms.",
            "impact":     "Early payments reduce available cash unnecessarily",
            "variance_pct": 30 - dpo,
        })

    if ccc > 45:
        findings.append({
            "severity":   "Critical" if ccc > 90 else "High",
            "category":   "Liquidity",
            "title":      f"Long Cash Conversion Cycle: {ccc:.0f} Days",
            "icon":       "🔄",
            "root_cause": f"CCC = DSO({dso:.0f}) + DIO({dio:.0f}) - DPO({dpo:.0f}) = {ccc:.0f} days. Cash is tied up for {ccc:.0f} days on average.",
            "impact":     f"Reduces operating cash flow and increases working capital requirement",
            "variance_pct": ccc - 30,
        })

    if wc < 0:
        findings.append({
            "severity":   "Critical",
            "category":   "Solvency",
            "title":      "Negative Working Capital",
            "icon":       "🚨",
            "root_cause": "Current liabilities exceed current assets. Risk of inability to meet short-term obligations.",
            "impact":     f"Negative WC = {wc:,.0f}",
            "variance_pct": -100,
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return findings


# ══════════════════════════════════════════════════════════════════════════════
# 4. FIXED ASSETS ROOT CAUSE
# CapEx efficiency, Depreciation coverage
# ══════════════════════════════════════════════════════════════════════════════

def analyze_fa_root_causes(analysis_result):
    findings = []
    summary  = analysis_result.get("summary", {})

    total_capex = summary.get("total_budget", 0)
    total_dep   = summary.get("total_depreciation", 0)
    net_inv     = total_capex - total_dep

    if net_inv < 0:
        findings.append({
            "severity":   "High",
            "category":   "Asset Base",
            "title":      "Net Disinvestment — Asset Base Shrinking",
            "icon":       "📉",
            "root_cause": f"Depreciation ({total_dep:,.0f}) > CapEx ({total_capex:,.0f}). The asset base is being consumed faster than it is being replaced.",
            "impact":     f"Net investment = {net_inv:,.0f} (negative)",
            "variance_pct": -abs(net_inv / total_capex * 100) if total_capex else 0,
        })
    else:
        findings.append({
            "severity":   "Low",
            "category":   "Asset Base",
            "title":      "Asset Base Growing",
            "icon":       "✅",
            "root_cause": f"CapEx ({total_capex:,.0f}) > Depreciation ({total_dep:,.0f}). Net investment is positive.",
            "impact":     f"Net investment = +{net_inv:,.0f}",
            "variance_pct": 0,
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return findings


# ══════════════════════════════════════════════════════════════════════════════
# 5. BALANCE SHEET ROOT CAUSE
# Liquidity & Leverage
# ══════════════════════════════════════════════════════════════════════════════

def analyze_bs_root_causes(analysis_result):
    findings = []
    summary  = analysis_result.get("summary", {})

    current_ratio  = summary.get("current_ratio", 0)
    debt_to_equity = summary.get("debt_to_equity", 0)
    working_capital = summary.get("working_capital", 0)

    if current_ratio < 1.0:
        findings.append({
            "severity":   "Critical",
            "category":   "Liquidity",
            "title":      f"Liquidity Crisis — Current Ratio: {current_ratio:.2f}x",
            "icon":       "🚨",
            "root_cause": f"Current ratio {current_ratio:.2f}x is below 1.0. Cannot cover short-term obligations with current assets.",
            "impact":     "Risk of default on short-term obligations",
            "variance_pct": (current_ratio - 1) * 100,
        })
    elif current_ratio < 1.5:
        findings.append({
            "severity":   "High",
            "category":   "Liquidity",
            "title":      f"Low Current Ratio: {current_ratio:.2f}x",
            "icon":       "⚠️",
            "root_cause": f"Current ratio {current_ratio:.2f}x below 1.5x standard. Limited liquidity buffer.",
            "impact":     "Tight liquidity — monitor cash closely",
            "variance_pct": (current_ratio - 1.5) * 100,
        })

    if debt_to_equity > 2.0:
        findings.append({
            "severity":   "High",
            "category":   "Leverage",
            "title":      f"High Leverage — D/E: {debt_to_equity:.2f}x",
            "icon":       "📊",
            "root_cause": f"Debt-to-Equity ratio of {debt_to_equity:.2f}x exceeds 2.0x. High financial risk — review debt structure.",
            "impact":     "High leverage amplifies losses and increases financing costs",
            "variance_pct": (debt_to_equity - 2) * 100,
        })

    if not findings:
        findings.append({
            "severity":   "Low",
            "category":   "Balance Sheet",
            "title":      "Balance Sheet Healthy",
            "icon":       "✅",
            "root_cause": "Liquidity and leverage ratios within acceptable ranges.",
            "impact":     "No immediate financial risk identified",
            "variance_pct": 0,
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return findings


# ══════════════════════════════════════════════════════════════════════════════
# SMART ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def analyze_root_causes_smart(analysis_result, variances=None, kpis=None):
    """
    Entry point موحد:
    بيوجه للـ root cause analyzer الصح حسب نوع الملف
    """
    budget_type = analysis_result.get("type", "UNKNOWN")
    summary     = analysis_result.get("summary", {})

    if budget_type == "P&L":
        return analyze_root_causes(variances or [], kpis or {}, summary)

    elif budget_type == "WORKING_CAPITAL":
        return analyze_wc_root_causes(analysis_result)

    elif budget_type == "FIXED_ASSETS":
        return analyze_fa_root_causes(analysis_result)

    elif budget_type == "BALANCE_SHEET":
        return analyze_bs_root_causes(analysis_result)

    elif budget_type in ("DIRECT_MATERIALS", "OVERHEADS", "SGA", "BUDGET", "PAYROLL"):
        return analyze_cost_root_causes(analysis_result)

    else:
        return [{
            "severity":   "Low",
            "category":   "Unknown",
            "title":      "File Type Not Fully Supported",
            "icon":       "❓",
            "root_cause": "Upload a P&L, Budget, or other recognized financial file.",
            "impact":     "—",
            "variance_pct": 0,
        }]
