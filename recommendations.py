"""
Recommendation Engine
"""
PRIORITY_MATRIX = {
    "Critical": "Immediate (This Week)",
    "High":     "Short-term (30 Days)",
    "Medium":   "Mid-term (90 Days)",
    "Low":      "Long-term (6 Months)",
}

def generate_recommendations(root_causes, kpis, forecasts, alerts):
    recs = []
    p = kpis.get("profitability", {})
    c = kpis.get("cost_efficiency", {})
    fc = forecasts.get("insights", {})

    if p.get("net_margin", 100) < 10:
        recs.append(_rec("High", "Revenue Growth", "Accelerate Revenue Generation",
            f"Net margin at {p.get('net_margin',0):.1f}% below 10% target",
            ["Review pricing — consider 3-5% increase on premium products",
             "Identify upsell opportunities in existing customer base",
             "Focus sales team on deals in final 2 pipeline stages",
             "Launch promotional campaign on highest-margin product lines"],
            "Chief Revenue Officer", "Net Margin → Target: >10%", "2-4% margin improvement in 90 days"))

    if c.get("cogs_ratio", 0) > 40:
        recs.append(_rec("High", "Cost of Goods", "Reduce COGS & Improve Gross Margin",
            f"COGS ratio at {c.get('cogs_ratio',0):.1f}% — above 40% benchmark",
            ["Renegotiate top 5 supplier contracts (target 5-8% reduction)",
             "Audit production efficiency — identify waste and idle capacity",
             "Evaluate make-vs-buy for key components",
             "Shift sales toward higher-margin SKUs"],
            "Chief Operations Officer", "COGS Ratio → Target: <38%", "1-3% gross margin expansion in 6 months"))

    if c.get("opex_ratio", 0) > 55:
        recs.append(_rec("High" if c.get("opex_ratio",0) > 65 else "Medium",
            "Operating Expenses", "Optimize Operating Cost Structure",
            f"OpEx at {c.get('opex_ratio',0):.1f}% of revenue — target <55%",
            ["Freeze non-essential hiring; review headcount productivity",
             "Audit SaaS subscriptions and vendor contracts",
             "Shift marketing to performance/ROI-driven channels",
             "Implement zero-based budgeting for next quarter"],
            "Chief Financial Officer", "OpEx Ratio → Target: <55%", "3-6% cost reduction in 60-90 days"))

    if fc.get("outlook") == "Declining":
        recs.append(_rec("High", "Strategic Planning", "Prepare for Revenue Headwinds",
            "3-month forecast indicates declining revenue trajectory",
            ["Activate contingency budget — identify $500K+ in deferrable spend",
             "Review and strengthen sales pipeline",
             "Engage top 10 customers proactively to secure renewals",
             "Accelerate receivables collection"],
            "CEO & CFO", "Revenue Growth → Reverse declining trend", "Preserve cash runway"))

    for rc in root_causes:
        if rc["severity"] == "Critical":
            recs.append(_rec("Critical", rc["category"], f"URGENT: {rc['title']}", rc["root_cause"],
                ["Convene emergency review with department heads",
                 "Implement spending freeze pending analysis",
                 "Weekly variance reporting until resolved",
                 "Escalate to board if not resolved in 30 days"],
                "CEO & CFO", f"Resolve {rc['title']}", rc.get("impact", "")))

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    recs.sort(key=lambda x: severity_order.get(x["priority"], 4))
    for i, r in enumerate(recs): r["number"] = i + 1
    return recs

def _rec(priority, category, title, problem, actions, owner, kpi, impact):
    return {"priority": priority, "category": category, "title": title, "problem": problem,
            "actions": actions, "owner": owner, "kpi_to_watch": kpi, "expected_impact": impact,
            "timeline": PRIORITY_MATRIX.get(priority, "30 Days")}

def generate_executive_summary(kpis, alerts, recommendations, forecasts):
    p  = kpis.get("profitability", {})
    sc = kpis.get("health_scores", {}).get("overall_score", 0)
    fc = forecasts.get("insights", {})
    critical = sum(1 for a in alerts if a["severity"] == "Critical")
    health = "STRONG" if sc >= 75 else "MODERATE" if sc >= 50 else "NEEDS ATTENTION"
    return (f"**Overall Health: {health}** (Score: {sc:.0f}/100)\n\n"
            f"Gross Margin: {p.get('gross_margin',0):.1f}% | Net Margin: {p.get('net_margin',0):.1f}% | "
            f"EBITDA: {p.get('ebitda_margin',0):.1f}%\n\n"
            f"Active Alerts: {len(alerts)} ({critical} Critical)\n\n"
            f"3-Month Outlook: {fc.get('outlook','Stable')} | "
            f"Revenue Growth: {fc.get('projected_revenue_growth',0):+.1f}%")