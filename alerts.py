"""
Alert Engine — Academic Grade
بيولد alerts حسب نوع الميزانية:
- P&L: Margin, Revenue, Cost alerts
- Cost Budgets: Variance alerts
- Working Capital: CCC, DSO, Liquidity alerts
- Fixed Assets: CapEx vs Depreciation alerts
- Balance Sheet: Ratio alerts
"""
from datetime import datetime


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ══════════════════════════════════════════════════════════════════════════════
# 1. P&L ALERTS — الوحيد اللي فيه Margin/Revenue alerts
# ══════════════════════════════════════════════════════════════════════════════

def generate_alerts(kpis, variance_summary, root_causes):
    """P&L-specific alerts فقط"""
    alerts = []
    ts     = _ts()
    p      = kpis.get("profitability", {})
    c      = kpis.get("cost_efficiency", {})
    rv     = variance_summary.get("revenue_variance", {})
    ev     = variance_summary.get("expense_variance", {})

    checks = [
        (p.get("net_margin",   100) < 5,   "Critical", "🚨 Net Margin Critical",
         f"Net margin ({p.get('net_margin',0):.1f}%) below 5% critical threshold"),
        (p.get("net_margin",   100) < 10,  "High",     "⚠️ Low Net Margin",
         f"Net margin ({p.get('net_margin',0):.1f}%) below 10% target"),
        (p.get("gross_margin", 100) < 25,  "Critical", "🚨 Gross Margin Alert",
         f"Gross margin ({p.get('gross_margin',0):.1f}%) below critical 25% floor"),
        (p.get("gross_margin", 100) < 30,  "High",     "⚠️ Margin Compression",
         f"Gross margin ({p.get('gross_margin',0):.1f}%) below 30% benchmark"),
        (c.get("opex_ratio",     0) > 65,  "Critical", "🚨 Cost Structure Crisis",
         f"OpEx ratio ({c.get('opex_ratio',0):.1f}%) exceeds 65%"),
        (c.get("opex_ratio",     0) > 55,  "High",     "⚠️ OpEx Elevated",
         f"OpEx ratio ({c.get('opex_ratio',0):.1f}%) above 55% benchmark"),
        (rv.get("variance_pct",  0) < -10, "Critical", "🚨 Revenue Shortfall",
         f"Revenue is {rv.get('variance_pct',0):.1f}% below budget"),
        (rv.get("variance_pct",  0) < -5,  "High",     "⚠️ Revenue Below Plan",
         f"Revenue is {rv.get('variance_pct',0):.1f}% below budget"),
        (ev.get("variance_pct",  0) > 10,  "Critical", "🚨 Cost Overrun Critical",
         f"Expenses are {ev.get('variance_pct',0):.1f}% above budget"),
        (ev.get("variance_pct",  0) > 5,   "High",     "⚠️ Cost Overrun",
         f"Expenses are {ev.get('variance_pct',0):.1f}% over budget"),
    ]

    seen = set()
    for condition, severity, title, message in checks:
        if condition and title not in seen:
            seen.add(title)
            alerts.append({
                "severity":  severity,
                "title":     title,
                "message":   message,
                "timestamp": ts,
                "icon":      title.split()[0],
            })

    for rc in root_causes:
        if rc["severity"] in ("Critical", "High"):
            alerts.append({
                "severity":  rc["severity"],
                "title":     rc["title"],
                "message":   rc["root_cause"][:120],
                "timestamp": ts,
                "icon":      rc.get("icon", "⚠️"),
            })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return alerts


def get_alert_summary(alerts):
    return {
        "total":        len(alerts),
        "critical":     sum(1 for a in alerts if a["severity"] == "Critical"),
        "high":         sum(1 for a in alerts if a["severity"] == "High"),
        "health_color": (
            "red"    if any(a["severity"] == "Critical" for a in alerts) else
            "orange" if any(a["severity"] == "High"     for a in alerts) else
            "green"
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. COST BUDGET ALERTS (Materials, OH, SG&A, Budget)
# فقط Cost variance — مفيش Margin alerts
# ══════════════════════════════════════════════════════════════════════════════

def generate_cost_alerts(analysis_result, root_causes=None):
    """للميزانيات المصروفية — فقط cost variance alerts"""
    alerts      = []
    ts          = _ts()
    budget_type = analysis_result.get("type", "BUDGET")
    summary     = analysis_result.get("summary", {})

    variance_pct = summary.get("variance_pct", 0)
    total_cost   = (summary.get("total_cost") or summary.get("total_sga") or
                    summary.get("total_oh")   or summary.get("total_budget") or 0)

    type_labels = {
        "DIRECT_MATERIALS": "Materials",
        "OVERHEADS":        "Overheads",
        "SGA":              "SG&A",
        "BUDGET":           "Budget",
    }
    label = type_labels.get(budget_type, "Cost")

    if variance_pct > 20:
        alerts.append({
            "severity":  "Critical",
            "title":     f"🚨 {label} Severely Over Budget",
            "message":   f"{label} is {variance_pct:.1f}% above budget — immediate review required",
            "timestamp": ts, "icon": "🚨",
        })
    elif variance_pct > 10:
        alerts.append({
            "severity":  "High",
            "title":     f"⚠️ {label} Over Budget",
            "message":   f"{label} is {variance_pct:.1f}% above budget",
            "timestamp": ts, "icon": "⚠️",
        })
    elif variance_pct < -15:
        alerts.append({
            "severity":  "Medium",
            "title":     f"💡 {label} Under Budget",
            "message":   f"{label} is {abs(variance_pct):.1f}% below budget — review for delayed activities",
            "timestamp": ts, "icon": "💡",
        })

    # SG&A ratio alert
    if budget_type == "SGA":
        sga_pct = summary.get("sga_pct", 0)
        if sga_pct > 35:
            alerts.append({
                "severity":  "High",
                "title":     "⚠️ High SG&A Ratio",
                "message":   f"SG&A = {sga_pct:.1f}% of revenue (benchmark <25%)",
                "timestamp": ts, "icon": "⚠️",
            })

    # Overheads: Fixed % alert
    if budget_type == "OVERHEADS":
        fixed_pct = summary.get("fixed_pct", 0)
        if fixed_pct > 85:
            alerts.append({
                "severity":  "High",
                "title":     "⚠️ Very High Fixed Overhead",
                "message":   f"Fixed OH = {fixed_pct:.0f}% — high operating leverage",
                "timestamp": ts, "icon": "🏭",
            })

    # من root causes
    if root_causes:
        for rc in root_causes:
            if rc["severity"] in ("Critical", "High"):
                alerts.append({
                    "severity":  rc["severity"],
                    "title":     rc["title"],
                    "message":   rc["root_cause"][:120],
                    "timestamp": ts,
                    "icon":      rc.get("icon", "⚠️"),
                })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# 3. WORKING CAPITAL ALERTS
# CCC, DSO, Liquidity
# ══════════════════════════════════════════════════════════════════════════════

def generate_wc_alerts(analysis_result, root_causes=None):
    alerts  = []
    ts      = _ts()
    summary = analysis_result.get("summary", {})

    dso = summary.get("dso", 0)
    dpo = summary.get("dpo", 0)
    ccc = summary.get("ccc", 0)
    wc  = summary.get("working_capital", 0)

    if wc < 0:
        alerts.append({
            "severity":  "Critical",
            "title":     "🚨 Negative Working Capital",
            "message":   "Current liabilities exceed current assets — solvency risk",
            "timestamp": ts, "icon": "🚨",
        })
    if ccc > 90:
        alerts.append({
            "severity":  "Critical",
            "title":     f"🚨 Cash Conversion Cycle: {ccc:.0f} Days",
            "message":   f"CCC of {ccc:.0f} days severely strains operating cash flow",
            "timestamp": ts, "icon": "🚨",
        })
    elif ccc > 45:
        alerts.append({
            "severity":  "High",
            "title":     f"⚠️ High CCC: {ccc:.0f} Days",
            "message":   f"DSO({dso:.0f}) + DIO - DPO({dpo:.0f}) = {ccc:.0f} days — review collections",
            "timestamp": ts, "icon": "⚠️",
        })
    if dso > 60:
        alerts.append({
            "severity":  "High",
            "title":     f"⚠️ High DSO: {dso:.0f} Days",
            "message":   "Slow receivables collection — review credit terms",
            "timestamp": ts, "icon": "📥",
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# 4. FIXED ASSETS ALERTS
# ══════════════════════════════════════════════════════════════════════════════

def generate_fa_alerts(analysis_result, root_causes=None):
    alerts  = []
    ts      = _ts()
    summary = analysis_result.get("summary", {})

    total_capex = summary.get("total_budget", 0)
    total_dep   = summary.get("total_depreciation", 0)
    net_inv     = total_capex - total_dep

    if net_inv < 0:
        alerts.append({
            "severity":  "High",
            "title":     "⚠️ Asset Base Shrinking",
            "message":   f"Depreciation ({total_dep:,.0f}) > CapEx ({total_capex:,.0f}) — net disinvestment",
            "timestamp": ts, "icon": "📉",
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# 5. BALANCE SHEET ALERTS
# ══════════════════════════════════════════════════════════════════════════════

def generate_bs_alerts(analysis_result, root_causes=None):
    alerts  = []
    ts      = _ts()
    summary = analysis_result.get("summary", {})

    current_ratio  = summary.get("current_ratio", 2)
    debt_to_equity = summary.get("debt_to_equity", 0)

    if current_ratio < 1.0:
        alerts.append({
            "severity":  "Critical",
            "title":     f"🚨 Liquidity Crisis — CR: {current_ratio:.2f}x",
            "message":   "Current ratio below 1.0 — cannot cover short-term obligations",
            "timestamp": ts, "icon": "🚨",
        })
    elif current_ratio < 1.5:
        alerts.append({
            "severity":  "High",
            "title":     f"⚠️ Low Liquidity — CR: {current_ratio:.2f}x",
            "message":   f"Current ratio {current_ratio:.2f}x below 1.5x benchmark",
            "timestamp": ts, "icon": "⚠️",
        })

    if debt_to_equity > 2.0:
        alerts.append({
            "severity":  "High",
            "title":     f"⚠️ High Leverage — D/E: {debt_to_equity:.2f}x",
            "message":   f"Debt-to-Equity {debt_to_equity:.2f}x exceeds 2.0x — review financing",
            "timestamp": ts, "icon": "📊",
        })

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
# SMART ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def generate_alerts_smart(analysis_result, kpis=None, variance_summary=None, root_causes=None):
    """
    Entry point موحد:
    بيختار الـ alert generator الصح حسب نوع الملف
    """
    budget_type = analysis_result.get("type", "UNKNOWN")

    if budget_type == "P&L":
        return generate_alerts(kpis or {}, variance_summary or {}, root_causes or [])

    elif budget_type == "WORKING_CAPITAL":
        return generate_wc_alerts(analysis_result, root_causes)

    elif budget_type == "FIXED_ASSETS":
        return generate_fa_alerts(analysis_result, root_causes)

    elif budget_type == "BALANCE_SHEET":
        return generate_bs_alerts(analysis_result, root_causes)

    elif budget_type in ("DIRECT_MATERIALS", "OVERHEADS", "SGA", "BUDGET", "PAYROLL"):
        return generate_cost_alerts(analysis_result, root_causes)

    else:
        return []
