import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from mapping import map_file
from variance import calculate_all_variances, variance_summary
from kpi import calculate_kpis, format_kpi_card
from root_cause import analyze_root_causes
from alerts import generate_alerts, get_alert_summary
from forecast import build_forecast_from_summary
from recommendations import generate_recommendations, generate_executive_summary
from file_classifier import classify_file
from analyzers import analyze_file

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinSight CFO Dashboard",
    page_icon="📊",
    layout="wide"
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700;800&family=DM+Mono:wght@400;600&display=swap');
*, body, .stApp { font-family: 'DM Sans', sans-serif !important; }
.stApp { background: #080F1E !important; color: #F0F6FF !important; }
section[data-testid="stSidebar"] { background: #0F1E3C !important; border-right: 1px solid #1E3A5F; }
.block-container { padding: 1.5rem 2rem !important; max-width: 1400px; }
.fin-card { background:#111F38; border:1px solid #1E3A5F; border-radius:12px; padding:18px 20px; margin-bottom:16px; }
.fin-card-accent-purple { border-top:3px solid #8B5CF6; }
.kpi-card { background:linear-gradient(135deg,#111F38,#1A2F52); border:1px solid #1E3A5F; border-radius:12px; padding:16px 18px; }
.kpi-label { color:#8BA3C7; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.1em; }
.kpi-value { font-family:'DM Mono',monospace; font-size:28px; font-weight:800; line-height:1; margin:8px 0 4px; }
.alert-critical { background:#3B0A0A; border:1px solid #EF4444; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.alert-high     { background:#2D1B00; border:1px solid #F97316; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.alert-medium   { background:#1A2200; border:1px solid #EAB308; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.badge { display:inline-block; border-radius:4px; padding:2px 7px; font-size:10px; font-weight:800; }
.badge-critical { background:#EF4444; color:#fff; }
.badge-high     { background:#F97316; color:#fff; }
.badge-medium   { background:#EAB308; color:#000; }
.big-metric { font-family:'DM Mono',monospace; font-size:32px; font-weight:800; }
.section-title { display:flex; align-items:center; gap:10px; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#F0F6FF; margin-bottom:14px; }
.section-title::before { content:''; display:block; width:3px; height:18px; background:#06B6D4; border-radius:2px; }
.rec-card { background:#111F38; border:1px solid #1E3A5F; border-radius:10px; padding:16px; margin-bottom:12px; }
.rec-action { display:flex; gap:8px; align-items:flex-start; margin-bottom:6px; font-size:13px; color:#F0F6FF; }
.rec-num { background:#1E5CC8; color:#fff; border-radius:50%; width:20px; height:20px; font-size:10px; font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
#MainMenu, footer, header { visibility:hidden; }
.stDeployButton { display:none; }
div[data-testid="stToolbar"] { display:none; }
</style>
""", unsafe_allow_html=True)

# ── HELPERS ──────────────────────────────────────────────────────────────────
def fmt_money(v):
    if v is None: return "—"
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v/1e6:.2f}M" if v>=1e6 else f"{s}${v/1e3:.0f}K" if v>=1e3 else f"{s}${v:.0f}"

def fmt_pct(v): return f"{v*100:.1f}%" if v else "0.0%"

# ── DEMO DATA ─────────────────────────────────────────────────────────────────
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
        {"month":"Jan","actual":1115000,"budget":1040000},
        {"month":"Feb","actual":1152000,"budget":1112000},
        {"month":"Mar","actual":1208000,"budget":1175000},
        {"month":"Apr","actual":1191000,"budget":1180000},
        {"month":"May","actual":1250000,"budget":1243000},
        {"month":"Jun","actual":1282000,"budget":1265000},
        {"month":"Jul","actual":1314000,"budget":1297000},
        {"month":"Aug","actual":1346000,"budget":1329000},
        {"month":"Sep","actual":1298000,"budget":1322000},
        {"month":"Oct","actual":1350000,"budget":1385000},
        {"month":"Nov","actual":1393000,"budget":1418000},
        {"month":"Dec","actual":1462000,"budget":1470000},
    ]
}

# ── PROCESS P&L ───────────────────────────────────────────────────────────────
def process_pl_data(summary, line_items):
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

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:20px 0 10px'>
        <div style='background:linear-gradient(135deg,#1E5CC8,#06B6D4);width:48px;height:48px;
                    border-radius:12px;display:inline-flex;align-items:center;
                    justify-content:center;font-size:24px;'>📊</div>
        <div style='color:#F0F6FF;font-size:20px;font-weight:800;margin-top:8px'>FinSight</div>
        <div style='color:#8BA3C7;font-size:11px;letter-spacing:0.12em;
                    text-transform:uppercase'>CFO Intelligence Platform</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    uploaded = st.file_uploader(
        "📂 Upload Financial File",
        type=["xlsx","xls"],
        label_visibility="collapsed"
    )
    use_demo = st.button("🎯 Try Demo Data (NileTech)", use_container_width=True)
    st.markdown("---")
    st.markdown("<div style='color:#8BA3C7;font-size:11px;font-weight:700'>PIPELINE</div>",
                unsafe_allow_html=True)
    for step in ["🗂️ Classify File","📊 Map P&L","📉 Variances",
                 "🎯 KPIs","🔍 Root Cause","🚨 Alerts","🔮 Forecast",
                 "💡 Recommendations","🏗️ Budget Builder"]:
        st.markdown(
            f"<div style='color:#8BA3C7;font-size:12px;padding:3px 0'>→ {step}</div>",
            unsafe_allow_html=True)

# ── STATE ─────────────────────────────────────────────────────────────────────
data_loaded  = False
file_type    = None
summary      = None
line_items   = None
monthly_data = None
company_name = None
period       = None
analysis     = None
classifier   = None

# ── CASE 1: Demo ──────────────────────────────────────────────────────────────
if use_demo:
    st.session_state.clear()
    st.session_state["mode"] = "demo"

if st.session_state.get("mode") == "demo":
    summary      = DEMO["summary"]
    line_items   = DEMO["line_items"]
    monthly_data = DEMO["monthly"]
    company_name = "NileTech Solutions"
    period       = "FY 2024"
    file_type    = "P&L"
    data_loaded  = True

# ── CASE 2: Upload ────────────────────────────────────────────────────────────
elif uploaded:
    file_key = uploaded.name + str(uploaded.size)
    if st.session_state.get("file_key") != file_key:
        with st.spinner("🔍 Classifying and analyzing file..."):
            import tempfile, os, gc
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            cl = classify_file(tmp_path)
            an = analyze_file(tmp_path, cl)
            gc.collect()
            try: os.unlink(tmp_path)
            except: pass
            st.session_state["file_key"]   = file_key
            st.session_state["mode"]       = "file"
            st.session_state["classifier"] = cl
            st.session_state["analysis"]   = an
            st.session_state["company"]    = uploaded.name.replace(".xlsx","").replace(".xls","")

    classifier   = st.session_state["classifier"]
    analysis     = st.session_state["analysis"]
    company_name = st.session_state["company"]
    file_type    = analysis.get("type","UNKNOWN")
    period       = "YTD"

    if file_type == "P&L" and not analysis.get("error"):
        summary      = analysis.get("summary", DEMO["summary"])
        line_items   = analysis.get("line_items", DEMO["line_items"])
        monthly_data = DEMO["monthly"]
    else:
        summary = line_items = monthly_data = None

    data_loaded = True

# ── WELCOME SCREEN ────────────────────────────────────────────────────────────
if not data_loaded:
    st.markdown("""
    <div style='display:flex;flex-direction:column;align-items:center;
                justify-content:center;min-height:70vh;text-align:center'>
        <div style='font-size:64px;margin-bottom:20px'>📊</div>
        <div style='color:#F0F6FF;font-size:28px;font-weight:800;margin-bottom:10px'>
            FinSight CFO Dashboard</div>
        <div style='color:#8BA3C7;font-size:15px;margin-bottom:30px'>
            Upload any financial Excel file or try demo data</div>
        <div style='display:flex;gap:12px;flex-wrap:wrap;justify-content:center'>
            <span style='background:#111F38;border:1px solid #1E3A5F;color:#8BA3C7;
                         border-radius:8px;padding:6px 14px;font-size:12px'>📊 P&L</span>
            <span style='background:#111F38;border:1px solid #1E3A5F;color:#8BA3C7;
                         border-radius:8px;padding:6px 14px;font-size:12px'>🏦 Balance Sheet</span>
            <span style='background:#111F38;border:1px solid #1E3A5F;color:#8BA3C7;
                         border-radius:8px;padding:6px 14px;font-size:12px'>🏗️ Fixed Assets</span>
            <span style='background:#111F38;border:1px solid #1E3A5F;color:#8BA3C7;
                         border-radius:8px;padding:6px 14px;font-size:12px'>👥 Payroll</span>
            <span style='background:#111F38;border:1px solid #1E3A5F;color:#8BA3C7;
                         border-radius:8px;padding:6px 14px;font-size:12px'>💸 Cash Flow</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

# File type badge
if classifier:
    cl = classifier
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:10px;margin-bottom:16px;
                background:#111F38;border:1px solid {cl["color"]}40;
                border-left:4px solid {cl["color"]};border-radius:10px;padding:12px 16px'>
        <span style='font-size:24px'>{cl["icon"]}</span>
        <div>
            <div style='color:{cl["color"]};font-size:14px;font-weight:800'>{cl["label"]}</div>
            <div style='color:#8BA3C7;font-size:12px'>
                Confidence: {cl["confidence"]:.0f}% &nbsp;·&nbsp;
                Sheets: {", ".join(cl.get("sheet_names",[]))}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── TABS — دايماً ظاهرين ─────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview", "📈 P&L Analysis",
    "🚨 Alerts & Root Cause", "🔮 Forecast",
    "💡 Action Plan", "🏗️ Budget Builder"
])

# ══════════════════════════════════════════════════════════════════════════════
# P&L CONTENT
# ══════════════════════════════════════════════════════════════════════════════
if file_type == "P&L" and summary and line_items:
    variances, var_sum, kpis, kpi_cards, root_causes, alerts, alert_sum, forecasts, recs, exec_sum = \
        process_pl_data(summary, line_items)

    health_score = kpis["health_scores"]["overall_score"]
    health_color = "#10B981" if health_score>=75 else "#F59E0B" if health_score>=50 else "#EF4444"
    health_label = "Strong" if health_score>=75 else "Moderate" if health_score>=50 else "Needs Attention"
    df_monthly   = pd.DataFrame(monthly_data)

    with tab1:
        col1,col2,col3,col4 = st.columns([3,1,1,1])
        with col1:
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:12px;margin-bottom:4px'>
                <div style='color:#F0F6FF;font-size:22px;font-weight:800'>{company_name}</div>
                <div style='color:#8BA3C7;font-size:14px'>· {period}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown(f"""<div class='fin-card' style='text-align:center;padding:12px'>
                <div style='color:#8BA3C7;font-size:10px;font-weight:700;text-transform:uppercase'>Health Score</div>
                <div style='color:{health_color};font-size:26px;font-weight:800;font-family:DM Mono'>
                    {health_score:.0f}<span style='font-size:14px'>/100</span></div>
                <div style='color:{health_color};font-size:11px;font-weight:700'>{health_label}</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            crit = alert_sum["critical"]
            c = "#EF4444" if crit>0 else "#F59E0B"
            st.markdown(f"""<div class='fin-card' style='text-align:center;padding:12px'>
                <div style='color:#8BA3C7;font-size:10px;font-weight:700;text-transform:uppercase'>Alerts</div>
                <div style='color:{c};font-size:26px;font-weight:800;font-family:DM Mono'>{alert_sum["total"]}</div>
                <div style='color:{c};font-size:11px'>{crit} Critical</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            fc_out = forecasts["insights"]["outlook"]
            fc_c   = "#10B981" if fc_out=="Positive" else "#F59E0B" if fc_out=="Stable" else "#EF4444"
            st.markdown(f"""<div class='fin-card' style='text-align:center;padding:12px'>
                <div style='color:#8BA3C7;font-size:10px;font-weight:700;text-transform:uppercase'>3M Outlook</div>
                <div style='color:{fc_c};font-size:20px;font-weight:800'>{fc_out}</div>
                <div style='color:{fc_c};font-size:11px'>{forecasts["insights"]["projected_revenue_growth"]:+.1f}% rev growth</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:16px'>Key Performance Indicators</div>",
                    unsafe_allow_html=True)
        cols = st.columns(3)
        for i, card in enumerate(kpi_cards):
            color = {"good":"#10B981","warning":"#F59E0B","critical":"#EF4444"}.get(card["status"],"#8BA3C7")
            with cols[i%3]:
                st.markdown(f"""
                <div class='kpi-card' style='border-top:2px solid {color}'>
                    <div class='kpi-label'>{card["label"]}</div>
                    <div class='kpi-value' style='color:{color}'>{card["value"]}</div>
                    <div style='color:#8BA3C7;font-size:11px'>Benchmark: {card["benchmark"]}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>P&L Summary</div>",
                    unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        for col,label,val,color in [
            (c1,"Total Revenue", fmt_money(summary["total_revenue"]), "#06B6D4"),
            (c2,"Gross Profit",  fmt_money(summary["gross_profit"]),  "#10B981"),
            (c3,"EBIT",          fmt_money(summary["ebit"]),          "#3B82F6"),
            (c4,"Net Income",    fmt_money(summary["net_income"]),
             "#10B981" if summary["net_income"]>0 else "#EF4444"),
        ]:
            with col:
                st.markdown(f"""<div class='fin-card'>
                    <div style='color:#8BA3C7;font-size:11px;font-weight:700;
                                text-transform:uppercase;margin-bottom:8px'>{label}</div>
                    <div class='big-metric' style='color:{color}'>{val}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Revenue: Actual vs Budget</div>",
                    unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_monthly["month"],y=df_monthly["actual"],
            name="Actual",line=dict(color="#06B6D4",width=2.5),
            fill="tozeroy",fillcolor="rgba(6,182,212,0.08)"))
        fig.add_trace(go.Scatter(x=df_monthly["month"],y=df_monthly["budget"],
            name="Budget",line=dict(color="#3B82F6",width=1.5,dash="dot")))
        fig.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
            font=dict(color="#8BA3C7",family="DM Sans"),
            legend=dict(bgcolor="#111F38",bordercolor="#1E3A5F"),
            xaxis=dict(gridcolor="#1E3A5F",showline=False),
            yaxis=dict(gridcolor="#1E3A5F",showline=False,tickformat="$,.0f"),
            margin=dict(l=0,r=0,t=10,b=0),height=250)
        st.plotly_chart(fig,use_container_width=True)

        st.markdown("<div class='section-title'>Executive Summary</div>",
                    unsafe_allow_html=True)
        st.markdown(f"""<div class='fin-card'
            style='background:linear-gradient(135deg,#0A1628,#0F2040);border-color:#3B82F640'>
            <div style='color:#8BA3C7;font-size:13px;line-height:1.8'>
                {exec_sum.replace(chr(10),"<br>")}
            </div>
        </div>""", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='section-title'>P&L Waterfall — YTD</div>",
                    unsafe_allow_html=True)
        s = summary
        pl_items = [
            ("Total Revenue",      s["total_revenue"],           True,  "#06B6D4"),
            ("Cost of Goods Sold", -s["total_cogs"],             False, "#EF4444"),
            ("Gross Profit",       s["gross_profit"],            True,  "#10B981"),
            ("Operating Expenses", -s["total_opex"],             False, "#F97316"),
            ("EBIT",               s["ebit"],                    True,  "#3B82F6"),
            ("Interest & Tax",     -(s["ebit"]-s["net_income"]), False, "#8B5CF6"),
            ("Net Income",         s["net_income"],              True,
             "#10B981" if s["net_income"]>0 else "#EF4444"),
        ]
        max_val = max(abs(v) for _,v,_,_ in pl_items)
        for label,val,is_total,color in pl_items:
            bar_pct = abs(val)/max_val*100 if max_val else 0
            bg     = "#1A2F52" if is_total else "transparent"
            border = f"border-left:3px solid {color}" if is_total else "border-left:3px solid transparent"
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:12px;background:{bg};
                        border-radius:8px;padding:{"10px 12px" if is_total else "6px 12px"};
                        margin-bottom:4px;{border}'>
                <div style='flex:0 0 180px;color:{"#F0F6FF" if is_total else "#8BA3C7"};
                            font-size:13px;font-weight:{"700" if is_total else "500"}'>{label}</div>
                <div style='flex:1;height:8px;background:#1E3A5F;border-radius:4px;overflow:hidden'>
                    <div style='width:{bar_pct}%;height:100%;background:{color};border-radius:4px;
                                opacity:{"1" if is_total else "0.6"}'></div>
                </div>
                <div style='flex:0 0 110px;text-align:right;color:{color};
                            font-size:{"15px" if is_total else "13px"};
                            font-weight:{"800" if is_total else "600"};
                            font-family:DM Mono'>{fmt_money(val)}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>Budget vs Actual</div>",
                    unsafe_allow_html=True)
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
                "Status":    ("✅ " if ytd["favorable"] else "⚠️ ")+ytd["status"],
            })
        if var_rows:
            st.dataframe(pd.DataFrame(var_rows),use_container_width=True,hide_index=True)

        col1,col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-title'>Cost Breakdown</div>",
                        unsafe_allow_html=True)
            pie = go.Figure(go.Pie(
                labels=["COGS","OpEx","Net Income"],
                values=[s["total_cogs"],s["total_opex"],max(s["net_income"],0)],
                marker_colors=["#EF4444","#F97316","#10B981"],
                hole=0.55,textfont=dict(color="#F0F6FF")))
            pie.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
                font=dict(color="#8BA3C7"),legend=dict(bgcolor="#111F38"),
                margin=dict(l=0,r=0,t=10,b=0),height=220)
            st.plotly_chart(pie,use_container_width=True)
        with col2:
            st.markdown("<div class='section-title'>Monthly Revenue vs Gross Profit</div>",
                        unsafe_allow_html=True)
            bar = go.Figure()
            bar.add_trace(go.Bar(x=df_monthly["month"],y=df_monthly["actual"],
                name="Revenue",marker_color="#06B6D4",opacity=0.85))
            bar.add_trace(go.Bar(x=df_monthly["month"],
                y=[v*s["gross_margin"] for v in df_monthly["actual"]],
                name="Gross Profit",marker_color="#10B981",opacity=0.85))
            bar.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
                font=dict(color="#8BA3C7"),barmode="group",
                legend=dict(bgcolor="#111F38"),margin=dict(l=0,r=0,t=10,b=0),height=220,
                xaxis=dict(gridcolor="#1E3A5F"),
                yaxis=dict(gridcolor="#1E3A5F",tickformat="$,.0f"))
            st.plotly_chart(bar,use_container_width=True)

    with tab3:
        col1,col2 = st.columns([1,2])
        with col1:
            st.markdown("<div class='section-title'>Alert Summary</div>",
                        unsafe_allow_html=True)
            for label,count,color in [
                ("Critical",alert_sum["critical"],"#EF4444"),
                ("High",    alert_sum["high"],    "#F97316"),
                ("Total",   alert_sum["total"],   "#3B82F6"),
            ]:
                st.markdown(f"""
                <div style='background:{color}15;border:1px solid {color}40;
                    border-radius:10px;padding:12px 20px;text-align:center;margin-bottom:10px'>
                    <div style='color:{color};font-size:28px;font-weight:800;font-family:DM Mono'>
                        {count}</div>
                    <div style='color:#8BA3C7;font-size:12px;font-weight:600'>{label}</div>
                </div>""", unsafe_allow_html=True)
        with col2:
            st.markdown("<div class='section-title'>Active Alerts</div>",
                        unsafe_allow_html=True)
            for alert in alerts:
                sev = alert["severity"].lower()
                tc  = {"critical":"#FCA5A5","high":"#FCD34D","medium":"#FDE68A"}.get(sev,"#F0F6FF")
                st.markdown(f"""
                <div class='alert-{sev}'>
                    <div style='display:flex;justify-content:space-between;
                                align-items:center;margin-bottom:4px'>
                        <div style='color:{tc};font-weight:700;font-size:13px'>
                            {alert.get("icon","⚠️")} {alert["title"]}</div>
                        <span class='badge badge-{sev}'>{alert["severity"]}</span>
                    </div>
                    <div style='color:#8BA3C7;font-size:12px;line-height:1.5'>
                        {alert["message"]}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>Root Cause Analysis</div>",
                    unsafe_allow_html=True)
        for rc in root_causes:
            bg,border,text = {
                "Critical":("#3B0A0A","#EF4444","#FCA5A5"),
                "High":    ("#2D1B00","#F97316","#FCD34D"),
                "Medium":  ("#1A2200","#EAB308","#FDE68A"),
            }.get(rc["severity"],("#111F38","#1E3A5F","#F0F6FF"))
            st.markdown(f"""
            <div style='background:{bg};border:1px solid {border};
                        border-radius:10px;padding:16px;margin-bottom:12px'>
                <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
                    <span style='font-size:20px'>{rc["icon"]}</span>
                    <span style='color:{text};font-size:14px;font-weight:700'>{rc["title"]}</span>
                    <span style='margin-left:auto;background:{border};color:#fff;
                        font-size:10px;font-weight:800;border-radius:4px;
                        padding:2px 7px'>{rc["severity"]}</span>
                </div>
                <p style='color:#8BA3C7;font-size:13px;margin:0 0 8px;line-height:1.6'>
                    {rc["root_cause"]}</p>
                <div style='background:#0F1E3C;border-radius:6px;padding:8px 12px;
                    color:#F59E0B;font-size:12px;font-weight:600'>
                    📌 Impact: {rc["impact"]}</div>
            </div>""", unsafe_allow_html=True)

    with tab4:
        fc_table    = forecasts["table"]
        fc_insights = forecasts["insights"]
        cols = st.columns(3)
        for i,row in enumerate(fc_table):
            with cols[i]:
                st.markdown(f"""<div class='fin-card fin-card-accent-purple'>
                    <div style='color:#8BA3C7;font-size:11px;font-weight:700;
                                text-transform:uppercase;margin-bottom:12px'>{row["month"]}</div>
                    <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                        <span style='color:#8BA3C7;font-size:12px'>Revenue</span>
                        <span style='color:#06B6D4;font-size:15px;font-weight:700;
                                     font-family:DM Mono'>{fmt_money(row["revenue"])}</span>
                    </div>
                    <div style='display:flex;justify-content:space-between;margin-bottom:6px'>
                        <span style='color:#8BA3C7;font-size:12px'>Gross Profit</span>
                        <span style='color:#10B981;font-size:15px;font-weight:700;
                                     font-family:DM Mono'>{fmt_money(row["gross_profit"])}</span>
                    </div>
                    <div style='display:flex;justify-content:space-between'>
                        <span style='color:#8BA3C7;font-size:12px'>Net Income</span>
                        <span style='color:#3B82F6;font-size:15px;font-weight:700;
                                     font-family:DM Mono'>{fmt_money(row["net_income"])}</span>
                    </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Revenue — Historical + 3-Month Forecast</div>",
                    unsafe_allow_html=True)
        hist_months = [m["month"] for m in monthly_data[-6:]]
        hist_vals   = [m["actual"] for m in monthly_data[-6:]]
        fc_months   = [r["month"] for r in fc_table]
        fc_vals     = [r["revenue"] for r in fc_table]
        fig_fc = go.Figure()
        fig_fc.add_trace(go.Scatter(x=hist_months,y=hist_vals,name="Historical",
            line=dict(color="#06B6D4",width=2.5),
            fill="tozeroy",fillcolor="rgba(6,182,212,0.08)"))
        fig_fc.add_trace(go.Scatter(x=fc_months,y=fc_vals,name="Forecast",
            line=dict(color="#8B5CF6",width=2.5,dash="dot"),
            mode="lines+markers",marker=dict(size=8,color="#8B5CF6",symbol="circle")))
        fig_fc.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
            font=dict(color="#8BA3C7",family="DM Sans"),
            legend=dict(bgcolor="#111F38",bordercolor="#1E3A5F"),
            xaxis=dict(gridcolor="#1E3A5F"),
            yaxis=dict(gridcolor="#1E3A5F",tickformat="$,.0f"),
            margin=dict(l=0,r=0,t=10,b=0),height=260)
        st.plotly_chart(fig_fc,use_container_width=True)

        out_color = "#10B981" if fc_insights["outlook"]=="Positive" else \
                    "#F59E0B" if fc_insights["outlook"]=="Stable" else "#EF4444"
        c1,c2,c3 = st.columns(3)
        for col,label,val,color in [
            (c1,"Revenue Growth",
             f"{fc_insights['projected_revenue_growth']:+.1f}%",
             "#10B981" if fc_insights['projected_revenue_growth']>0 else "#EF4444"),
            (c2,"Net Margin",f"{fc_insights['projected_net_margin']:.1f}%","#10B981"),
            (c3,"Outlook",fc_insights["outlook"],out_color),
        ]:
            with col:
                st.markdown(f"""<div class='fin-card' style='text-align:center'>
                    <div style='color:{color};font-size:24px;font-weight:800;
                                font-family:DM Mono'>{val}</div>
                    <div style='color:#8BA3C7;font-size:12px;font-weight:600;
                                margin-top:6px'>{label}</div>
                </div>""", unsafe_allow_html=True)

    with tab5:
        priority_colors = {"Critical":"#EF4444","High":"#F97316",
                           "Medium":"#EAB308","Low":"#10B981"}
        for rec in recs:
            pc = priority_colors.get(rec["priority"],"#8BA3C7")
            actions_html = "".join([
                f"<div class='rec-action'><div class='rec-num'>{j+1}</div><div>{a}</div></div>"
                for j,a in enumerate(rec["actions"])
            ])
            st.markdown(f"""<div class='rec-card' style='border-left:4px solid {pc}'>
                <div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>
                    <span style='background:{pc}20;color:{pc};font-size:10px;font-weight:800;
                        border-radius:4px;padding:2px 7px'>{rec["priority"]}</span>
                    <span style='color:#8BA3C7;font-size:11px'>
                        {rec["timeline"]} · {rec["owner"]}</span>
                </div>
                <div style='color:#F0F6FF;font-size:14px;font-weight:700;margin-bottom:10px'>
                    {rec["title"]}</div>
                <div style='color:#8BA3C7;font-size:12px;margin-bottom:12px'>
                    <strong style='color:#F59E0B'>Problem:</strong> {rec["problem"]}</div>
                <div style='margin-bottom:12px'>{actions_html}</div>
                <div style='background:#0F2040;border:1px solid #10B98140;
                            border-radius:8px;padding:8px 12px'>
                    <span style='color:#10B981;font-size:11px;font-weight:700'>
                        Expected Impact: </span>
                    <span style='color:#8BA3C7;font-size:12px'>{rec["expected_impact"]}</span>
                </div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# NON-P&L CONTENT
# ══════════════════════════════════════════════════════════════════════════════
elif file_type in ("FIXED_ASSETS","BALANCE_SHEET","PAYROLL",
                   "BUDGET","CASH_FLOW","WORKING_CAPITAL",
                   "LOAN","SGA","PRODUCTION") and analysis:
    an = analysis
    with tab1:
        st.markdown(f"""
        <div style='color:#F0F6FF;font-size:22px;font-weight:800;margin-bottom:16px'>
            {company_name} · {period}</div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Key Metrics</div>",
                    unsafe_allow_html=True)
        kpi_cards = an.get("kpi_cards",[])
        cols = st.columns(3)
        for i,card in enumerate(kpi_cards):
            color = {"good":"#10B981","warning":"#F59E0B","critical":"#EF4444"}.get(
                     card.get("status","good"),"#8BA3C7")
            with cols[i%3]:
                st.markdown(f"""
                <div class='kpi-card' style='border-top:2px solid {color}'>
                    <div class='kpi-label'>{card.get("icon","")} {card["label"]}</div>
                    <div class='kpi-value' style='color:{color}'>{card["value"]}</div>
                </div>""", unsafe_allow_html=True)

        for ins in an.get("insights",[]):
            st.info(f"{ins['icon']} {ins['text']}")

        alerts = an.get("alerts",[])
        if alerts:
            st.markdown("<div class='section-title' style='margin-top:20px'>Alerts</div>",
                        unsafe_allow_html=True)
            for alert in alerts:
                sev = alert["severity"].lower()
                bc  = {"critical":"#EF4444","high":"#F97316","medium":"#EAB308"}.get(sev,"#8BA3C7")
                bg  = {"critical":"#3B0A0A","high":"#2D1B00","medium":"#1A2200"}.get(sev,"#111F38")
                st.markdown(f"""
                <div style='background:{bg};border:1px solid {bc};
                            border-radius:10px;padding:12px 14px;margin-bottom:8px'>
                    <div style='display:flex;justify-content:space-between;margin-bottom:4px'>
                        <span style='color:{bc};font-weight:700;font-size:13px'>
                            {alert.get("icon","⚠️")} {alert["title"]}</span>
                        <span style='background:{bc};color:#fff;font-size:10px;
                                     font-weight:800;border-radius:4px;padding:2px 7px'>
                            {alert["severity"]}</span>
                    </div>
                    <div style='color:#8BA3C7;font-size:12px'>{alert["message"]}</div>
                </div>""", unsafe_allow_html=True)

        charts = an.get("charts",{})
        if file_type == "FIXED_ASSETS" and charts.get("top_assets"):
            st.markdown("<div class='section-title'>Budget vs Actual</div>",
                        unsafe_allow_html=True)
            items = charts["top_assets"]
            fig = go.Figure()
            fig.add_trace(go.Bar(name="Budget",
                x=[i["name"][:20] for i in items],
                y=[i["budget"] for i in items],
                marker_color="#3B82F6",opacity=0.8))
            fig.add_trace(go.Bar(name="Actual",
                x=[i["name"][:20] for i in items],
                y=[i["actual"] for i in items],
                marker_color="#10B981",opacity=0.8))
            fig.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
                font=dict(color="#8BA3C7"),barmode="group",
                xaxis=dict(gridcolor="#1E3A5F",tickangle=-30),
                yaxis=dict(gridcolor="#1E3A5F",tickformat="$,.0f"),
                legend=dict(bgcolor="#111F38"),
                margin=dict(l=0,r=0,t=10,b=80),height=300)
            st.plotly_chart(fig,use_container_width=True)

        pie_data = (charts.get("by_category") or
                    charts.get("by_dept") or
                    charts.get("structure",[]))
        if pie_data:
            st.markdown("<div class='section-title'>Breakdown</div>",
                        unsafe_allow_html=True)
            pie = go.Figure(go.Pie(
                labels=[d["name"] for d in pie_data],
                values=[d["value"] for d in pie_data],
                hole=0.55,textfont=dict(color="#F0F6FF")))
            pie.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
                font=dict(color="#8BA3C7"),legend=dict(bgcolor="#111F38"),
                margin=dict(l=0,r=0,t=10,b=0),height=280)
            st.plotly_chart(pie,use_container_width=True)

    with tab2:
        st.info("📊 P&L Analysis available for Income Statement files only.")
    with tab3:
        st.info("🚨 Alerts shown in Overview tab.")
    with tab4:
        st.info("🔮 Forecast available for P&L files only.")
    with tab5:
        st.info("💡 Recommendations available for P&L files only.")

elif file_type == "UNKNOWN":
    with tab1:
        st.error("❓ File type not recognized")
        if analysis:
            for s in analysis.get("suggestions",[]):
                st.write(f"- **{s['type']}** (score: {s['score']})")
        st.info("📋 Supported: P&L · Balance Sheet · Fixed Assets · Payroll · Cash Flow · Budget")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — BUDGET BUILDER (دايماً ظاهر)
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    from budget_builder import (
        build_master_budget, run_scenarios,
        explain_budget, DEFAULT_ASSUMPTIONS
    )

    st.markdown("""
    <div style='background:linear-gradient(135deg,#0A1628,#0F2040);
                border:1px solid #8B5CF640;border-radius:12px;padding:20px;
                margin-bottom:20px'>
        <div style='color:#8B5CF6;font-size:13px;font-weight:700;
                    text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px'>
            🏗️ FP&A Budget Builder</div>
        <div style='color:#8BA3C7;font-size:13px;line-height:1.7'>
            Enter your assumptions and FinSight will automatically build a complete
            Master Budget — Revenue, Production, Materials, Labor, Overhead,
            SG&A, CapEx, Income Statement, and Cash Flow.
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⚙️ Budget Assumptions", expanded=True):
        col1,col2,col3 = st.columns(3)
        with col1:
            st.markdown("**Revenue**")
            base_rev   = st.number_input("Base Revenue ($)",      value=1_000_000, step=50_000)
            rev_growth = st.slider("Revenue Growth %",            0, 50, 10) / 100
            price_unit = st.number_input("Price per Unit ($)",    value=100,       step=10)
        with col2:
            st.markdown("**Costs**")
            cogs_pct   = st.slider("COGS % of Revenue",           20, 70, 38) / 100
            inflation  = st.slider("Inflation Rate %",            0,  20, 7)  / 100
            mat_cost   = st.number_input("Material Cost/Unit ($)",value=30,        step=5)
            labor_hrs  = st.number_input("Labor Hours/Unit",      value=2,         step=1)
            labor_rate = st.number_input("Labor Rate/Hour ($)",   value=25,        step=5)
        with col3:
            st.markdown("**Headcount & Finance**")
            headcount  = st.number_input("Headcount",             value=50,        step=5)
            avg_salary = st.number_input("Avg Monthly Salary ($)",value=15_000,    step=1_000)
            loan_bal   = st.number_input("Loan Balance ($)",      value=2_000_000, step=100_000)
            int_rate   = st.slider("Interest Rate %",             0, 30, 12) / 100
            tax_rate   = st.slider("Tax Rate %",                  0, 40, 22) / 100
            capex      = st.number_input("Annual CapEx ($)",      value=500_000,   step=50_000)

    if st.button("🚀 Build Master Budget", use_container_width=True):
        with st.spinner("Building complete budget..."):
            assumptions = {
                **DEFAULT_ASSUMPTIONS,
                "base_revenue":        base_rev,
                "revenue_growth":      rev_growth,
                "price_per_unit":      price_unit,
                "cogs_pct":            cogs_pct,
                "inflation_rate":      inflation,
                "material_per_unit":   mat_cost,
                "labor_hours_per_unit":labor_hrs,
                "labor_rate_per_hour": labor_rate,
                "base_headcount":      headcount,
                "avg_salary_monthly":  avg_salary,
                "loan_balance":        loan_bal,
                "interest_rate":       int_rate,
                "tax_rate":            tax_rate,
                "capex_annual":        capex,
            }
            master    = build_master_budget(assumptions)
            scenarios = run_scenarios(assumptions)
            insights  = explain_budget(master)
            st.session_state["master_budget"] = master
            st.session_state["scenarios"]     = scenarios
            st.session_state["bb_insights"]   = insights

    if "master_budget" in st.session_state:
        master    = st.session_state["master_budget"]
        scenarios = st.session_state["scenarios"]
        insights  = st.session_state["bb_insights"]
        is_data   = master["income_statement"]
        cf_data   = master["cash_flow"]

        st.markdown("<div class='section-title'>Budgeted KPIs</div>",
                    unsafe_allow_html=True)
        k1,k2,k3,k4,k5,k6 = st.columns(6)
        for col,label,val,color in [
            (k1,"Annual Revenue",  fmt_money(is_data["annual_revenue"]),  "#06B6D4"),
            (k2,"Gross Profit",    fmt_money(is_data["annual_gp"]),       "#10B981"),
            (k3,"Net Income",      fmt_money(is_data["annual_net"]),
             "#10B981" if is_data["annual_net"]>0 else "#EF4444"),
            (k4,"Gross Margin",    f"{is_data['avg_gm']:.1f}%",           "#10B981"),
            (k5,"Net Margin",      f"{is_data['avg_nm']:.1f}%",
             "#10B981" if is_data["avg_nm"]>10 else "#F59E0B"),
            (k6,"Closing Cash",    fmt_money(cf_data["closing"]),
             "#10B981" if cf_data["closing"]>0 else "#EF4444"),
        ]:
            with col:
                st.markdown(f"""
                <div class='fin-card' style='text-align:center;padding:12px'>
                    <div style='color:#8BA3C7;font-size:10px;font-weight:700;
                                text-transform:uppercase'>{label}</div>
                    <div style='color:{color};font-size:18px;font-weight:800;
                                font-family:DM Mono;margin-top:6px'>{val}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>AI Budget Insights</div>",
                    unsafe_allow_html=True)
        for ins in insights:
            st.markdown(f"""
            <div style='background:#111F38;border:1px solid #1E3A5F;
                        border-left:3px solid #8B5CF6;border-radius:8px;
                        padding:12px 16px;margin-bottom:8px;
                        color:#8BA3C7;font-size:13px;line-height:1.6'>{ins}</div>
            """, unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>Monthly Revenue Budget</div>",
                    unsafe_allow_html=True)
        rev_data = master["revenue"]["monthly"]
        fig_rev  = go.Figure()
        fig_rev.add_trace(go.Bar(
            x=[m["month"] for m in rev_data],
            y=[m["revenue"] for m in rev_data],
            marker_color="#06B6D4",opacity=0.85,name="Revenue"))
        fig_rev.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
            font=dict(color="#8BA3C7"),
            xaxis=dict(gridcolor="#1E3A5F"),
            yaxis=dict(gridcolor="#1E3A5F",tickformat="$,.0f"),
            margin=dict(l=0,r=0,t=10,b=0),height=220)
        st.plotly_chart(fig_rev,use_container_width=True)

        st.markdown("<div class='section-title'>Budgeted Income Statement</div>",
                    unsafe_allow_html=True)
        is_rows = []
        for m in is_data["monthly"]:
            is_rows.append({
                "Month":        m["month"],
                "Revenue":      fmt_money(m["revenue"]),
                "COGS":         fmt_money(m["cogs"]),
                "Gross Profit": fmt_money(m["gross_profit"]),
                "GM%":          f"{m['gross_margin']:.1f}%",
                "SG&A":         fmt_money(m["sga"]),
                "EBIT":         fmt_money(m["ebit"]),
                "Net Income":   fmt_money(m["net_income"]),
                "NM%":          f"{m['net_margin']:.1f}%",
            })
        st.dataframe(pd.DataFrame(is_rows),use_container_width=True,hide_index=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>What-If Scenarios</div>",
                    unsafe_allow_html=True)
        sc_cols = st.columns(4)
        sc_colors = {"Base Case":"#3B82F6","Optimistic":"#10B981",
                     "Pessimistic":"#EF4444","High Inflation":"#F59E0B"}
        for col,(name,vals) in zip(sc_cols,scenarios.items()):
            color = sc_colors.get(name,"#8BA3C7")
            with col:
                st.markdown(f"""
                <div class='fin-card' style='border-top:3px solid {color};text-align:center'>
                    <div style='color:{color};font-size:12px;font-weight:800;margin-bottom:10px'>
                        {name}</div>
                    <div style='color:#06B6D4;font-size:13px;margin-bottom:4px'>
                        Rev: {fmt_money(vals["revenue"])}</div>
                    <div style='color:#10B981;font-size:13px;margin-bottom:4px'>
                        Net: {fmt_money(vals["net_income"])}</div>
                    <div style='color:#F59E0B;font-size:12px'>
                        GM: {vals["gross_margin"]:.1f}% | NM: {vals["net_margin"]:.1f}%</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title' style='margin-top:20px'>Cash Flow Projection</div>",
                    unsafe_allow_html=True)
        cf_monthly = cf_data["monthly"]
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(
            x=[m["month"] for m in cf_monthly],
            y=[m["closing_cash"] for m in cf_monthly],
            name="Closing Cash",line=dict(color="#10B981",width=2.5),
            fill="tozeroy",fillcolor="rgba(16,185,129,0.08)"))
        fig_cf.add_trace(go.Bar(
            x=[m["month"] for m in cf_monthly],
            y=[m["net_cash"] for m in cf_monthly],
            name="Net Cash Flow",
            marker_color=["#10B981" if m["net_cash"]>=0 else "#EF4444"
                          for m in cf_monthly],opacity=0.7))
        fig_cf.update_layout(plot_bgcolor="#111F38",paper_bgcolor="#111F38",
            font=dict(color="#8BA3C7"),
            xaxis=dict(gridcolor="#1E3A5F"),
            yaxis=dict(gridcolor="#1E3A5F",tickformat="$,.0f"),
            legend=dict(bgcolor="#111F38"),
            margin=dict(l=0,r=0,t=10,b=0),height=250)
        st.plotly_chart(fig_cf,use_container_width=True)
