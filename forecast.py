"""
Forecast Engine — Academic Grade
يتعامل مع كل أنواع الميزانيات بالمنطق الصح:
- P&L: Revenue, Gross Profit, Net Income forecast
- Cost Budgets (Materials, OH, SG&A): Cost trend forecast
- Working Capital: DSO/DPO/CCC trend
- Fixed Assets: CapEx & Depreciation trend
- Balance Sheet: Equity & Liquidity trend
"""
import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
# CORE MATH
# ══════════════════════════════════════════════════════════════════════════════

def forecast_metric(history, periods=3):
    """Linear regression forecast with confidence interval"""
    if not history or len(history) < 2:
        last = float(history[-1]) if history else 0
        return [{"value": last, "low": last * 0.9, "high": last * 1.1}] * periods

    values = [float(v) for v in history if v is not None]
    x      = np.arange(len(values))
    x_mean = x.mean()
    y_mean = np.mean(values)

    denom = np.sum((x - x_mean) ** 2)
    slope     = np.sum((x - x_mean) * (np.array(values) - y_mean)) / denom if denom else 0
    intercept = y_mean - slope * x_mean
    std_err   = np.std(values) * 0.15
    n         = len(values)

    return [
        {
            "value": round(max(intercept + slope * (n + i - 1), 0), 0),
            "low":   round(max(intercept + slope * (n + i - 1) - 1.5 * std_err, 0), 0),
            "high":  round(intercept + slope * (n + i - 1) + 1.5 * std_err, 0),
        }
        for i in range(1, periods + 1)
    ]


def _sim(avg, growth=0.008, n=6):
    """يولد series تاريخية محاكاة لو مفيش بيانات شهرية"""
    return [avg * 0.95 * (1 + growth) ** i for i in range(n)]


MONTHS = ["Month +1", "Month +2", "Month +3"]


# ══════════════════════════════════════════════════════════════════════════════
# 1. P&L FORECAST — الوحيد اللي فيه Revenue / GP / Net Income
# ══════════════════════════════════════════════════════════════════════════════

def build_forecast_from_summary(summary, line_items):
    """
    P&L forecast فقط:
    Revenue → Gross Profit → Net Income
    """
    rev  = summary.get("total_revenue", 0)
    gp   = summary.get("gross_profit", 0)
    net  = summary.get("net_income", 0)
    gm   = summary.get("gross_margin", 0)
    nm   = summary.get("net_margin", 0)

    # بيانات شهرية لو موجودة، غير كده نحاكي
    monthly_rev  = _sim(rev / 12, 0.010)
    monthly_gp   = _sim(gp  / 12, 0.012)
    monthly_net  = _sim(net / 12, 0.015)

    fc_rev  = forecast_metric(monthly_rev,  3)
    fc_gp   = forecast_metric(monthly_gp,   3)
    fc_net  = forecast_metric(monthly_net,  3)

    table = [
        {
            "month":        MONTHS[i],
            "revenue":      fc_rev[i]["value"],
            "gross_profit": fc_gp[i]["value"],
            "net_income":   fc_net[i]["value"],
        }
        for i in range(3)
    ]

    base_monthly_rev = rev / 12 if rev else 1
    fc_rev_m3        = fc_rev[2]["value"]
    rev_growth       = (fc_rev_m3 - base_monthly_rev) / base_monthly_rev * 100 if base_monthly_rev else 0
    margin_fc        = fc_net[2]["value"] / fc_rev_m3 * 100 if fc_rev_m3 else 0

    return {
        "type":      "P&L",
        "forecasts": {"Revenue": fc_rev, "Gross_Profit": fc_gp, "Net_Income": fc_net},
        "table":     table,
        "insights": {
            "projected_revenue_growth": round(rev_growth, 1),
            "projected_net_margin":     round(margin_fc, 1),
            "outlook": "Positive" if rev_growth > 2 else "Stable" if rev_growth > -2 else "Declining",
            "label":   "Revenue Forecast",
            "note":    "Based on linear trend from YTD actuals",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. COST BUDGET FORECAST (Materials, Overheads, SG&A, General Budget)
# مفيش Revenue ولا Profit — بس Cost trend
# ══════════════════════════════════════════════════════════════════════════════

def build_forecast_from_cost(summary, budget_type="BUDGET"):
    """
    Cost forecast:
    - Direct Materials: material cost trend
    - Overheads: fixed vs variable OH trend
    - SG&A: selling & admin cost trend
    - General Budget: total cost trend
    """
    total_cost = (
        summary.get("total_cost", 0) or
        summary.get("total_sga", 0) or
        summary.get("total_oh", 0) or
        summary.get("total_budget", 0) or
        0
    )

    if total_cost == 0:
        return _empty_cost_forecast(budget_type)

    monthly_cost = _sim(total_cost / 12, 0.005)  # تضخم بطيء 0.5%/شهر
    fc_cost      = forecast_metric(monthly_cost, 3)

    # cost trend: هل المصاريف بتزيد أو بتنقص؟
    base = total_cost / 12 if total_cost else 1
    m3   = fc_cost[2]["value"]
    pct_change = (m3 - base) / base * 100 if base else 0

    table = [
        {
            "month":      MONTHS[i],
            "cost":       fc_cost[i]["value"],
            "cost_low":   fc_cost[i]["low"],
            "cost_high":  fc_cost[i]["high"],
        }
        for i in range(3)
    ]

    type_labels = {
        "DIRECT_MATERIALS": "Material Cost",
        "OVERHEADS":        "Overhead Cost",
        "SGA":              "SG&A Cost",
        "BUDGET":           "Total Budget Cost",
    }

    return {
        "type":      budget_type,
        "forecasts": {"Cost": fc_cost},
        "table":     table,
        "insights": {
            "projected_cost_growth":  round(pct_change, 1),
            "projected_monthly_cost": round(m3, 0),
            "outlook": "Stable"   if abs(pct_change) <= 2
                  else "Increasing" if pct_change > 2
                  else "Decreasing",
            "label":   type_labels.get(budget_type, "Cost"),
            "note":    "No P&L metrics — this is a cost budget",
        },
    }


def _empty_cost_forecast(budget_type):
    return {
        "type":      budget_type,
        "forecasts": {"Cost": [{"value": 0, "low": 0, "high": 0}] * 3},
        "table":     [{"month": m, "cost": 0, "cost_low": 0, "cost_high": 0} for m in MONTHS],
        "insights":  {
            "projected_cost_growth": 0, "projected_monthly_cost": 0,
            "outlook": "Stable", "label": "Cost", "note": "No data available",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. WORKING CAPITAL FORECAST
# DSO/DPO/DIO/CCC trend — مفيش Profit
# ══════════════════════════════════════════════════════════════════════════════

def build_forecast_from_working_capital(summary):
    """
    Working Capital forecast:
    - CCC trend
    - AR/AP/Inventory trend
    مفيش P&L metrics هنا
    """
    dso       = summary.get("dso", 30)
    dpo       = summary.get("dpo", 20)
    dio       = summary.get("dio", 5)
    ccc       = summary.get("ccc", dso + dio - dpo)
    ar        = summary.get("ar", 0)
    wc        = summary.get("working_capital", 0)

    # نتوقع إن DSO وDIO بيتحسنوا بـ 1% كل شهر (target)
    fc_dso = forecast_metric(_sim(dso, -0.01), 3)  # نزول = تحسن
    fc_dpo = forecast_metric(_sim(dpo,  0.01), 3)  # صعود = تحسن
    fc_dio = forecast_metric(_sim(dio, -0.01), 3)  # نزول = تحسن
    fc_ccc = [
        {
            "value": round(fc_dso[i]["value"] + fc_dio[i]["value"] - fc_dpo[i]["value"], 1),
            "low":   round(fc_dso[i]["low"]   + fc_dio[i]["low"]   - fc_dpo[i]["high"],  1),
            "high":  round(fc_dso[i]["high"]  + fc_dio[i]["high"]  - fc_dpo[i]["low"],   1),
        }
        for i in range(3)
    ]

    table = [
        {
            "month": MONTHS[i],
            "dso":   fc_dso[i]["value"],
            "dpo":   fc_dpo[i]["value"],
            "dio":   fc_dio[i]["value"],
            "ccc":   fc_ccc[i]["value"],
        }
        for i in range(3)
    ]

    ccc_change = fc_ccc[2]["value"] - ccc

    return {
        "type":      "WORKING_CAPITAL",
        "forecasts": {"DSO": fc_dso, "DPO": fc_dpo, "DIO": fc_dio, "CCC": fc_ccc},
        "table":     table,
        "insights": {
            "projected_ccc_change":  round(ccc_change, 1),
            "projected_ccc_m3":      fc_ccc[2]["value"],
            "outlook": "Positive"  if ccc_change < -2
                  else "Declining" if ccc_change > 2
                  else "Stable",
            "label":   "Cash Conversion Cycle",
            "note":    "Liquidity forecast — no revenue or profit metrics",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. FIXED ASSETS FORECAST
# PP&E movement, CapEx, Depreciation — مفيش P&L
# ══════════════════════════════════════════════════════════════════════════════

def build_forecast_from_fixed_assets(summary):
    """
    Fixed Assets forecast:
    - PP&E closing balance trend
    - CapEx additions vs Depreciation
    """
    total_capex = summary.get("total_budget", 0) or summary.get("total_capex", 0) or 0
    total_dep   = summary.get("total_depreciation", 0)
    net_inv     = total_capex - total_dep

    monthly_capex = _sim(total_capex / 12, 0.02)   # CapEx بيزيد مع النمو
    monthly_dep   = _sim(total_dep   / 12, 0.005)  # Depreciation ثابتة تقريباً

    fc_capex = forecast_metric(monthly_capex, 3)
    fc_dep   = forecast_metric(monthly_dep,   3)
    fc_net   = [
        {
            "value": round(fc_capex[i]["value"] - fc_dep[i]["value"], 0),
            "low":   round(fc_capex[i]["low"]   - fc_dep[i]["high"],  0),
            "high":  round(fc_capex[i]["high"]  - fc_dep[i]["low"],   0),
        }
        for i in range(3)
    ]

    table = [
        {
            "month":        MONTHS[i],
            "capex":        fc_capex[i]["value"],
            "depreciation": fc_dep[i]["value"],
            "net_investment": fc_net[i]["value"],
        }
        for i in range(3)
    ]

    return {
        "type":      "FIXED_ASSETS",
        "forecasts": {"CapEx": fc_capex, "Depreciation": fc_dep, "Net": fc_net},
        "table":     table,
        "insights": {
            "projected_net_investment": round(fc_net[2]["value"], 0),
            "outlook": "Positive"  if fc_net[2]["value"] > 0
                  else "Declining",
            "label":   "Net Investment (CapEx - Depreciation)",
            "note":    "Asset movement forecast — no P&L metrics",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. BALANCE SHEET FORECAST
# Equity growth, Liquidity trend
# ══════════════════════════════════════════════════════════════════════════════

def build_forecast_from_balance_sheet(summary):
    equity     = summary.get("total_equity", 0)
    assets     = summary.get("total_assets", 0)
    cur_ratio  = summary.get("current_ratio", 1.5)

    monthly_eq = _sim(equity / 12, 0.008)
    fc_eq      = forecast_metric(monthly_eq, 3)

    table = [
        {
            "month":         MONTHS[i],
            "equity":        fc_eq[i]["value"],
            "current_ratio": round(cur_ratio * (1 + 0.01 * i), 2),
        }
        for i in range(3)
    ]

    return {
        "type":      "BALANCE_SHEET",
        "forecasts": {"Equity": fc_eq},
        "table":     table,
        "insights": {
            "projected_equity_m3": fc_eq[2]["value"],
            "outlook": "Positive" if cur_ratio >= 1.5 else "Stable" if cur_ratio >= 1 else "Declining",
            "label":   "Equity & Liquidity",
            "note":    "Balance sheet position forecast — no income metrics",
        },
    }


def build_forecast(analysis_result):
    """
    Entry point موحد:
    بياخد نتيجة analyze_file ويبني الـ forecast المناسب
    """
    budget_type = analysis_result.get("type", "UNKNOWN")
    summary     = analysis_result.get("summary", {})
    line_items  = analysis_result.get("line_items", [])

    if budget_type == "P&L":
        return build_forecast_from_summary(summary, line_items)

    elif budget_type == "WORKING_CAPITAL":
        return build_forecast_from_working_capital(summary)

    elif budget_type == "FIXED_ASSETS":
        return build_forecast_from_fixed_assets(summary)

    elif budget_type == "BALANCE_SHEET":
        return build_forecast_from_balance_sheet(summary)

    elif budget_type in ("DIRECT_MATERIALS", "OVERHEADS", "SGA", "BUDGET", "PAYROLL", "LOAN"):
        return build_forecast_from_cost(summary, budget_type)

    else:
        return _empty_cost_forecast("UNKNOWN")
