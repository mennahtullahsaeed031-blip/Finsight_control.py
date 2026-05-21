"""
Alert Engine
"""
from datetime import datetime

def generate_alerts(kpis, variance_summary, root_causes):
    alerts = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    p = kpis.get("profitability", {})
    c = kpis.get("cost_efficiency", {})
    rv = variance_summary.get("revenue_variance", {})
    ev = variance_summary.get("expense_variance", {})

    checks = [
        (p.get("net_margin", 100) < 5,   "Critical", "🚨 Net Margin Critical",   f"Net margin ({p.get('net_margin',0):.1f}%) below 5% critical threshold"),
        (p.get("net_margin", 100) < 10,  "High",     "⚠️ Low Net Margin",        f"Net margin ({p.get('net_margin',0):.1f}%) below 10% target"),
        (p.get("gross_margin",100) < 25, "Critical", "🚨 Gross Margin Alert",    f"Gross margin ({p.get('gross_margin',0):.1f}%) below critical 25% floor"),
        (p.get("gross_margin",100) < 30, "High",     "⚠️ Margin Compression",    f"Gross margin ({p.get('gross_margin',0):.1f}%) below 30% benchmark"),
        (c.get("opex_ratio", 0) > 65,   "Critical", "🚨 Cost Structure Crisis", f"OpEx ratio ({c.get('opex_ratio',0):.1f}%) exceeds 65%"),
        (c.get("opex_ratio", 0) > 55,   "High",     "⚠️ OpEx Elevated",         f"OpEx ratio ({c.get('opex_ratio',0):.1f}%) above 55% benchmark"),
        (rv.get("variance_pct", 0) < -10,"Critical", "🚨 Revenue Shortfall",     f"Revenue is {rv.get('variance_pct',0):.1f}% below budget"),
        (rv.get("variance_pct", 0) < -5, "High",     "⚠️ Revenue Below Plan",    f"Revenue is {rv.get('variance_pct',0):.1f}% below budget"),
        (ev.get("variance_pct", 0) > 10, "Critical", "🚨 Cost Overrun Critical", f"Expenses are {ev.get('variance_pct',0):.1f}% above budget"),
        (ev.get("variance_pct", 0) > 5,  "High",     "⚠️ Cost Overrun",          f"Expenses are {ev.get('variance_pct',0):.1f}% over budget"),
    ]
    seen = set()
    for condition, severity, title, message in checks:
        if condition and title not in seen:
            seen.add(title)
            alerts.append({"severity": severity, "title": title, "message": message, "timestamp": ts})

    for rc in root_causes:
        if rc["severity"] in ("Critical", "High"):
            alerts.append({"severity": rc["severity"], "title": rc["title"],
                           "message": rc["root_cause"][:120], "timestamp": ts, "icon": rc.get("icon","⚠️")})

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return alerts

def get_alert_summary(alerts):
    return {
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["severity"] == "Critical"),
        "high": sum(1 for a in alerts if a["severity"] == "High"),
        "health_color": "red" if any(a["severity"]=="Critical" for a in alerts) else "orange" if any(a["severity"]=="High" for a in alerts) else "green"
    }