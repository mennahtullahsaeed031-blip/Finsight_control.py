import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from mapping import map_file
from variance import calculate_all_variances, variance_summary
from kpi import calculate_kpis, format_kpi_card
from root_cause import analyze_root_causes
from alerts import generate_alerts, get_alert_summary
from forecast import build_forecast_from_summary
from recommendations import generate_recommendations, generate_executive_summary

# ── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="FinSight CFO Dashboard", page_icon="📊", layout="wide")

# ── DARK THEME CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700;800&family=DM+Mono:wght@400;600&display=swap');

*, body, .stApp { font-family: 'DM Sans', sans-serif !important; }
.stApp { background: #080F1E !important; color: #F0F6FF !important; }
section[data-testid="stSidebar"] { background: #0F1E3C !important; border-right: 1px solid #1E3A5F; }
.block-container { padding: 1.5rem 2rem !important; max-width: 1400px; }

/* Cards */
.fin-card {
    background: #111F38;
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 16px;
}
.fin-card-accent-green  { border-top: 3px solid #10B981; }
.fin-card-accent-red    { border-top: 3px solid #EF4444; }
.fin-card-accent-blue   { border-top: 3px solid #3B82F6; }
.fin-card-accent-yellow { border-top: 3px solid #F59E0B; }
.fin-card-accent-purple { border-top: 3px solid #8B5CF6; }
.fin-card-accent-cyan   { border-top: 3px solid #06B6D4; }

/* KPI Cards */
.kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 20px; }
.kpi-card {
    background: linear-gradient(135deg, #111F38, #1A2F52);
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 16px 18px;
}
.kpi-label { color: #8BA3C7; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }
.kpi-value { font-family: 'DM Mono', monospace; font-size: 28px; font-weight: 800; line-height: 1; margin: 8px 0 4px; }
.kpi-good    { color: #10B981; border-top: 2px solid #10B981; }
.kpi-warning { color: #F59E0B; border-top: 2px solid #F59E0B; }
.kpi-critical{ color: #EF4444; border-top: 2px solid #EF4444; }

/* Alerts */
.alert-critical { background:#3B0A0A; border:1px solid #EF4444; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.alert-high     { background:#2D1B00; border:1px solid #F97316; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.alert-medium   { background:#1A2200; border:1px solid #EAB308; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.alert-title    { font-weight:700; font-size:13px; margin-bottom:4px; }
.alert-msg      { color:#8BA3C7; font-size:12px; line-height:1.5; }
.badge { display:inline-block; border-radius:4px; padding:2px 7px; font-size:10px; font-weight:800; }
.badge-critical { background:#EF4444; color:#fff; }
.badge-high     { background:#F97316; color:#fff; }
.badge-medium   { background:#EAB308; color:#000; }

/* Metric big */
.big-metric { font-family:'DM Mono',monospace; font-size:32px; font-weight:800; }
.section-title {
    display:flex; align-items:center; gap:10px;
    font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em;
    color:#F0F6FF; margin-bottom:14px;
}
.section-title::before { content:''; display:block; width:3px; height:18px; background:#06B6D4; border-radius:2px; }

/* Recommendation cards */
.rec-card {
    background:#111F38; border:1px solid #1E3A5F;
    border-radius:10px; padding:16px; margin-bottom:12px;
}
.rec-action { display:flex; gap:8px; align-items:flex-start; margin-bottom:6px; font-size:13px; color:#F0F6FF; }
.rec-num {
    background:#1E5CC8; color:#fff; border-radius:50%;
    width:20px; height:20px; font-size:10px; font-weight:800;
    display:flex; align-items:center; justify-content:center; flex-shrink:0;
}

/* Hide Streamlit defaults */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
div[data-testid="stToolbar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── HELPERS ──────────────────────────────────────────────────────────────────
def fmt_money(v):
    if v is None: return "—"
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v/1e6:.2f}M" if v >= 1e6 else f"{s}${v/1e3:.0f}K" if v >= 1e3 else f"{s}${v:.0f}"

def fmt_pct(v): return f"{v*100:.1f}%" if v else "0.0%"

DEMO = {
    "summary": {
        "total_revenue":15361000,"total_cogs":5896000,"gross_profit":9465000,
        "gross_margin":0.616,"total_opex":7614000,"ebit":1851000,
        "ebit_margin":0.121,"total_nonop":624000,"net_income":1227000,"net_margin":0.0799
    },
    "line_items":[
        {"name":"Product Revenue","category":"Revenue","values":{},"total":11630000,"ytd_actual":11630000,"ytd_budget":11540000,"ytd_variance":{"variance_abs":90000,"variance_pct":0.78,"favorable":True,"severity":"Low","status":"Favorable"}},
        {"name":"Service Revenue","category":"Revenue","values":{},"total":3110000,"ytd_actual":3110000,"ytd_budget":3070000,"ytd_variance":{"variance_abs":40000,"variance_pct":1.3,"favorable":True,"severity":"Low","status":"Favorable"}},
        {"name":"COGS - Products","category":"COGS","values":{},"total":4652000,"ytd_actual":4652000,"ytd_budget":4616000,"ytd_variance":{"variance_abs":36000,"variance_pct":0.78,"favorable":False,"severity":"Low","status":"Unfavorable"}},
        {"name":"Salaries & Benefits","category":"OpEx","values":{},"total":3620000,"ytd_actual":3620000,"ytd_budget":3550000,"ytd_variance":{"variance_abs":70000,"variance_pct":1.97,"favorable":False,"severity":"Low","status":"Unfavorable"}},
        {"name":"Marketing & Sales","category":"OpEx","values":{},"total":1302000,"ytd_actual":1302000,"ytd_budget":1296000,"ytd_variance":{"variance_abs":6000,"variance_pct":0.46,"favorable":False,"severity":"Low","status":"Unfavorable"}},
        {"name":"R&D Expenses","category":"OpEx","values":{},"total":1564000,"ytd_actual":1564000,"ytd_budget":1541000,"ytd_variance":{"variance_abs":23000,"variance_pct":1.49,"favorable":False,"severity":"Low","status":"Unfavorable"}},
        {"name":"Interest Expense","category":"Non-Operating","values":{},"total":186000,"ytd_actual":186000,"ytd_budget":198000,"ytd_variance":{"variance_abs":-12000,"variance_pct":-6.06,"favorable":True,"severity":"Medium","status":"Favorable"}},
    ],
    "monthly":[
        {"month":"Jan","actual":1115000,"budget":1040000},{"month":"Feb","actual":1152000,"budget":1112000},
        {"month":"Mar","actual":1208000,"budget":1175000},{"month":"Apr","actual":1191000,"budget":1180000},
        {"month":"May","actual":1250000,"budget":1243000},{"month":"Jun","actual":1282000,"budget":1265000},
        {"month":"Jul","actual":1314000,"budget":1297000},{"month":"Aug","actual":1346000,"budget":1329000},
        {"month":"Sep","actual":1298000,"budget":1322000},{"month":"Oct","actual":1350000,"budget":1385000},
        {"month":"Nov","actual":1393000,"budget":1418000},{"month":"Dec","actual":1462000,"budget":1470000},
    ]
}

def process_data(summary, line_items):
    variances   = calculate_all_variances(line_items)
    var_sum     = variance_summary(variances)
    kpis        = calculate_kpis(summary, line_items)
    kpi_cards   = format_kpi_card(kpis)
    root_causes = analyze_root_causes(variances, kpis, summary)
    alerts      = generate_alerts(kpis, var_sum, root_causes)
    alert_sum   = get_alert_summary(alerts)
    forecasts   = build_forecast_from_summary(summary, line_items)
    recs        = generate_recommendations(root_causes, kpis, forecasts, alerts)
    exec_sum    = generate_executive_summary(kpis, alerts, recs, forecasts)
    return variances, var_sum, kpis, kpi_cards, root_causes, alerts, alert_sum, forecasts, recs, exec_sum

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding:20px 0 10px'>
        <div style='background:linear-gradient(135deg,#1E5CC8,#06B6D4);width:48px;height:48px;
                    border-radius:12px;display:inline-flex;align-items:center;justify-content:center;font-size:24px;'>
            📊
        </div>
        <div style='color:#F0F6FF;font-size:20px;font-weight:800;margin-top:8px;letter-spacing:-0.02em'>FinSight</div>
        <div style='color:#8BA3C7;font-size:11px;letter-spacing:0.12em;text-transform:uppercase'>CFO Intelligence Platform</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    uploaded = st.file_uploader("📂 Upload Excel P&L", type=["xlsx","xls"], label_visibility="collapsed")

    use_demo = st.button("🎯 Try Demo Data (NileTech)", use_container_width=True)

    st.markdown("---")
    st.markdown("<div style='color:#8BA3C7;font-size:11px;'>**Pipeline**</div>", unsafe_allow_html=True)
    for step in ["📊 Map P&L","📉 Variances","🎯 KPIs","🔍 Root Cause","🚨 Alerts","🔮 Forecast","💡 Recommendations"]:
        st.markdown(f"<div style='color:#8BA3C7;font-size:12px;padding:3px 0'>→ {step}</div>", unsafe_allow_html=True)

# ── LOAD DATA ────────────────────────────────────────────────────────────────
# ── LOAD DATA ──────────────────────────────────────
data_loaded = False
summary = line_items = monthly_data = company_name = period = None

if use_demo or "demo_loaded" in st.session_state:
    if use_demo: 
        st.session_state["demo_loaded"] = True
        st.session_state.pop("file_loaded", None)  
    summary      = DEMO["summary"]
    line_items   = DEMO["line_items"]
    monthly_data = DEMO["monthly"]
    company_name = "NileTech Solutions"
    period       = "FY 2024"
    data_loaded  = True

elif uploaded:
    
    if "processed" not in st.session_state or st.session_state.get("last_file") != uploaded.name:
        with st.spinner("🔍 Analyzing Excel file..."):
            import tempfile, os, gc
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            
            mapped = map_file(tmp_path)
            gc.collect()
            try:
                os.unlink(tmp_path)
            except PermissionError:
                pass
            
            pl = mapped.get("pl_data") or {}
            s  = pl.get("summary", {})
            li = pl.get("line_items", [])
            
            if not s or s.get("total_revenue", 0) == 0:
                s  = DEMO["summary"]
                li = DEMO["line_items"]
                st.warning("⚠️ Could not parse P&L — showing demo data.")
            
            # ← احفظ النتيجة في session_state
            st.session_state["processed"]   = True
            st.session_state["summary"]     = s
            st.session_state["line_items"]  = li
            st.session_state["last_file"]   = uploaded.name
            st.session_state["company"]     = uploaded.name.replace(".xlsx","").replace(".xls","")

   
    summary      = st.session_state["summary"]
    line_items   = st.session_state["line_items"]
    monthly_data = DEMO["monthly"]
    company_name = st.session_state["company"]
    period       = "YTD"
    data_loaded  = True
elif uploaded:
    with st.spinner("🔍 Analyzing Excel file..."):
        import tempfile, os
        import tempfile, os, gc

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
      tmp.write(uploaded.read())
      tmp_path = tmp.name

      mapped = map_file(tmp_path)

      gc.collect()
    try:
     os.unlink(tmp_path)
    except PermissionError:
        pass
        pl = mapped.get("pl_data") or {}
        summary    = pl.get("summary", {})
        line_items = pl.get("line_items", [])
        if not summary or summary.get("total_revenue", 0) == 0:
            summary    = DEMO["summary"]
            line_items = DEMO["line_items"]
            st.warning("⚠️ Could not parse P&L structure — showing demo data.")
        monthly_data = DEMO["monthly"]
        company_name = uploaded.name.replace(".xlsx","").replace(".xls","")
        period       = "YTD"
        data_loaded  = True

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
if not data_loaded:
    st.markdown("""
    <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:70vh;text-align:center;'>
        <div style='font-size:64px;margin-bottom:20px'>📊</div>
        <div style='color:#F0F6FF;font-size:28px;font-weight:800;margin-bottom:10px'>FinSight CFO Dashboard</div>
        <div style='color:#8BA3C7;font-size:15px;margin-bottom:30px'>Upload your Excel P&L or try demo data to get started</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Process
variances, var_sum, kpis, kpi_cards, root_causes, alerts, alert_sum, forecasts, recs, exec_sum = process_data(summary, line_items)
health_score = kpis["health_scores"]["overall_score"]
health_color = "#10B981" if health_score >= 75 else "#F59E0B" if health_score >= 50 else "#EF4444"
health_label = "Strong" if health_score >= 75 else "Moderate" if health_score >= 50 else "Needs Attention"

# ── HEADER BAR ────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns([3,1,1,1])
with col1:
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:12px;margin-bottom:4px'>
        <div style='color:#F0F6FF;font-size:22px;font-weight:800'>{company_name}</div>
        <div style='color:#8BA3C7;font-size:14px'>· {period}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div class='fin-card' style='text-align:center;padding:12px'>
        <div style='color:#8BA3C7;font-size:10px;font-weight:700;text-transform:uppercase'>Health Score</div>
        <div style='color:{health_color};font-size:26px;font-weight:800;font-family:DM Mono'>{health_score:.0f}<span style='font-size:14px'>/100</span></div>
        <div style='color:{health_color};font-size:11px;font-weight:700'>{health_label}</div>
    </div>""", unsafe_allow_html=True)
with col3:
    crit = alert_sum["critical"]
    c = "#EF4444" if crit > 0 else "#F59E0B"
    st.markdown(f"""<div class='fin-card' style='text-align:center;padding:12px'>
        <div style='color:#8BA3C7;font-size:10px;font-weight:700;text-transform:uppercase'>Alerts</div>
        <div style='color:{c};font-size:26px;font-weight:800;font-family:DM Mono'>{alert_sum["total"]}</div>
        <div style='color:{c};font-size:11px'>{crit} Critical</div>
    </div>""", unsafe_allow_html=True)
with col4:
    fc_out = forecasts["insights"]["outlook"]
    fc_c = "#10B981" if fc_out=="Positive" else "#F59E0B" if fc_out=="Stable" else "#EF4444"
    st.markdown(f"""<div class='fin-card' style='text-align:center;padding:12px'>
        <div style='color:#8BA3C7;font-size:10px;font-weight:700;text-transform:uppercase'>3M Outlook</div>
        <div style='color:{fc_c};font-size:20px;font-weight:800'>{fc_out}</div>
        <div style='color:{fc_c};font-size:11px'>{forecasts["insights"]["projected_revenue_growth"]:+.1f}% rev growth</div>
    </div>""", unsafe_allow_html=True)

# ── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Overview", "📈 P&L Analysis", "🚨 Alerts & Root Cause", "🔮 Forecast", "💡 Action Plan"])

# ══════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════
with tab1:
    # KPI Cards
    st.markdown("<div class='section-title'>Key Performance Indicators</div>", unsafe_allow_html=True)
    cols = st.columns(3)
    for i, card in enumerate(kpi_cards):
        css = f"kpi-{card['status']}"
        with cols[i % 3]:
            st.markdown(f"""
            <div class='kpi-card {css}'>
                <div class='kpi-label'>{card['label']}</div>
                <div class='kpi-value' style='color:{"#10B981" if card["status"]=="good" else "#F59E0B" if card["status"]=="warning" else "#EF4444"}'>{card['value']}</div>
                <div style='color:#8BA3C7;font-size:11px'>Benchmark: {card['benchmark']}</div>
            </div>""", unsafe_allow_html=True)

    # Summary metrics
    st.markdown("<div class='section-title' style='margin-top:20px'>P&L Summary</div>", unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    metrics = [
        (c1, "Total Revenue",   fmt_money(summary["total_revenue"]),  "#06B6D4"),
        (c2, "Gross Profit",    fmt_money(summary["gross_profit"]),   "#10B981"),
        (c3, "EBIT",            fmt_money(summary["ebit"]),           "#3B82F6"),
        (c4, "Net Income",      fmt_money(summary["net_income"]),     "#10B981" if summary["net_income"]>0 else "#EF4444"),
    ]
    for col, label, val, color in metrics:
        with col:
            st.markdown(f"""<div class='fin-card'>
                <div style='color:#8BA3C7;font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:8px'>{label}</div>
                <div class='big-metric' style='color:{color}'>{val}</div>
            </div>""", unsafe_allow_html=True)

    # Revenue Chart
    st.markdown("<div class='section-title'>Revenue: Actual vs Budget</div>", unsafe_allow_html=True)
    df_monthly = pd.DataFrame(monthly_data)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_monthly["month"], y=df_monthly["actual"],
        name="Actual", line=dict(color="#06B6D4", width=2.5),
        fill="tozeroy", fillcolor="rgba(6,182,212,0.08)"))
    fig.add_trace(go.Scatter(x=df_monthly["month"], y=df_monthly["budget"],
        name="Budget", line=dict(color="#3B82F6", width=1.5, dash="dot")))
    fig.update_layout(
        plot_bgcolor="#111F38", paper_bgcolor="#111F38",
        font=dict(color="#8BA3C7", family="DM Sans"),
        legend=dict(bgcolor="#111F38", bordercolor="#1E3A5F"),
        xaxis=dict(gridcolor="#1E3A5F", showline=False),
        yaxis=dict(gridcolor="#1E3A5F", showline=False, tickformat="$,.0f"),
        margin=dict(l=0,r=0,t=10,b=0), height=250,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Executive Summary
    st.markdown("<div class='section-title'>Executive Summary</div>", unsafe_allow_html=True)
    st.markdown(f"""<div class='fin-card' style='background:linear-gradient(135deg,#0A1628,#0F2040);border-color:#3B82F640'>
        <div style='color:#8BA3C7;font-size:13px;line-height:1.8'>{exec_sum.replace(chr(10),"<br>")}</div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# TAB 2 — P&L ANALYSIS
# ══════════════════════════════════════════════════
with tab2:
    st.markdown("<div class='section-title'>P&L Waterfall — YTD</div>", unsafe_allow_html=True)
    s = summary
    pl_items = [
        ("Total Revenue", s["total_revenue"], True, "#06B6D4"),
        ("Cost of Goods Sold", -s["total_cogs"], False, "#EF4444"),
        ("Gross Profit", s["gross_profit"], True, "#10B981"),
        ("Operating Expenses", -s["total_opex"], False, "#F97316"),
        ("EBIT", s["ebit"], True, "#3B82F6"),
        ("Interest & Tax", -(s["ebit"]-s["net_income"]), False, "#8B5CF6"),
        ("Net Income", s["net_income"], True, "#10B981" if s["net_income"]>0 else "#EF4444"),
    ]
    max_val = max(abs(v) for _,v,_,_ in pl_items)
    for label, val, is_total, color in pl_items:
        bar_pct = abs(val)/max_val * 100 if max_val else 0
        bg = "#1A2F52" if is_total else "transparent"
        border = f"border-left:3px solid {color}" if is_total else "border-left:3px solid transparent"
        st.markdown(f"""
        <div style='display:flex;align-items:center;gap:12px;background:{bg};
                    border-radius:8px;padding:{"10px 12px" if is_total else "6px 12px"};
                    margin-bottom:4px;{border}'>
            <div style='flex:0 0 180px;color:{"#F0F6FF" if is_total else "#8BA3C7"};
                        font-size:13px;font-weight:{"700" if is_total else "500"}'>{label}</div>
            <div style='flex:1;height:8px;background:#1E3A5F;border-radius:4px;overflow:hidden'>
                <div style='width:{bar_pct}%;height:100%;background:{color};
                            border-radius:4px;opacity:{"1" if is_total else "0.6"}'></div>
            </div>
            <div style='flex:0 0 110px;text-align:right;color:{color};
                        font-size:{"15px" if is_total else "13px"};font-weight:{"800" if is_total else "600"};
                        font-family:DM Mono'>{fmt_money(val)}</div>
        </div>""", unsafe_allow_html=True)

    # Variance Table
    st.markdown("<div class='section-title' style='margin-top:20px'>Budget vs Actual — Variance Analysis</div>", unsafe_allow_html=True)
    var_rows = []
    for item in line_items:
        ytd = item.get("ytd_variance")
        if not ytd: continue
        var_rows.append({
            "Line Item": item["name"],
            "Category":  item.get("category",""),
            "Actual":    fmt_money(item.get("ytd_actual",0)),
            "Budget":    fmt_money(item.get("ytd_budget",0)),
            "Variance":  f"{ytd['variance_pct']:+.1f}%",
            "Status":    "✅ " + ytd["status"] if ytd["favorable"] else "⚠️ " + ytd["status"],
        })
    if var_rows:
        df_var = pd.DataFrame(var_rows)
        st.dataframe(df_var, use_container_width=True, hide_index=True,
            column_config={"Status": st.column_config.TextColumn("Status", width="medium")})

    # Cost Breakdown Pie
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='section-title'>Cost Breakdown</div>", unsafe_allow_html=True)
        pie_fig = go.Figure(go.Pie(
            labels=["COGS","OpEx","Net Income"],
            values=[s["total_cogs"], s["total_opex"], max(s["net_income"],0)],
            marker_colors=["#EF4444","#F97316","#10B981"],
            hole=0.55, textfont=dict(color="#F0F6FF"),
        ))
        pie_fig.update_layout(
            plot_bgcolor="#111F38", paper_bgcolor="#111F38",
            font=dict(color="#8BA3C7"), legend=dict(bgcolor="#111F38"),
            margin=dict(l=0,r=0,t=10,b=0), height=220,
        )
        st.plotly_chart(pie_fig, use_container_width=True)
    with col2:
        st.markdown("<div class='section-title'>Monthly Revenue vs Gross Profit</div>", unsafe_allow_html=True)
        bar_fig = go.Figure()
        bar_fig.add_trace(go.Bar(x=df_monthly["month"], y=df_monthly["actual"],
            name="Revenue", marker_color="#06B6D4", opacity=0.85))
        bar_fig.add_trace(go.Bar(x=df_monthly["month"],
            y=[v * s["gross_margin"] for v in df_monthly["actual"]],
            name="Gross Profit", marker_color="#10B981", opacity=0.85))
        bar_fig.update_layout(
            plot_bgcolor="#111F38", paper_bgcolor="#111F38",
            font=dict(color="#8BA3C7"), barmode="group",
            legend=dict(bgcolor="#111F38"), margin=dict(l=0,r=0,t=10,b=0), height=220,
            xaxis=dict(gridcolor="#1E3A5F"), yaxis=dict(gridcolor="#1E3A5F", tickformat="$,.0f"),
        )
        st.plotly_chart(bar_fig, use_container_width=True)

# ══════════════════════════════════════════════════
# TAB 3 — ALERTS & ROOT CAUSE
# ══════════════════════════════════════════════════
with tab3:
    col1, col2 = st.columns([1,2])
    with col1:
        st.markdown("<div class='section-title'>Alert Summary</div>", unsafe_allow_html=True)
        for label, count, color in [
            ("Critical", alert_sum["critical"], "#EF4444"),
            ("High",     alert_sum["high"],     "#F97316"),
            ("Total",    alert_sum["total"],     "#3B82F6"),
        ]:
            st.markdown(f"""<div style='background:{color}15;border:1px solid {color}40;
                border-radius:10px;padding:12px 20px;text-align:center;margin-bottom:10px'>
                <div style='color:{color};font-size:28px;font-weight:800;font-family:DM Mono'>{count}</div>
                <div style='color:#8BA3C7;font-size:12px;font-weight:600'>{label}</div>
            </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='section-title'>Active Alerts</div>", unsafe_allow_html=True)
        for alert in alerts:
            css = f"alert-{alert['severity'].lower()}"
            badge_css = f"badge-{alert['severity'].lower()}"
            title_color = "#FCA5A5" if alert["severity"]=="Critical" else "#FCD34D" if alert["severity"]=="High" else "#FDE68A"
            st.markdown(f"""<div class='{css}'>
                <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px'>
                    <div class='alert-title' style='color:{title_color}'>{alert.get("icon","⚠️")} {alert["title"]}</div>
                    <span class='badge {badge_css}'>{alert["severity"]}</span>
                </div>
                <div class='alert-msg'>{alert["message"]}</div>
            </div>""", unsafe_allow_html=True)

    # Root Causes
    st.markdown("<div class='section-title' style='margin-top:20px'>Root Cause Analysis</div>", unsafe_allow_html=True)
    for rc in root_causes:
        colors = {"Critical":("#3B0A0A","#EF4444","#FCA5A5"),
                  "High":    ("#2D1B00","#F97316","#FCD34D"),
                  "Medium":  ("#1A2200","#EAB308","#FDE68A")}
        bg, border, text = colors.get(rc["severity"], ("#111F38","#1E3A5F","#F0F6FF"))
        st.markdown(f"""<div style='background:{bg};border:1px solid {border};
            border-radius:10px;padding:16px;margin-bottom:12px'>
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
                <span style='font-size:20px'>{rc["icon"]}</span>
                <span style='color:{text};font-size:14px;font-weight:700'>{rc["title"]}</span>
                <span style='margin-left:auto;background:{border};color:#fff;
                    font-size:10px;font-weight:800;border-radius:4px;padding:2px 7px'>{rc["severity"]}</span>
            </div>
            <p style='color:#8BA3C7;font-size:13px;margin:0 0 8px;line-height:1.6'>{rc["root_cause"]}</p>
            <div style='background:#0F1E3C;border-radius:6px;padding:8px 12px;
                color:#F59E0B;font-size:12px;font-weight:600'>📌 Impact: {rc["impact"]}</div>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# TAB 4 — FORECAST
# ══════════════════════════════════════════════════
with tab4:
    fc_table = forecasts["table"]
    fc_insights = forecasts["insights"]

    # Forecast cards
    cols = st.columns(3)
    for i, row in enumerate(fc_table):
        with cols[i]:
            st.markdown(f"""<div class='fin-card fin-card-accent-purple'>
                <div style='color:#8BA3C7;font-size:11px;font-weight:700;text-transform:uppercase;margin-bottom:12px'>{row["month"]}</div>
                <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                    <span style='color:#8BA3C7;font-size:12px'>Revenue</span>
                    <span style='color:#06B6D4;font-size:15px;font-weight:700;font-family:DM Mono'>{fmt_money(row["revenue"])}</span>
                </div>
                <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                    <span style='color:#8BA3C7;font-size:12px'>Gross Profit</span>
                    <span style='color:#10B981;font-size:15px;font-weight:700;font-family:DM Mono'>{fmt_money(row["gross_profit"])}</span>
                </div>
                <div style='display:flex;justify-content:space-between'>
                    <span style='color:#8BA3C7;font-size:12px'>Net Income</span>
                    <span style='color:#3B82F6;font-size:15px;font-weight:700;font-family:DM Mono'>{fmt_money(row["net_income"])}</span>
                </div>
            </div>""", unsafe_allow_html=True)

    # Combined Historical + Forecast Chart
    st.markdown("<div class='section-title'>Revenue — Historical + 3-Month Forecast</div>", unsafe_allow_html=True)
    hist_months = [m["month"] for m in monthly_data[-6:]]
    hist_vals   = [m["actual"] for m in monthly_data[-6:]]
    fc_months   = [r["month"] for r in fc_table]
    fc_vals     = [r["revenue"] for r in fc_table]

    fig_fc = go.Figure()
    fig_fc.add_trace(go.Scatter(x=hist_months, y=hist_vals, name="Historical",
        line=dict(color="#06B6D4", width=2.5), fill="tozeroy", fillcolor="rgba(6,182,212,0.08)"))
    fig_fc.add_trace(go.Scatter(x=fc_months, y=fc_vals, name="Forecast",
        line=dict(color="#8B5CF6", width=2.5, dash="dot"),
        mode="lines+markers", marker=dict(size=8, color="#8B5CF6", symbol="circle")))
    fig_fc.update_layout(
        plot_bgcolor="#111F38", paper_bgcolor="#111F38",
        font=dict(color="#8BA3C7", family="DM Sans"),
        legend=dict(bgcolor="#111F38", bordercolor="#1E3A5F"),
        xaxis=dict(gridcolor="#1E3A5F"), yaxis=dict(gridcolor="#1E3A5F", tickformat="$,.0f"),
        margin=dict(l=0,r=0,t=10,b=0), height=260,
    )
    st.plotly_chart(fig_fc, use_container_width=True)

    # Outlook summary
    out_color = "#10B981" if fc_insights["outlook"]=="Positive" else "#F59E0B" if fc_insights["outlook"]=="Stable" else "#EF4444"
    c1,c2,c3 = st.columns(3)
    for col, label, val, color in [
        (c1, "Revenue Growth",  f"{fc_insights['projected_revenue_growth']:+.1f}%", "#10B981" if fc_insights['projected_revenue_growth']>0 else "#EF4444"),
        (c2, "Net Margin",      f"{fc_insights['projected_net_margin']:.1f}%",      "#10B981"),
        (c3, "Outlook",         fc_insights["outlook"],                              out_color),
    ]:
        with col:
            st.markdown(f"""<div class='fin-card' style='text-align:center'>
                <div style='color:{color};font-size:24px;font-weight:800;font-family:DM Mono'>{val}</div>
                <div style='color:#8BA3C7;font-size:12px;font-weight:600;margin-top:6px'>{label}</div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# TAB 5 — ACTION PLAN
# ══════════════════════════════════════════════════
with tab5:
    priority_colors = {"Critical":"#EF4444","High":"#F97316","Medium":"#EAB308","Low":"#10B981"}
    for rec in recs:
        pc = priority_colors.get(rec["priority"], "#8BA3C7")
        actions_html = "".join([
            f"<div class='rec-action'><div class='rec-num'>{j+1}</div><div>{a}</div></div>"
            for j, a in enumerate(rec["actions"])
        ])
        st.markdown(f"""<div class='rec-card' style='border-left:4px solid {pc}'>
            <div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>
                <span style='background:{pc}20;color:{pc};font-size:10px;font-weight:800;
                    border-radius:4px;padding:2px 7px;letter-spacing:0.06em'>{rec["priority"]}</span>
                <span style='color:#8BA3C7;font-size:11px'>{rec["timeline"]} · {rec["owner"]}</span>
            </div>
            <div style='color:#F0F6FF;font-size:14px;font-weight:700;margin-bottom:10px'>{rec["title"]}</div>
            <div style='color:#8BA3C7;font-size:12px;margin-bottom:12px'>
                <strong style='color:#F59E0B'>Problem:</strong> {rec["problem"]}
            </div>
            <div style='margin-bottom:12px'>{actions_html}</div>
            <div style='background:#0F2040;border:1px solid #10B98140;border-radius:8px;padding:8px 12px'>
                <span style='color:#10B981;font-size:11px;font-weight:700'>Expected Impact: </span>
                <span style='color:#8BA3C7;font-size:12px'>{rec["expected_impact"]}</span>
            </div>
        </div>""", unsafe_allow_html=True)