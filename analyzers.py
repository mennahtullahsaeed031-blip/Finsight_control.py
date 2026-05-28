import pandas as pd
import numpy as np


def _to_num(val):
    if val is None:
        return None
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return None
    except:
        pass
    s = str(val).strip().replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except:
        return None


def _fmt(v):
    if v is None:
        return "—"
    s = "-" if v < 0 else ""
    v = abs(v)
    return f"{s}${v/1e6:.2f}M" if v >= 1e6 else f"{s}${v/1e3:.0f}K" if v >= 1e3 else f"{s}${v:.0f}"


def _find_text_col(df, exclude=None):
    for ci in range(min(5, len(df.columns))):
        if ci == exclude:
            continue
        col = df.iloc[:, ci].astype(str)
        ratio = sum(
            1 for v in col
            if len(v.strip()) > 2
            and not v.strip().replace(".", "").replace("-", "").replace(",", "").isnumeric()
            and v.strip() not in ["nan", "None", ""]
        ) / max(len(col), 1)
        if ratio > 0.3:
            return ci
    return 0


def _find_first_num_col(df, exclude=None):
    for ci in range(len(df.columns)):
        if ci == exclude:
            continue
        col = df.iloc[:, ci].apply(_to_num)
        if col.notna().sum() / max(len(col), 1) > 0.3:
            return ci
    return None


def _find_col_by_keywords(headers, keywords):
    for i, h in enumerate(headers):
        if any(kw in str(h).lower() for kw in keywords):
            return i
    return None


def _pl_charts(s):
    return {
        "waterfall": [
            {"label": "Revenue",    "value": s["total_revenue"], "color": "#06B6D4"},
            {"label": "COGS",       "value": -s["total_cogs"],   "color": "#EF4444"},
            {"label": "Gross Profit","value": s["gross_profit"],  "color": "#10B981"},
            {"label": "OpEx",       "value": -s["total_opex"],   "color": "#F97316"},
            {"label": "Net Income", "value": s["net_income"],     "color": "#3B82F6"},
        ]
    }


def analyze_pl(df_dict, summary, line_items):
    from kpi import calculate_kpis, format_kpi_card
    kpis      = calculate_kpis(summary, line_items)
    kpi_cards = format_kpi_card(kpis)
    return {
        "type":       "P&L",
        "summary":    summary,
        "line_items": line_items,
        "kpis":       kpis,
        "kpi_cards":  kpi_cards,
        "charts":     _pl_charts(summary),
        "alerts":     [],
    }


def analyze_fixed_assets(df_dict):
    all_items = []
    total_budget = total_actual = total_depreciation = 0

    BUDGET_KW = ["budget", "plan", "allocated", "مخطط", "ميزانية"]
    ACTUAL_KW = ["actual", "spent", "utilized", "فعلي", "منصرف"]
    DEP_KW    = ["depreciation", "dep", "استهلاك"]
    ASSET_CAT = ["equipment", "machinery", "vehicles", "furniture", "building",
                 "land", "software", "it", "hardware"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row = 0
        for i in range(min(10, len(df))):
            row = df.iloc[i].astype(str).str.lower().tolist()
            if any(any(kw in v for kw in BUDGET_KW + ACTUAL_KW) for v in row):
                header_row = i
                break

        headers = df.iloc[header_row].astype(str).tolist()
        data    = df.iloc[header_row + 1:].reset_index(drop=True)

        name_col   = _find_text_col(data)
        budget_col = _find_col_by_keywords(headers, BUDGET_KW)
        actual_col = _find_col_by_keywords(headers, ACTUAL_KW)
        dep_col    = _find_col_by_keywords(headers, DEP_KW)

        for _, row in data.iterrows():
            name = str(row.iloc[name_col]).strip() if name_col is not None else ""
            if not name or name in ["nan", "None", ""]:
                continue
            budget = _to_num(row.iloc[budget_col]) or 0 if budget_col is not None else 0
            actual = _to_num(row.iloc[actual_col]) or 0 if actual_col is not None else 0
            dep    = _to_num(row.iloc[dep_col])    or 0 if dep_col    is not None else 0
            if budget == 0 and actual == 0:
                continue

            cat = "Other"
            for c in ASSET_CAT:
                if c in name.lower():
                    cat = c.title()
                    break

            variance     = actual - budget
            variance_pct = (variance / budget * 100) if budget else 0
            utilization  = (actual  / budget * 100)  if budget else 0

            all_items.append({
                "name": name, "category": cat,
                "budget": budget, "actual": actual, "depreciation": dep,
                "variance": variance, "variance_pct": variance_pct,
                "utilization": utilization, "over_budget": variance > 0 and budget > 0,
            })
            total_budget       += budget
            total_actual       += actual
            total_depreciation += dep

    if not all_items:
        return {"type": "FIXED_ASSETS", "error": "No asset data found",
                "kpi_cards": [], "alerts": [], "insights": [], "charts": {}}

    utilization_rate  = (total_actual / total_budget * 100) if total_budget else 0
    over_budget_items = [i for i in all_items if i["over_budget"]]
    cat_summary       = {}
    for item in all_items:
        c = item["category"]
        cat_summary[c] = cat_summary.get(c, 0) + item["actual"]

    kpi_cards = [
        {"label": "Total Budget",      "value": _fmt(total_budget),
         "status": "good",    "icon": "📋"},
        {"label": "Total Spent",       "value": _fmt(total_actual),
         "status": "good" if utilization_rate <= 100 else "critical", "icon": "💰"},
        {"label": "Utilization",       "value": f"{utilization_rate:.1f}%",
         "status": "good" if 80 <= utilization_rate <= 105 else "warning", "icon": "📊"},
        {"label": "Depreciation",      "value": _fmt(total_depreciation),
         "status": "good",    "icon": "📉"},
        {"label": "Over Budget Items", "value": str(len(over_budget_items)),
         "status": "critical" if over_budget_items else "good", "icon": "⚠️"},
        {"label": "Categories",        "value": str(len(cat_summary)),
         "status": "good",    "icon": "🗂️"},
    ]

    alerts = []
    for item in over_budget_items:
        alerts.append({
            "severity": "Critical" if item["variance_pct"] > 20 else "High",
            "title":    f"Over Budget: {item['name']}",
            "message":  f"Spent {_fmt(item['actual'])} vs budget {_fmt(item['budget'])} ({item['variance_pct']:+.1f}%)",
            "icon":     "🔴",
        })

    insights = []
    if utilization_rate > 110:
        insights.append({"icon": "🚨", "text": f"CapEx is {utilization_rate-100:.1f}% over total budget"})
    elif utilization_rate < 60:
        insights.append({"icon": "💡", "text": f"Only {utilization_rate:.1f}% of CapEx budget utilized"})
    else:
        insights.append({"icon": "✅", "text": f"CapEx utilization at {utilization_rate:.1f}% — healthy range"})

    return {
        "type":      "FIXED_ASSETS",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  insights,
        "summary": {
            "total_budget": total_budget, "total_actual": total_actual,
            "total_depreciation": total_depreciation,
            "utilization_rate": utilization_rate,
        },
        "charts": {
            "by_category": [{"name": k, "value": v} for k, v in cat_summary.items()],
            "top_assets":  sorted(all_items, key=lambda x: x["actual"], reverse=True)[:8],
        }
    }


def analyze_balance_sheet(df_dict):
    total_assets = total_liabilities = total_equity = 0
    current_assets = current_liabilities = 0

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        text_col = _find_text_col(df)
        num_col  = _find_first_num_col(df, text_col)
        if text_col is None or num_col is None:
            continue
        for _, row in df.iterrows():
            label = str(row.iloc[text_col]).lower().strip()
            val   = _to_num(row.iloc[num_col]) or 0
            if any(x in label for x in ["total assets", "أصول إجمالية"]):
                total_assets = val or total_assets
            if any(x in label for x in ["total liabilities", "إجمالي الخصوم"]):
                total_liabilities = val or total_liabilities
            if any(x in label for x in ["equity", "shareholders", "حقوق ملكية"]):
                total_equity = val or total_equity
            if any(x in label for x in ["current assets", "أصول متداولة"]):
                current_assets = val or current_assets
            if any(x in label for x in ["current liabilities", "خصوم متداولة"]):
                current_liabilities = val or current_liabilities

    if total_assets == 0:
        return {"type": "BALANCE_SHEET", "error": "No data found",
                "kpi_cards": [], "alerts": [], "charts": {}}

    current_ratio   = current_assets / current_liabilities if current_liabilities else 0
    debt_to_equity  = total_liabilities / total_equity     if total_equity         else 0
    working_capital = current_assets - current_liabilities

    kpi_cards = [
        {"label": "Total Assets",     "value": _fmt(total_assets),
         "status": "good",  "icon": "🏦"},
        {"label": "Total Liabilities","value": _fmt(total_liabilities),
         "status": "good" if total_liabilities < total_assets else "warning", "icon": "📋"},
        {"label": "Total Equity",     "value": _fmt(total_equity),
         "status": "good" if total_equity > 0 else "critical", "icon": "💰"},
        {"label": "Current Ratio",    "value": f"{current_ratio:.2f}x",
         "status": "good" if current_ratio >= 1.5 else "warning" if current_ratio >= 1 else "critical", "icon": "⚡"},
        {"label": "Debt-to-Equity",   "value": f"{debt_to_equity:.2f}x",
         "status": "good" if debt_to_equity < 1 else "warning" if debt_to_equity < 2 else "critical", "icon": "📊"},
        {"label": "Working Capital",  "value": _fmt(working_capital),
         "status": "good" if working_capital > 0 else "critical", "icon": "💵"},
    ]

    alerts = []
    if current_ratio < 1:
        alerts.append({"severity": "Critical", "title": "Liquidity Risk", "icon": "🚨",
                       "message": f"Current ratio {current_ratio:.2f}x — below 1.0"})
    if debt_to_equity > 2:
        alerts.append({"severity": "High", "title": "High Leverage", "icon": "⚠️",
                       "message": f"Debt-to-equity at {debt_to_equity:.2f}x"})

    return {
        "type":      "BALANCE_SHEET",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "summary": {
            "total_assets": total_assets, "total_liabilities": total_liabilities,
            "total_equity": total_equity, "current_ratio": current_ratio,
            "debt_to_equity": debt_to_equity, "working_capital": working_capital,
        },
        "charts": {
            "structure": [
                {"name": "Liabilities", "value": total_liabilities, "color": "#EF4444"},
                {"name": "Equity",      "value": total_equity,      "color": "#10B981"},
            ]
        }
    }


def analyze_payroll(df_dict):
    employees = []
    SALARY_KW = ["salary", "basic", "gross", "net", "مرتب", "راتب"]
    DEPT_KW   = ["department", "dept", "قسم", "إدارة"]
    NAME_KW   = ["name", "employee", "staff", "الاسم", "موظف"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row = 0
        for i in range(min(5, len(df))):
            row = df.iloc[i].astype(str).str.lower().tolist()
            if any(any(kw in v for kw in SALARY_KW + NAME_KW) for v in row):
                header_row = i
                break
        headers = df.iloc[header_row].astype(str).tolist()
        data    = df.iloc[header_row + 1:].reset_index(drop=True)

        name_col   = _find_col_by_keywords(headers, NAME_KW)
        salary_col = _find_col_by_keywords(headers, SALARY_KW)
        dept_col   = _find_col_by_keywords(headers, DEPT_KW)

        if salary_col is None:
            continue
        for _, row in data.iterrows():
            salary = _to_num(row.iloc[salary_col])
            if not salary:
                continue
            employees.append({
                "name":   str(row.iloc[name_col]).strip() if name_col is not None else "N/A",
                "salary": salary,
                "dept":   str(row.iloc[dept_col]).strip()  if dept_col  is not None else "Other",
            })

    if not employees:
        return {"type": "PAYROLL", "error": "No payroll data found",
                "kpi_cards": [], "alerts": [], "charts": {}}

    total_payroll = sum(e["salary"] for e in employees)
    avg_salary    = total_payroll / len(employees)
    dept_summary  = {}
    for e in employees:
        d = e["dept"]
        if d not in dept_summary:
            dept_summary[d] = {"count": 0, "total": 0}
        dept_summary[d]["count"] += 1
        dept_summary[d]["total"] += e["salary"]

    kpi_cards = [
        {"label": "Total Payroll", "value": _fmt(total_payroll), "status": "good", "icon": "💰"},
        {"label": "Headcount",     "value": str(len(employees)), "status": "good", "icon": "👥"},
        {"label": "Avg Salary",    "value": _fmt(avg_salary),    "status": "good", "icon": "📊"},
        {"label": "Departments",   "value": str(len(dept_summary)), "status": "good", "icon": "🏢"},
    ]

    return {
        "type":      "PAYROLL",
        "kpi_cards": kpi_cards,
        "alerts":    [],
        "summary": {
            "total_payroll": total_payroll, "headcount": len(employees),
            "avg_salary": avg_salary,
        },
        "charts": {
            "by_dept": [{"name": k, "value": v["total"], "count": v["count"]}
                        for k, v in dept_summary.items()],
        }
    }


def analyze_unknown(df_dict, classifier_result):
    scores = classifier_result.get("scores", {})
    top3   = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "type":    "UNKNOWN",
        "kpi_cards": [],
        "suggestions": [{"type": t, "score": s} for t, s in top3 if s > 0],
        "alerts": [{
            "severity": "High",
            "title":    "File Type Not Recognized",
            "icon":     "❓",
            "message":  "Please upload: P&L, Balance Sheet, Fixed Assets, or Payroll file",
        }]
    }


def analyze_file(file_path, classifier_result):
    file_type = classifier_result.get("type", "UNKNOWN")

    df_dict = {}
    try:
        xl = pd.ExcelFile(file_path)
        for sheet in xl.sheet_names:
            df_dict[sheet] = pd.read_excel(file_path, sheet_name=sheet, header=None)
    except Exception as e:
        return {"type": "ERROR", "error": str(e), "kpi_cards": [], "alerts": []}

    if file_type == "P&L":
        from mapping import map_file
        mapped  = map_file(file_path)
        pl      = mapped.get("pl_data") or {}
        summary = pl.get("summary", {})
        items   = pl.get("line_items", [])
        if summary.get("total_revenue", 0) > 0:
            return analyze_pl(df_dict, summary, items)
        return {"type": "P&L", "error": "Could not parse P&L",
                "kpi_cards": [], "alerts": []}

    elif file_type == "FIXED_ASSETS":
        return analyze_fixed_assets(df_dict)

    elif file_type == "BALANCE_SHEET":
        return analyze_balance_sheet(df_dict)

    elif file_type == "PAYROLL":
        return analyze_payroll(df_dict)

    else:
        return analyze_unknown(df_dict, classifier_result)
