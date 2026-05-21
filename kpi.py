"""
KPI Engine
"""
def calculate_kpis(summary, line_items=None, headcount=150):
    rev = summary.get("total_revenue", 0)
    cogs = summary.get("total_cogs", 0)
    gp = summary.get("gross_profit", 0)
    opex = summary.get("total_opex", 0)
    ebit = summary.get("ebit", 0)
    net = summary.get("net_income", 0)
    ebitda = ebit + rev * 0.018
    mktg = sum(i.get("total", 0) for i in (line_items or []) if any(x in i.get("name","").lower() for x in ["marketing","sales","تسويق"]))
    def pct(n, d): return round((n / d) * 100, 2) if d else 0
    p_score = min(gp/rev*200 if rev else 0, 50) + min(net/rev*500 if rev else 0, 50)
    e_score = 100 if opex/rev<=0.30 else 85 if opex/rev<=0.40 else 70 if opex/rev<=0.50 else 55 if opex/rev<=0.60 else 40 if opex/rev<=0.70 else 20
    return {
        "profitability": {
            "gross_margin": pct(gp, rev), "net_margin": pct(net, rev),
            "ebitda_margin": pct(ebitda, rev), "ebit_margin": pct(ebit, rev),
        },
        "cost_efficiency": {
            "cogs_ratio": pct(cogs, rev), "opex_ratio": pct(opex, rev),
            "marketing_ratio": pct(mktg, rev) if mktg else None,
        },
        "growth_indicators": {"revenue": rev, "gross_profit": gp, "ebitda": ebitda, "net_income": net},
        "operational": {"revenue_per_employee": rev/headcount if headcount else 0,
                        "profit_per_employee": net/headcount if headcount else 0, "headcount": headcount},
        "health_scores": {"profitability_score": round(p_score, 1),
                          "efficiency_score": e_score, "overall_score": round((p_score + e_score) / 2, 1)},
    }

def format_kpi_card(kpis):
    p = kpis["profitability"]
    c = kpis["cost_efficiency"]
    g = kpis["growth_indicators"]
    def fmt(v): return f"${v/1e6:.2f}M" if abs(v)>=1e6 else f"${v/1e3:.1f}K" if abs(v)>=1e3 else f"${v:.0f}"
    return [
        {"label": "Gross Margin",  "value": f"{p['gross_margin']:.1f}%",  "status": "good" if p['gross_margin']>30 else "warning",  "benchmark": "30%+"},
        {"label": "Net Margin",    "value": f"{p['net_margin']:.1f}%",    "status": "good" if p['net_margin']>10 else "warning",    "benchmark": "10%+"},
        {"label": "EBITDA Margin", "value": f"{p['ebitda_margin']:.1f}%", "status": "good" if p['ebitda_margin']>15 else "warning", "benchmark": "15%+"},
        {"label": "OpEx Ratio",    "value": f"{c['opex_ratio']:.1f}%",    "status": "good" if c['opex_ratio']<55 else "warning",   "benchmark": "<55%"},
        {"label": "Net Income",    "value": fmt(g['net_income']),          "status": "good" if g['net_income']>0 else "critical",   "benchmark": ">0"},
        {"label": "EBITDA",        "value": fmt(g['ebitda']),              "status": "good" if g['ebitda']>0 else "critical",       "benchmark": ">0"},
    ]