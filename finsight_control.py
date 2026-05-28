import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import requests
import json
import io
from validator import run_validation, normalize_percentage
from calculations import run_scenarios, build_cashflows, calculate_future_value
from report_generator import generate_report
from session_manager import save_session, load_session, clear_session
from mapping_engine import (map_dataframe_columns, detect_statement_type,
                               get_benchmark, check_assumptions)
from sensitivity import run_sensitivity

st.set_page_config(page_title="FinSight Corporate",
                   page_icon="🏢", layout="wide")

st.markdown("""
<h1 style='text-align:center;color:#1E3A5F;'>🏢 FinSight</h1>
<p style='text-align:center;color:gray;'>
    Corporate Investment Intelligence Platform
</p><hr>
""", unsafe_allow_html=True)

if "project_name" not in st.session_state:
    saved = load_session()
    if saved:
        for k, v in saved.items():
            st.session_state[k] = v
        st.rerun()

if "projects" not in st.session_state:
    st.session_state["projects"] = []

step   = st.session_state.get("step", 1)
labels = ["📋 Project Info", "📂 Data Input",
          "🔍 Validation", "📊 Results", "🤖 CFO Report"]
st.progress(step / 5)
st.markdown(f"**Step {step} of 5 — {labels[step-1]}**")
st.markdown("---")

# ── STEP 1 ───────────────────────────────────────────────
if step == 1:
    st.subheader("📋 Project Information")
    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input("Project Name",
                           placeholder="e.g. New Production Line")
        project_type = st.selectbox("Project Type", [
            "Expansion", "Automation", "Cost Reduction",
            "New Product", "ERP Implementation", "New Branch"])
    with col2:
        company_name = st.text_input("Company Name",
                           placeholder="e.g. Edita Food Industries")
        currency = st.selectbox("Base Currency", ["EGP", "USD", "EUR"])

    if st.button("Next →"):
        if not project_name:
            st.error("Please enter a project name.")
        else:
            st.session_state.update({
                "step": 2, "project_name": project_name,
                "project_type": project_type,
                "company_name": company_name, "currency": currency
            })
            save_session(dict(st.session_state))
            st.rerun()

# ── STEP 2 ───────────────────────────────────────────────
elif step == 2:
    st.subheader("📂 Data Input")
    input_mode = st.radio("How would you like to enter data?",
                          ["Upload Excel", "Manual Entry"], horizontal=True)

    if input_mode == "Upload Excel":
        uploaded = st.file_uploader("Upload your financial model (Excel)",
                                    type=["xlsx", "xls"])
        if uploaded:
            st.session_state["uploaded_file"] = uploaded
            st.success("File uploaded — proceed to validation.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state["step"] = 1
                save_session(dict(st.session_state))
                st.rerun()
        with col2:
            if st.button("Next →") and st.session_state.get("uploaded_file"):
                st.session_state["input_mode"] = "upload"
                st.session_state["step"] = 3
                save_session(dict(st.session_state))
                st.rerun()
    else:
        st.markdown("#### CapEx")
        capex = st.number_input("Total Capital Expenditure",
                                min_value=0.0, value=3_000_000.0, step=100_000.0)
        st.markdown("#### Operating Forecast")
        years = st.slider("Number of Years", min_value=1, max_value=10, value=5)
        revenues, fixed_costs, var_costs, maintenance = [], [], [], []

        for y in range(1, years + 1):
            st.markdown(f"**Year {y}**")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                revenues.append(st.number_input(
                    f"Revenue Y{y}", value=2_500_000.0,
                    step=100_000.0, key=f"rev_{y}"))
            with c2:
                fixed_costs.append(st.number_input(
                    f"Fixed Costs Y{y}", value=400_000.0,
                    step=50_000.0, key=f"fix_{y}"))
            with c3:
                var_costs.append(st.number_input(
                    f"Variable Costs Y{y}", value=200_000.0,
                    step=50_000.0, key=f"var_{y}"))
            with c4:
                maintenance.append(st.number_input(
                    f"Maintenance Y{y}", value=50_000.0,
                    step=10_000.0, key=f"mnt_{y}"))

        st.markdown("#### Economic Variables")
        col1, col2, col3 = st.columns(3)
        with col1:
            discount_rate = st.slider("Discount Rate / WACC (%)", 1.0, 30.0, 12.0, 0.5)
        with col2:
            tax_rate = st.slider("Tax Rate (%)", 0.0, 40.0, 22.5, 0.5)
        with col3:
            inflation = st.slider("Inflation Rate (%)", 1.0, 30.0, 14.0, 0.5)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state["step"] = 1
                save_session(dict(st.session_state))
                st.rerun()
        with col2:
            if st.button("Next →"):
                st.session_state["projects"].append({
                    "name":          st.session_state.get("project_name", "Project"),
                    "type":          st.session_state.get("project_type", "Expansion"),
                    "capex":         capex,
                    "revenues":      revenues,
                    "fixed_costs":   fixed_costs,
                    "var_costs":     var_costs,
                    "maintenance":   maintenance,
                    "discount_rate": discount_rate / 100,
                    "tax_rate":      tax_rate / 100,
                })
                st.session_state.update({
                    "input_mode":    "manual",
                    "capex":         capex,
                    "revenues":      revenues,
                    "fixed_costs":   fixed_costs,
                    "var_costs":     var_costs,
                    "maintenance":   maintenance,
                    "discount_rate": discount_rate / 100,
                    "tax_rate":      tax_rate / 100,
                    "inflation":     inflation / 100,
                    "step":          3
                })
                save_session(dict(st.session_state))
                st.rerun()

# ── STEP 3 ───────────────────────────────────────────────
elif step == 3:
    st.subheader("🔍 Validation & Assumption Check")
    s = st.session_state

    if s.get("input_mode") == "upload":
        results = run_validation(s["uploaded_file"], s["project_name"])
        for msg in results['passed']:   st.success(f"✅ {msg}")
        for msg in results['warnings']: st.warning(f"⚠️ {msg}")
        for msg in results['errors']:   st.error(f"🚨 {msg}")

        if not results['errors']:
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                discount_input  = st.text_input("Discount Rate", value="12%")
                tax_input       = st.text_input("Tax Rate", value="22.5%")
            with col2:
                inflation_input = st.text_input("Inflation Rate", value="14%")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("← Back"):
                    st.session_state["step"] = 2
                    save_session(dict(st.session_state))
                    st.rerun()
            with col2:
                if st.button("Proceed to Analysis →"):
                    st.session_state.update({
                        "discount_rate": normalize_percentage(discount_input),
                        "tax_rate":      normalize_percentage(tax_input),
                        "inflation":     normalize_percentage(inflation_input),
                        "step":          4
                    })
                    save_session(dict(st.session_state))
                    st.rerun()
    else:
        st.success("✅ Manual entry validated")
        st.markdown("### 🔔 Assumption Risk Check")
        alerts = check_assumptions(
            s.get("discount_rate", 0.12),
            s.get("tax_rate", 0.225),
            s.get("inflation", 0.14),
            s.get("revenues", []),
            s.get("fixed_costs", []),
            s.get("var_costs", [])
        )
        for alert in alerts:
            if "✅" in alert:
                st.success(alert)
            else:
                st.warning(alert)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state["step"] = 2
                save_session(dict(st.session_state))
                st.rerun()
        with col2:
            if st.button("Proceed to Analysis →"):
                st.session_state["step"] = 4
                save_session(dict(st.session_state))
                st.rerun()

# ── STEP 4 ───────────────────────────────────────────────
elif step == 4:
    st.subheader("📊 Investment Analysis Results")
    s = st.session_state

    if "capex" not in s:
        st.error("⚠️ Session data missing.")
        if st.button("← Back to Data Input"):
            st.session_state["step"] = 2
            st.rerun()
        st.stop()

    scenarios = run_scenarios(
        s["capex"], s["revenues"], s["fixed_costs"],
        s["var_costs"], s["maintenance"],
        s["tax_rate"], s["discount_rate"]
    )
    st.session_state["scenarios"] = scenarios
    save_session(dict(st.session_state))
    cur = s.get("currency", "EGP")

    # ── Executive Dashboard ──────────────────────────────
    st.markdown("### 🎯 Executive Dashboard")
    npv   = scenarios['base']['npv']
    irr   = scenarios['base']['irr'] or 0
    pi    = scenarios['base']['pi']  or 0
    dr    = s['discount_rate'] * 100
    bench = get_benchmark(s.get("project_type", "Expansion"))

    if npv > 0 and irr > dr and pi > 1:
        verdict       = "🟢 APPROVE"
        verdict_color = "#2ecc71"
    elif npv > 0 and pi > 1:
        verdict       = "🟡 CONDITIONAL"
        verdict_color = "#f39c12"
    else:
        verdict       = "🔴 REJECT"
        verdict_color = "#e74c3c"

    bench_status = (
        f"✅ IRR {irr:.1f}% within benchmark {bench['min_irr']}-{bench['max_irr']}%"
        if bench['min_irr'] <= irr <= bench['max_irr']
        else f"⚠️ IRR {irr:.1f}% outside range {bench['min_irr']}-{bench['max_irr']}%"
    )

    risk_factors = []
    if npv < 0:
        risk_factors.append("Negative NPV under base case")
    if irr < dr:
        risk_factors.append(f"IRR ({irr:.1f}%) below WACC ({dr:.1f}%)")
    if pi < 1:
        risk_factors.append("Profitability Index below 1.0")
    if not scenarios['base']['payback']:
        risk_factors.append("Investment not recovered within project life")
    if not risk_factors:
        risk_factors.append("No major risk factors identified")

    st.markdown(f"""
    <div style='background:#1a1a2e;padding:20px;border-radius:10px;
    text-align:center;border:2px solid {verdict_color};'>
        <h2 style='color:{verdict_color};'>{verdict}</h2>
        <p style='color:white;'>{bench_status}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**🔺 Top Risk Factors:**")
    for i, risk in enumerate(risk_factors[:3], 1):
        st.write(f"{i}. {risk}")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    col1.metric("📉 Worst NPV", f"{cur} {scenarios['worst']['npv']:,.0f}")
    col2.metric("📊 Base NPV",  f"{cur} {scenarios['base']['npv']:,.0f}",
                "Positive ✅" if scenarios['base']['npv'] > 0 else "Negative ❌")
    col3.metric("📈 Best NPV",  f"{cur} {scenarios['best']['npv']:,.0f}")

    col1, col2, col3 = st.columns(3)
    col1.metric("IRR (Base)",
                f"{scenarios['base']['irr']:.1f}%"
                if scenarios['base']['irr'] else "N/A")
    col2.metric("Payback Period",
                f"Year {scenarios['base']['payback']}"
                if scenarios['base']['payback'] else "Not recovered")
    col3.metric("Profitability Index",
                f"{scenarios['base']['pi']:.2f}"
                if scenarios['base']['pi'] else "N/A")

    st.markdown("---")

    years_list = list(range(len(scenarios['base']['cashflows'])))
    fig = go.Figure()
    for label, key, color in [
            ("Best Case",  "best",  "#2ecc71"),
            ("Base Case",  "base",  "#3498db"),
            ("Worst Case", "worst", "#e74c3c")]:
        fig.add_trace(go.Scatter(
            x=years_list, y=scenarios[key]['cashflows'],
            name=label, mode="lines+markers",
            line=dict(color=color)))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title="Net Cash Flow by Scenario",
                      xaxis_title="Year",
                      yaxis_title=f"Cash Flow ({cur})")
    st.plotly_chart(fig, use_container_width=True)

    # ── Sensitivity Analysis ─────────────────────────────
    st.markdown("---")
    st.subheader("🔬 Sensitivity Analysis")
    sens_results, base_npv = run_sensitivity(
        s["capex"], s["revenues"], s["fixed_costs"],
        s["var_costs"], s["maintenance"],
        s["tax_rate"], s["discount_rate"]
    )
    sens_df = pd.DataFrame(sens_results)
    st.dataframe(sens_df, use_container_width=True)

    fig3 = px.bar(
        sens_df, x="Scenario", y="Change %",
        color="Impact",
        color_discrete_map={
            "🔴 High Risk": "#e74c3c",
            "🟡 Moderate":  "#f39c12",
            "🟢 Low Risk":  "#2ecc71"},
        title="NPV Sensitivity to Key Variables"
    )
    fig3.add_hline(y=0, line_dash="dash", line_color="white")
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")

    # ── Project Comparison ───────────────────────────────
    st.subheader("⚖️ Project Comparison")
    projects = st.session_state.get("projects", [])

    col1, col2 = st.columns(2)
    with col1:
        if len(projects) < 4:
            if st.button("➕ Add Another Project to Compare"):
                st.session_state["step"] = 1
                save_session(dict(st.session_state))
                st.rerun()
    with col2:
        if st.button("🗑️ Clear All Projects"):
            st.session_state["projects"] = []
            save_session(dict(st.session_state))
            st.rerun()

    if len(projects) > 1:
        st.markdown(f"**Comparing {len(projects)} Projects**")
        comparison_data = []
        for p in projects:
            sc = run_scenarios(
                p["capex"], p["revenues"], p["fixed_costs"],
                p["var_costs"], p["maintenance"],
                p["tax_rate"], p["discount_rate"]
            )
            score = 0
            if sc['base']['npv'] > 0:
                score += 2
            if (sc['base']['irr'] or 0) > (p['discount_rate'] * 100):
                score += 2
            if (sc['base']['pi'] or 0) > 1:
                score += 1
            if sc['base']['payback']:
                score += 1

            comparison_data.append({
                "Project":    p["name"],
                "Type":       p["type"],
                "NPV (Base)": round(sc['base']['npv'], 0),
                "IRR (%)":    round(sc['base']['irr'], 1) if sc['base']['irr'] else 0,
                "Payback":    f"Year {sc['base']['payback']}" if sc['base']['payback'] else "N/A",
                "PI":         round(sc['base']['pi'], 2) if sc['base']['pi'] else 0,
                "Score":      score,
                "Verdict":    "🟢 APPROVE" if score >= 4
                              else "🟡 CONDITIONAL" if score >= 2
                              else "🔴 REJECT"
            })

        comp_df = pd.DataFrame(comparison_data).sort_values("Score", ascending=False)
        winner  = comp_df.iloc[0]["Project"]
        st.success(f"🏆 Recommended Project: **{winner}**")
        st.dataframe(comp_df, use_container_width=True)

        fig_comp = px.bar(
            comp_df, x="Project", y="NPV (Base)",
            color="Verdict",
            color_discrete_map={
                "🟢 APPROVE":     "#2ecc71",
                "🟡 CONDITIONAL": "#f39c12",
                "🔴 REJECT":      "#e74c3c"},
            title="NPV Comparison Across Projects",
            text="NPV (Base)"
        )
        fig_comp.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
        st.plotly_chart(fig_comp, use_container_width=True)

        fig_irr = px.bar(
            comp_df, x="Project", y="IRR (%)",
            color="Verdict",
            color_discrete_map={
                "🟢 APPROVE":     "#2ecc71",
                "🟡 CONDITIONAL": "#f39c12",
                "🔴 REJECT":      "#e74c3c"},
            title="IRR Comparison Across Projects"
        )
        dr_pct = s['discount_rate'] * 100
        fig_irr.add_hline(y=dr_pct, line_dash="dash",
                          line_color="white",
                          annotation_text=f"WACC {dr_pct:.1f}%")
        st.plotly_chart(fig_irr, use_container_width=True)

        st.markdown("---")
        st.subheader("🤖 AI Project Comparison Memo")
        if st.button("Generate Comparison Memo"):
            with st.spinner("Analyzing all projects..."):
                projects_summary = ""
                for _, row in comp_df.iterrows():
                    projects_summary += (
                        f"Project: {row['Project']} ({row['Type']})\n"
                        f"- NPV: {cur} {row['NPV (Base)']:,.0f}\n"
                        f"- IRR: {row['IRR (%)']:.1f}%\n"
                        f"- Payback: {row['Payback']}\n"
                        f"- Score: {row['Score']}/6\n"
                        f"- Verdict: {row['Verdict']}\n\n"
                    )
                prompt = f"""
You are a CFO preparing a capital allocation recommendation for the Board.
The company is evaluating {len(projects)} investment projects simultaneously.
WACC / Discount Rate: {s['discount_rate']*100:.1f}%

{projects_summary}

Write a professional Capital Allocation Memo with:
1. Executive Summary
2. Project Rankings with Justification
3. Risk Comparison
4. Final Recommendation
5. Budget Allocation suggestion

Reference CMA/CFA capital budgeting principles.
Use formal CFO language suitable for board presentation.
"""
                try:
                    groq_key = st.secrets.get("GROQ_API_KEY", "")
                    if groq_key:
                        resp = requests.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Content-Type":  "application/json",
                                "Authorization": f"Bearer {groq_key}"
                            },
                            json={
                                "model":      "llama-3.3-70b-versatile",
                                "messages":   [{"role": "user", "content": prompt}],
                                "max_tokens": 1200
                            },
                            timeout=30
                        )
                        result = resp.json()
                        if "choices" in result:
                            memo = result["choices"][0]["message"]["content"]
                            st.markdown(memo)
                            st.session_state["comparison_memo"] = memo
                            save_session(dict(st.session_state))
                        else:
                            st.error("API Error")
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("Add at least one more project to enable comparison.")

    # ── Excel Export ─────────────────────────────────────
    st.markdown("---")
    st.subheader("📥 Export to Excel")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame({
            'Metric': ['NPV', 'IRR (%)', 'Payback', 'PI'],
            'Worst':  [scenarios['worst']['npv'], scenarios['worst']['irr'],
                       scenarios['worst']['payback'], scenarios['worst']['pi']],
            'Base':   [scenarios['base']['npv'],  scenarios['base']['irr'],
                       scenarios['base']['payback'],  scenarios['base']['pi']],
            'Best':   [scenarios['best']['npv'],  scenarios['best']['irr'],
                       scenarios['best']['payback'],  scenarios['best']['pi']],
        }).to_excel(writer, sheet_name='Summary', index=False)

        pd.DataFrame({
            'Year':  years_list,
            'Best':  scenarios['best']['cashflows'],
            'Base':  scenarios['base']['cashflows'],
            'Worst': scenarios['worst']['cashflows'],
        }).to_excel(writer, sheet_name='Cash Flows', index=False)

        sens_df.to_excel(writer, sheet_name='Sensitivity', index=False)

        if len(projects) > 1:
            comp_df.to_excel(writer, sheet_name='Comparison', index=False)

    st.download_button(
        "⬇️ Download Excel Report",
        data=output.getvalue(),
        file_name=f"{s.get('project_name','project')}_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back"):
            st.session_state["step"] = 3
            save_session(dict(st.session_state))
            st.rerun()
    with col2:
        if st.button("Generate CFO Report →"):
            st.session_state["step"] = 5
            save_session(dict(st.session_state))
            st.rerun()

# ── STEP 5 ───────────────────────────────────────────────
elif step == 5:
    st.subheader("🤖 CFO Investment Recommendation")
    s   = st.session_state
    sc  = s["scenarios"]
    cur = s.get("currency", "EGP")

    worst_pi  = f"{sc['worst']['pi']:.2f}"   if sc['worst']['pi']  else "N/A"
    base_pi   = f"{sc['base']['pi']:.2f}"    if sc['base']['pi']   else "N/A"
    best_pi   = f"{sc['best']['pi']:.2f}"    if sc['best']['pi']   else "N/A"
    worst_irr = f"{sc['worst']['irr']:.1f}%" if sc['worst']['irr'] else "N/A"
    base_irr  = f"{sc['base']['irr']:.1f}%"  if sc['base']['irr']  else "N/A"
    best_irr  = f"{sc['best']['irr']:.1f}%"  if sc['best']['irr']  else "N/A"
    worst_pb  = f"Year {sc['worst']['payback']}" if sc['worst']['payback'] else "Not recovered"
    base_pb   = f"Year {sc['base']['payback']}"  if sc['base']['payback']  else "Not recovered"
    best_pb   = f"Year {sc['best']['payback']}"  if sc['best']['payback']  else "Not recovered"

    bench = get_benchmark(s.get("project_type", "Expansion"))

    st.markdown("### 📊 Financial Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Worst Case**")
        st.write(f"NPV: {cur} {sc['worst']['npv']:,.0f}")
        st.write(f"IRR: {worst_irr}")
        st.write(f"Payback: {worst_pb}")
        st.write(f"PI: {worst_pi}")
    with col2:
        st.markdown("**Base Case**")
        st.write(f"NPV: {cur} {sc['base']['npv']:,.0f}")
        st.write(f"IRR: {base_irr}")
        st.write(f"Payback: {base_pb}")
        st.write(f"PI: {base_pi}")
    with col3:
        st.markdown("**Best Case**")
        st.write(f"NPV: {cur} {sc['best']['npv']:,.0f}")
        st.write(f"IRR: {best_irr}")
        st.write(f"Payback: {best_pb}")
        st.write(f"PI: {best_pi}")

    st.markdown("---")
    st.markdown("### 🤖 AI CFO Memo")

    if st.button("Generate CFO Memo"):
        with st.spinner("Writing Investment Memo..."):
            prompt = f"""
You are a Chief Financial Officer at a leading corporation.
Prepare a formal Investment Decision Memo for the Board of Directors.

Project: {s['project_name']} | Type: {s['project_type']}
Company: {s.get('company_name', 'N/A')} | Currency: {cur}
Discount Rate: {s['discount_rate']*100:.1f}% | Tax Rate: {s['tax_rate']*100:.1f}%
Industry Benchmark IRR: {bench['min_irr']}% - {bench['max_irr']}%

Financial Results:
                  Worst         Base          Best
NPV:              {sc['worst']['npv']:,.0f}    {sc['base']['npv']:,.0f}    {sc['best']['npv']:,.0f}
IRR:              {worst_irr}    {base_irr}    {best_irr}
Payback:          {worst_pb}     {base_pb}     {best_pb}
Prof. Index:      {worst_pi}     {base_pi}     {best_pi}

Write a structured Investment Memo with:
1. Executive Summary
2. Financial Assessment (reference benchmark IRR)
3. Risk Analysis
4. Strategic Recommendation (Approve / Reject / Conditional)
5. Conditions or Mitigants
Use formal CFO language suitable for board presentation.
"""
            memo = None
            try:
                groq_key = st.secrets.get("GROQ_API_KEY", "")
                if groq_key:
                    resp = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Content-Type":  "application/json",
                            "Authorization": f"Bearer {groq_key}"
                        },
                        json={
                            "model":      "llama-3.3-70b-versatile",
                            "messages":   [{"role": "user", "content": prompt}],
                            "max_tokens": 1000
                        },
                        timeout=30
                    )
                    result = resp.json()
                    if "choices" in result:
                        memo = result["choices"][0]["message"]["content"]
                    elif "error" in result:
                        st.error(f"Groq Error: {result['error']['message']}")
            except Exception as e:
                st.warning(f"Connection error: {e}")

            if not memo:
                st.info("Showing rule-based recommendation:")
                npv = sc['base']['npv']
                irr = sc['base']['irr'] or 0
                pi  = sc['base']['pi']  or 0
                dr  = s['discount_rate'] * 100

                if npv > 0 and irr > dr and pi > 1:
                    decision = "✅ RECOMMENDATION: APPROVE"
                    findings = [
                        f"Positive NPV of {cur} {npv:,.0f} indicates value creation.",
                        f"IRR of {irr:.1f}% exceeds WACC of {dr:.1f}%.",
                        f"PI of {pi:.2f} confirms efficient capital deployment."
                    ]
                    actions = [
                        "Proceed with project implementation.",
                        "Establish quarterly review milestones.",
                        "Monitor cash flow against base case."
                    ]
                elif npv > 0 and pi > 1:
                    decision = "⚠️ RECOMMENDATION: CONDITIONAL APPROVAL"
                    findings = [
                        f"NPV is positive at {cur} {npv:,.0f}.",
                        f"IRR of {irr:.1f}% is marginal vs WACC.",
                        "Moderate execution risk detected."
                    ]
                    actions = [
                        "Review and reduce cost structure.",
                        "Seek additional revenue commitments.",
                        "Re-evaluate after 6 months."
                    ]
                else:
                    decision = "❌ RECOMMENDATION: REJECT"
                    findings = [
                        f"NPV of {cur} {npv:,.0f} does not justify investment.",
                        f"IRR of {irr:.1f}% below minimum threshold.",
                        "Project does not meet return requirements."
                    ]
                    actions = [
                        "Do not proceed under current parameters.",
                        "Explore cost reduction strategies.",
                        "Reconsider if market conditions improve."
                    ]

                st.markdown(f"### {decision}")
                st.markdown("**Key Findings:**")
                for f in findings:
                    st.write(f"• {f}")
                st.markdown("**Recommended Actions:**")
                for a in actions:
                    st.write(f"→ {a}")
                memo = decision + "\n" + "\n".join(findings) + "\n" + "\n".join(actions)
            else:
                st.markdown(memo)

            st.session_state["memo"] = memo
            save_session(dict(st.session_state))

    if st.session_state.get("memo"):
        st.markdown("---")
        if st.button("📄 Export PDF Report"):
            path = generate_report(
                s["project_name"], s["project_type"],
                sc, s["memo"]
            )
            with open(path, "rb") as f:
                st.download_button(
                    "⬇️ Download PDF", data=f,
                    file_name=f"{s['project_name']}_report.pdf",
                    mime="application/pdf"
                )

    st.markdown("---")
    if st.button("🔄 Start New Project"):
        clear_session()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
