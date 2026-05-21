"""
Forecast Engine — 3 months ahead
"""
import numpy as np

def forecast_metric(history, periods=3):
    if not history or len(history) < 2:
        last = history[-1] if history else 0
        return [{"value": last, "low": last*0.9, "high": last*1.1}] * periods
    values = [float(v) for v in history if v is not None]
    x = np.arange(len(values))
    x_mean, y_mean = x.mean(), np.mean(values)
    slope = np.sum((x - x_mean) * (values - y_mean)) / np.sum((x - x_mean)**2)
    intercept = y_mean - slope * x_mean
    std_err = np.std(values) * 0.15
    n = len(values)
    return [
        {"value": round(max(intercept + slope*(n+i-1), 0), 0),
         "low":   round(max(intercept + slope*(n+i-1) - 1.5*std_err, 0), 0),
         "high":  round(intercept + slope*(n+i-1) + 1.5*std_err, 0)}
        for i in range(1, periods+1)
    ]

def build_forecast_from_summary(summary, line_items):
    rev  = summary.get("total_revenue", 0)
    cogs = summary.get("total_cogs", 0)
    gp   = summary.get("gross_profit", 0)
    opex = summary.get("total_opex", 0)
    net  = summary.get("net_income", 0)

    def sim(avg, g=0.008): return [avg*0.95*(1+g)**i for i in range(6)]

    forecasts = {
        "Revenue":      forecast_metric(sim(rev/12, 0.01), 3),
        "Gross_Profit": forecast_metric(sim(gp/12, 0.012), 3),
        "Net_Income":   forecast_metric(sim(net/12, 0.015), 3),
    }
    months = ["Month +1", "Month +2", "Month +3"]
    table = [{"month": months[i],
              "revenue":      forecasts["Revenue"][i]["value"],
              "gross_profit": forecasts["Gross_Profit"][i]["value"],
              "net_income":   forecasts["Net_Income"][i]["value"]} for i in range(3)]

    rev_growth = ((forecasts["Revenue"][2]["value"] - rev/12) / (rev/12) * 100) if rev else 0
    margin_fc  = (forecasts["Net_Income"][2]["value"] / forecasts["Revenue"][2]["value"] * 100) if forecasts["Revenue"][2]["value"] else 0
    return {
        "forecasts": forecasts, "table": table,
        "insights": {
            "projected_revenue_growth": round(rev_growth, 1),
            "projected_net_margin":     round(margin_fc, 1),
            "outlook": "Positive" if rev_growth > 2 else "Stable" if rev_growth > -2 else "Declining",
        }
    }