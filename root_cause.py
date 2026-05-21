"""
Root Cause Engine
"""
EXPENSE_CATEGORIES = {"COGS", "OpEx", "Non-Operating"}

def analyze_root_causes(variances, kpis, summary):
    findings = []
    rev = summary.get("total_revenue", 0)
    gm = summary.get("gross_margin", 0)
    net_margin = kpis.get("profitability", {}).get("net_margin", 0)
    opex_ratio = kpis.get("cost_efficiency", {}).get("opex_ratio", 0)

    rev_var = _find_category_variance(variances, "Revenue")
    if rev_var and rev_var["variance_pct"] < -3:
        findings.append({
            "severity": "Critical" if rev_var["variance_pct"] < -10 else "High",
            "category": "Revenue", "title": "Revenue Below Target", "icon": "📉",
            "root_cause": f"Revenue gap driven by market demand or pricing pressure. Review sales pipeline.",
            "impact": f"${abs(rev_var['variance_abs']):,.0f} revenue gap vs budget",
            "variance_pct": rev_var["variance_pct"],
        })
    if gm < 0.30:
        findings.append({
            "severity": "High", "category": "Margin", "title": "Gross Margin Compression", "icon": "⚠️",
            "root_cause": "Gross margin below 30% threshold. Review COGS structure and pricing power.",
            "impact": f"Gross margin at {gm*100:.1f}% — below 30% threshold",
            "variance_pct": (gm - 0.35) * 100,
        })
    for item in variances:
        ytd = item.get("ytd_variance")
        if not ytd: continue
        cat = item.get("category", "")
        if cat in EXPENSE_CATEGORIES and not ytd["favorable"] and ytd["severity"] in ("High", "Critical"):
            findings.append({
                "severity": ytd["severity"], "category": cat, "icon": "🔴",
                "title": f"Cost Overrun: {item['name']}",
                "root_cause": f"{item['name']} is {ytd['variance_pct']:+.1f}% over budget. Conduct detailed cost review.",
                "impact": f"${abs(ytd['variance_abs']):,.0f} over budget ({ytd['variance_pct']:+.1f}%)",
                "variance_pct": ytd["variance_pct"],
            })
    if opex_ratio and opex_ratio > 60:
        findings.append({
            "severity": "High", "category": "Efficiency", "title": "High Operating Expense Ratio", "icon": "⚙️",
            "root_cause": "Operating expenses >60% of revenue. Review headcount, overhead, discretionary spending.",
            "impact": f"OpEx at {opex_ratio:.1f}% of revenue — benchmark <55%",
            "variance_pct": opex_ratio - 55,
        })
    if net_margin < 5:
        findings.append({
            "severity": "Medium", "category": "Profitability", "title": "Low Net Profit Margin", "icon": "💡",
            "root_cause": "Net margin below 5%. Combined pressure from COGS, OpEx, or revenue shortfall.",
            "impact": f"Net margin at {net_margin:.1f}% — target >10%",
            "variance_pct": net_margin - 10,
        })
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return findings

def _find_category_variance(variances, category):
    total_actual = sum(i.get("ytd_actual", 0) for i in variances if i.get("category") == category)
    total_budget = sum(i.get("ytd_budget", 0) for i in variances if i.get("category") == category)
    if not total_budget: return None
    var_abs = total_actual - total_budget
    return {"variance_abs": var_abs, "variance_pct": (var_abs / total_budget) * 100}