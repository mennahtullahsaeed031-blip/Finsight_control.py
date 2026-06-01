"""
analyzers.py — Academic-grade financial analysis
كل نوع ميزانية بيتحلل بالمنطق الأكاديمي الصح (CMA/CPA/CIMA)

Rules:
- Income Statement / P&L فقط → Gross Margin, EBIT, Net Margin
- Cost budgets (Materials, Labor, OH, SG&A) → Cost KPIs فقط، مفيش Profit
- Balance Sheet → Liquidity & Leverage ratios
- Working Capital → DSO, DPO, DIO, CCC
- Fixed Assets → CapEx Utilization, Depreciation
- Cash Flow → Operating/Investing/Financing CF
"""

import pandas as pd
import numpy as np
import math


# ══════════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _to_num(val):
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return None if math.isnan(float(val)) else float(val)
    except:
        pass
    s = str(val).strip().replace(",", "").replace(" ", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        v = float(s)
        return None if math.isnan(v) else v
    except:
        return None


def _fmt(v):
    if v is None:
        return "—"
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 1e6:   return f"{sign}${v/1e6:.2f}M"
    if v >= 1e3:   return f"{sign}${v/1e3:.0f}K"
    return f"{sign}${v:.0f}"


def _find_text_col(df, exclude=None):
    """يلاقي عمود أسماء البنود"""
    best_ci, best_score = 0, -1
    for ci in range(min(5, len(df.columns))):
        if ci == exclude:
            continue
        col = df.iloc[:, ci].fillna("").astype(str).str.strip()
        score = sum(
            1 for v in col
            if len(v) > 2
            and v not in ["nan", "None", "", "-", "—"]
            and _to_num(v) is None
        )
        if score > best_score:
            best_score, best_ci = score, ci
    return best_ci


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


def _find_header_row(df, extra_keywords=None):
    """يلاقي الـ header row"""
    kw = ["q1", "q2", "q3", "q4", "budget", "actual", "last year",
          "next year", "fy", "in '000", "total"]
    if extra_keywords:
        kw += extra_keywords
    best_row, best_score = 0, 0
    for i in range(min(12, len(df))):
        row = df.iloc[i].fillna("").astype(str).str.lower().tolist()
        score = sum(1 for v in row if any(k in v for k in kw))
        if score > best_score:
            best_score, best_row = score, i
    return best_row


def _get_budget_cols(headers, data, acct_col):
    """
    يختار أعمدة الـ Budget (مش Last Year):
    - لو في NaN separator → خد المجموعة التانية
    - يستبعد نسب (avg_abs < 2)
    """
    candidates = []
    for ci, h in enumerate(headers):
        if ci == acct_col:
            continue
        if ci >= len(data.columns):
            continue
        col_nums = [_to_num(str(v)) for v in data.iloc[:, ci]]
        valid = [v for v in col_nums if v is not None]
        if not valid:
            continue
        fill = len(valid) / max(len(data), 1)
        if fill < 0.2:
            continue
        avg = sum(abs(v) for v in valid) / len(valid)
        if avg < 2:
            continue  # نسب مئوية
        candidates.append(ci)

    if not candidates:
        return []

    # لو في gap → خد المجموعة التانية (Budget)
    max_gap, split_at = 0, -1
    for i in range(len(candidates) - 1):
        gap = candidates[i+1] - candidates[i]
        if gap > 1 and gap > max_gap:
            max_gap, split_at = gap, i

    if split_at >= 0:
        return candidates[split_at + 1:]
    return candidates


def _sum_budget_col(data, period_cols, acct_col, target_rows_keywords):
    """يجمع أرقام صفوف معينة من أعمدة Budget"""
    total = 0
    acct_col_data = data.iloc[:, acct_col].fillna("").astype(str).str.lower()
    for ri in range(len(data)):
        label = acct_col_data.iloc[ri]
        if any(kw in label for kw in target_rows_keywords):
            for ci in period_cols:
                if ci < len(data.columns):
                    v = _to_num(str(data.iloc[ri, ci]))
                    if v is not None:
                        total += v
    return total


# ══════════════════════════════════════════════════════════════════════════════
# 1. P&L / INCOME STATEMENT
# الوحيد اللي يحسب فيه Gross Margin, EBIT, Net Margin
# ══════════════════════════════════════════════════════════════════════════════

def analyze_pl(df_dict, summary, line_items):
    """
    Academic P&L analysis:
    Revenue - COGS = Gross Profit
    Gross Profit - SG&A/OpEx = EBIT
    EBIT - Interest - Tax = Net Income
    """
    from kpi import calculate_kpis, format_kpi_card
    kpis      = calculate_kpis(summary, line_items)
    kpi_cards = format_kpi_card(kpis)
    return {
        "type":       "P&L",
        "summary":    summary,
        "line_items": line_items,
        "kpis":       kpis,
        "kpi_cards":  kpi_cards,
        "alerts":     [],
        "insights":   [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. DIRECT MATERIALS BUDGET
# KPIs: Total Material Cost, Cost per Unit, % of Revenue, Fabric/Material Usage
# مفيش Gross Profit — ده cost budget بس
# ══════════════════════════════════════════════════════════════════════════════

def analyze_direct_materials(df_dict):
    total_cost = 0
    items = []

    COST_KW  = ["fabric", "material", "purchase", "cost", "مواد", "شراء"]
    PRICE_KW = ["price", "rate", "سعر"]
    USAGE_KW = ["usage", "quantity", "units", "استخدام", "كمية"]
    SKIP_KW  = ["volume", "production", "% of", "as a %", "revenue", "إيراد",
                "days", "number of"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row = _find_header_row(df)
        headers    = df.iloc[header_row].fillna("").astype(str).tolist()
        data       = df.iloc[header_row + 1:].reset_index(drop=True)
        acct_col   = _find_text_col(data)
        period_cols = _get_budget_cols(headers, data, acct_col)

        if not period_cols:
            continue

        for _, row in data.iterrows():
            name = str(row.iloc[acct_col]).strip() if acct_col < len(row) else ""
            if not name or name.lower() in ["nan", "none", "", "-", "—"]:
                continue
            if any(k in name.lower() for k in SKIP_KW):
                continue
            if not any(k in name.lower() for k in COST_KW):
                continue

            values = {}
            for ci in period_cols:
                if ci < len(row):
                    v = _to_num(str(row.iloc[ci]))
                    if v is not None:
                        values[headers[ci]] = v

            if not values:
                continue

            item_total = sum(values.values())
            total_cost += abs(item_total)
            items.append({
                "name":    name,
                "total":   item_total,
                "values":  values,
                "is_cost": True,
            })

    if not items:
        return {
            "type": "DIRECT_MATERIALS",
            "kpi_cards": [],
            "alerts": [],
            "insights": [{"icon": "⚠️", "text": "Could not extract material cost items"}],
            "charts": {},
        }

    # KPIs: Total Cost, by Product, Variance
    by_product = {}
    for item in items:
        k = item["name"]
        by_product[k] = by_product.get(k, 0) + abs(item["total"])

    kpi_cards = [
        {"label": "Total Material Cost",  "value": _fmt(total_cost),
         "status": "good", "icon": "🧵"},
        {"label": "Products / Materials", "value": str(len(by_product)),
         "status": "good", "icon": "📦"},
        {"label": "Avg Cost / Item",
         "value": _fmt(total_cost / len(by_product)) if by_product else "—",
         "status": "good", "icon": "📊"},
    ]

    insights = [
        {"icon": "📋",
         "text": f"Direct Materials budget covers {len(by_product)} material lines totaling {_fmt(total_cost)}"},
        {"icon": "💡",
         "text": "This is a COST budget — no revenue or profit metrics apply here"},
    ]

    alerts = []
    for name, cost in sorted(by_product.items(), key=lambda x: -x[1])[:3]:
        pct = cost / total_cost * 100 if total_cost else 0
        if pct > 40:
            alerts.append({
                "severity": "High",
                "title":    f"High concentration: {name}",
                "message":  f"{pct:.1f}% of total material cost",
                "icon":     "⚠️",
            })

    return {
        "type":      "DIRECT_MATERIALS",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  insights,
        "summary":   {"total_cost": total_cost},
        "charts": {
            "by_category": [{"name": k, "value": v} for k, v in by_product.items()],
            "top_assets":  sorted(items, key=lambda x: abs(x["total"]), reverse=True)[:8],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. PRODUCTION OVERHEADS BUDGET
# KPIs: Total OH Cost, Fixed vs Variable OH, OH Rate per Unit
# مفيش P&L هنا
# ══════════════════════════════════════════════════════════════════════════════

def analyze_overheads(df_dict):
    fixed_oh = variable_oh = total_oh = 0
    items = []

    FIXED_KW    = ["rent", "indirect labor", "indirect person", "fixed", "إيجار", "ثابت"]
    VARIABLE_KW = ["utility", "variable", "maintenance", "متغير", "صيانة"]
    SKIP_KW     = ["volume", "production", "% of", "as a %", "revenue",
                   "number of", "average", "rate", "days", "إيراد"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row  = _find_header_row(df)
        headers     = df.iloc[header_row].fillna("").astype(str).tolist()
        data        = df.iloc[header_row + 1:].reset_index(drop=True)
        acct_col    = _find_text_col(data)
        period_cols = _get_budget_cols(headers, data, acct_col)

        if not period_cols:
            continue

        for _, row in data.iterrows():
            name = str(row.iloc[acct_col]).strip() if acct_col < len(row) else ""
            if not name or name.lower() in ["nan", "none", "", "-", "—"]:
                continue
            if any(k in name.lower() for k in SKIP_KW):
                continue

            values = {}
            for ci in period_cols:
                if ci < len(row):
                    v = _to_num(str(row.iloc[ci]))
                    if v is not None:
                        values[headers[ci]] = v
            if not values:
                continue

            item_total = sum(values.values())
            if item_total == 0:
                continue

            is_fixed    = any(k in name.lower() for k in FIXED_KW)
            is_variable = any(k in name.lower() for k in VARIABLE_KW)

            items.append({
                "name":      name,
                "total":     item_total,
                "oh_type":   "Fixed" if is_fixed else "Variable" if is_variable else "Other",
                "values":    values,
            })
            total_oh += abs(item_total)
            if is_fixed:    fixed_oh    += abs(item_total)
            elif is_variable: variable_oh += abs(item_total)

    if not items:
        return {
            "type": "OVERHEADS",
            "kpi_cards": [],
            "alerts": [],
            "insights": [{"icon": "⚠️", "text": "Could not extract overhead cost items"}],
            "charts": {},
        }

    fixed_pct    = fixed_oh    / total_oh * 100 if total_oh else 0
    variable_pct = variable_oh / total_oh * 100 if total_oh else 0

    kpi_cards = [
        {"label": "Total Overhead Cost", "value": _fmt(total_oh),
         "status": "good", "icon": "🏭"},
        {"label": "Fixed Overhead",
         "value": f"{_fmt(fixed_oh)} ({fixed_pct:.0f}%)",
         "status": "good", "icon": "🔒"},
        {"label": "Variable Overhead",
         "value": f"{_fmt(variable_oh)} ({variable_pct:.0f}%)",
         "status": "good", "icon": "📈"},
        {"label": "OH Items", "value": str(len(items)),
         "status": "good", "icon": "📋"},
    ]

    insights = [
        {"icon": "📊",
         "text": f"Fixed OH is {fixed_pct:.0f}% of total — {'high operating leverage' if fixed_pct > 70 else 'balanced structure'}"},
        {"icon": "💡",
         "text": "This is a COST budget — no gross margin or profit applies"},
    ]

    alerts = []
    if fixed_pct > 85:
        alerts.append({
            "severity": "High",
            "title":    "Very High Fixed OH Concentration",
            "message":  f"{fixed_pct:.0f}% fixed costs — risk in low-volume periods",
            "icon":     "⚠️",
        })

    return {
        "type":      "OVERHEADS",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  insights,
        "summary":   {
            "total_oh": total_oh, "fixed_oh": fixed_oh,
            "variable_oh": variable_oh, "fixed_pct": fixed_pct,
        },
        "charts": {
            "by_category": [
                {"name": "Fixed OH",    "value": fixed_oh},
                {"name": "Variable OH", "value": variable_oh},
            ],
            "top_assets": sorted(items, key=lambda x: abs(x["total"]), reverse=True)[:8],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. SG&A BUDGET
# KPIs: Total SG&A, by category, % of Revenue (reference only — not P&L)
# Revenue هنا بس reference للنسب، مش P&L
# ══════════════════════════════════════════════════════════════════════════════

def analyze_sga(df_dict):
    total_sga = 0
    ref_revenue = 0
    items = []

    EXPENSE_KW = ["commission", "transport", "external", "payroll", "rent",
                  "marketing", "advertising", "admin", "expense", "sga", "sg&a",
                  "عمولة", "نقل", "رواتب", "إيجار", "تسويق"]
    SKIP_KW    = ["% of", "as a %", "driver", "days", "volume",
                  "revenue", "إيراد", "sales volume"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row  = _find_header_row(df)
        headers     = df.iloc[header_row].fillna("").astype(str).tolist()
        data        = df.iloc[header_row + 1:].reset_index(drop=True)
        acct_col    = _find_text_col(data)
        period_cols = _get_budget_cols(headers, data, acct_col)

        if not period_cols:
            continue

        for _, row in data.iterrows():
            name = str(row.iloc[acct_col]).strip() if acct_col < len(row) else ""
            if not name or name.lower() in ["nan", "none", "", "-", "—"]:
                continue
            name_lower = name.lower()

            # Revenue row → مش expense، بس نأخذها كـ reference
            if "revenue" in name_lower and "as a %" not in name_lower:
                for ci in period_cols:
                    v = _to_num(str(row.iloc[ci])) if ci < len(row) else None
                    if v and v > 0:
                        ref_revenue += v
                continue

            if any(k in name_lower for k in SKIP_KW):
                continue

            values = {}
            for ci in period_cols:
                if ci < len(row):
                    v = _to_num(str(row.iloc[ci]))
                    if v is not None:
                        values[headers[ci]] = v
            if not values:
                continue

            item_total = sum(values.values())
            if item_total == 0:
                continue

            # SG&A items دايماً مصاريف (سالبة أو بنأخذ absolute value)
            items.append({
                "name":   name,
                "total":  item_total,
                "values": values,
            })
            total_sga += abs(item_total)

    if not items:
        return {
            "type": "SGA",
            "kpi_cards": [],
            "alerts": [],
            "insights": [{"icon": "⚠️", "text": "Could not extract SG&A items"}],
            "charts": {},
        }

    # % of Revenue كـ reference metric (مش P&L)
    sga_pct = total_sga / ref_revenue * 100 if ref_revenue > 0 else 0
    by_item = {i["name"]: abs(i["total"]) for i in items}

    kpi_cards = [
        {"label": "Total SG&A Cost",    "value": _fmt(total_sga),
         "status": "good", "icon": "💼"},
        {"label": "SG&A % of Revenue",
         "value": f"{sga_pct:.1f}%" if ref_revenue > 0 else "—",
         "status": "good" if sga_pct < 25 else "warning" if sga_pct < 40 else "critical",
         "icon":  "📊"},
        {"label": "Expense Lines",      "value": str(len(items)),
         "status": "good", "icon": "📋"},
    ]

    insights = [
        {"icon": "📊",
         "text": f"SG&A totals {_fmt(total_sga)}"
                 + (f", representing {sga_pct:.1f}% of revenue" if ref_revenue else "")},
        {"icon": "💡",
         "text": "SG&A is an EXPENSE budget — Gross Margin & Net Income are NOT calculated here"},
    ]

    alerts = []
    if sga_pct > 35:
        alerts.append({
            "severity": "High",
            "title":    "High SG&A Ratio",
            "message":  f"SG&A is {sga_pct:.1f}% of revenue — review cost efficiency",
            "icon":     "⚠️",
        })

    return {
        "type":      "SGA",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  insights,
        "summary":   {
            "total_sga": total_sga, "ref_revenue": ref_revenue, "sga_pct": sga_pct,
        },
        "charts": {
            "by_category": [{"name": k, "value": v} for k, v in by_item.items()],
            "top_assets":  sorted(items, key=lambda x: abs(x["total"]), reverse=True)[:8],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. FIXED ASSETS / CAPEX BUDGET
# KPIs: Opening PP&E, Additions, Depreciation, Closing PP&E, CapEx % Revenue
# ══════════════════════════════════════════════════════════════════════════════

def analyze_fixed_assets(df_dict):
    total_capex = total_depreciation = closing_ppe = opening_ppe = 0
    items       = []

    CAPEX_KW = ["purchase", "addition", "capex", "capital", "شراء", "إضافة"]
    DEP_KW   = ["depreciation", "dep", "استهلاك"]
    PPE_KW   = ["pp&e", "property", "plant", "equipment", "ppe", "opening",
                "closing", "أصول ثابتة"]
    REV_KW   = ["revenue", "إيراد"]
    SKIP_KW  = ["% of", "as a %", "days"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row  = _find_header_row(df)
        headers     = df.iloc[header_row].fillna("").astype(str).tolist()
        data        = df.iloc[header_row + 1:].reset_index(drop=True)
        acct_col    = _find_text_col(data)
        period_cols = _get_budget_cols(headers, data, acct_col)

        if not period_cols:
            continue

        for _, row in data.iterrows():
            name = str(row.iloc[acct_col]).strip() if acct_col < len(row) else ""
            if not name or name.lower() in ["nan", "none", "", "-", "—"]:
                continue
            name_lower = name.lower()
            if any(k in name_lower for k in SKIP_KW + REV_KW):
                continue

            values = {}
            for ci in period_cols:
                if ci < len(row):
                    v = _to_num(str(row.iloc[ci]))
                    if v is not None:
                        values[headers[ci]] = v
            if not values:
                continue

            item_total = sum(values.values())

            if any(k in name_lower for k in CAPEX_KW):
                total_capex += abs(item_total)
            elif any(k in name_lower for k in DEP_KW):
                total_depreciation += abs(item_total)
            elif "closing" in name_lower or "end" in name_lower:
                closing_ppe = abs(list(values.values())[-1]) if values else 0
            elif "opening" in name_lower or "begin" in name_lower:
                opening_ppe = abs(list(values.values())[0]) if values else 0

            items.append({
                "name":   name,
                "budget": abs(item_total),
                "actual": abs(item_total),
                "total":  item_total,
                "values": values,
            })

    if not items:
        return {
            "type": "FIXED_ASSETS", "kpi_cards": [], "alerts": [],
            "insights": [{"icon": "⚠️", "text": "Could not extract fixed asset data"}],
            "charts": {},
        }

    net_investment = total_capex - total_depreciation

    kpi_cards = [
        {"label": "Total CapEx",       "value": _fmt(total_capex),
         "status": "good", "icon": "🏗️"},
        {"label": "Total Depreciation","value": _fmt(total_depreciation),
         "status": "good", "icon": "📉"},
        {"label": "Net Investment",    "value": _fmt(net_investment),
         "status": "good" if net_investment > 0 else "warning", "icon": "📊"},
        {"label": "Closing PP&E",      "value": _fmt(closing_ppe) if closing_ppe else _fmt(total_capex),
         "status": "good", "icon": "🏦"},
    ]

    insights = [
        {"icon": "🏗️",
         "text": f"CapEx budget: {_fmt(total_capex)} | Depreciation: {_fmt(total_depreciation)} | Net: {_fmt(net_investment)}"},
        {"icon": "💡",
         "text": "Fixed Assets budget tracks PP&E movement — no P&L metrics apply"},
    ]

    alerts = []
    if total_depreciation > total_capex:
        alerts.append({
            "severity": "High",
            "title":    "Asset Base Shrinking",
            "message":  f"Depreciation ({_fmt(total_depreciation)}) > CapEx ({_fmt(total_capex)}) — net disinvestment",
            "icon":     "📉",
        })

    return {
        "type":      "FIXED_ASSETS",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  insights,
        "summary": {
            "total_budget": total_capex, "total_actual": total_capex,
            "total_depreciation": total_depreciation,
            "utilization_rate": 100,
        },
        "charts": {
            "by_category": [
                {"name": "CapEx Additions", "value": total_capex},
                {"name": "Depreciation",    "value": total_depreciation},
            ],
            "top_assets": sorted(items, key=lambda x: abs(x["total"]), reverse=True)[:8],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. WORKING CAPITAL BUDGET
# KPIs: DSO, DPO, DIO, CCC, AR, AP, Inventory
# الـ Revenue وCOGS هنا بس لحساب النسب — مش P&L
# ══════════════════════════════════════════════════════════════════════════════

def analyze_working_capital(df_dict):
    dso = dpo = dio = 0
    ar = ap = inventory = wc = 0
    ref_revenue = ref_cogs = 0

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row  = _find_header_row(df)
        headers     = df.iloc[header_row].fillna("").astype(str).tolist()
        data        = df.iloc[header_row + 1:].reset_index(drop=True)
        acct_col    = _find_text_col(data)
        period_cols = _get_budget_cols(headers, data, acct_col)

        if not period_cols:
            continue

        for _, row in data.iterrows():
            name = str(row.iloc[acct_col]).strip() if acct_col < len(row) else ""
            nl   = name.lower()
            if not name or nl in ["nan", "none", "", "-", "—"]:
                continue

            # خذ آخر قيمة (Q4/FY)
            last_val = None
            avg_val  = 0
            count    = 0
            for ci in period_cols:
                if ci < len(row):
                    v = _to_num(str(row.iloc[ci]))
                    if v is not None:
                        last_val = v
                        avg_val += v
                        count   += 1
            avg_val = avg_val / count if count else 0

            if "revenue" in nl and "% of" not in nl:
                ref_revenue = abs(avg_val) if avg_val else 0
            elif "cost of goods" in nl or "cogs" in nl:
                ref_cogs    = abs(avg_val) if avg_val else 0
            elif "accounts receiv" in nl:
                ar          = abs(avg_val) if avg_val else 0
            elif "accounts payab" in nl:
                ap          = abs(avg_val) if avg_val else 0
            elif "inventory" in nl and "days" not in nl:
                inventory   = abs(avg_val) if avg_val else 0
            elif "days of sales" in nl or "dso" in nl:
                dso         = abs(avg_val) if avg_val else 0
            elif "days of payab" in nl or "dpo" in nl:
                dpo         = abs(avg_val) if avg_val else 0
            elif "days of invent" in nl or "dio" in nl or "days of inv" in nl:
                dio         = abs(avg_val) if avg_val else 0
            elif "working capital" in nl and "budget" not in nl:
                wc          = avg_val if avg_val else 0
            elif "cash conversion" in nl:
                pass  # CCC = DSO + DIO - DPO

    # حساب CCC
    ccc = dso + dio - dpo

    # حساب WC لو مش موجود
    if wc == 0 and (ar + inventory - ap) != 0:
        wc = ar + inventory - ap

    kpi_cards = [
        {"label": "Days Sales Outstanding (DSO)",
         "value": f"{dso:.0f} days",
         "status": "good" if dso <= 30 else "warning" if dso <= 60 else "critical",
         "icon":  "📥"},
        {"label": "Days Payable Outstanding (DPO)",
         "value": f"{dpo:.0f} days",
         "status": "good" if dpo >= 30 else "warning",
         "icon":  "📤"},
        {"label": "Days Inventory Outstanding (DIO)",
         "value": f"{dio:.0f} days",
         "status": "good" if dio <= 30 else "warning" if dio <= 60 else "critical",
         "icon":  "📦"},
        {"label": "Cash Conversion Cycle (CCC)",
         "value": f"{ccc:.0f} days",
         "status": "good" if ccc <= 30 else "warning" if ccc <= 60 else "critical",
         "icon":  "🔄"},
        {"label": "Accounts Receivable",  "value": _fmt(ar),
         "status": "good", "icon": "💰"},
        {"label": "Working Capital",      "value": _fmt(wc),
         "status": "good" if wc > 0 else "critical", "icon": "⚡"},
    ]

    insights = [
        {"icon": "🔄",
         "text": f"CCC = DSO({dso:.0f}) + DIO({dio:.0f}) - DPO({dpo:.0f}) = {ccc:.0f} days"},
        {"icon": "💡",
         "text": "Working Capital budget measures liquidity efficiency — no P&L metrics"},
    ]

    alerts = []
    if ccc > 60:
        alerts.append({
            "severity": "High",
            "title":    f"High Cash Conversion Cycle: {ccc:.0f} days",
            "message":  "Long CCC ties up cash — consider improving collections or extending payables",
            "icon":     "🚨",
        })
    if dso > 45:
        alerts.append({
            "severity": "Medium",
            "title":    f"High DSO: {dso:.0f} days",
            "message":  "Slow customer collections — review credit policy",
            "icon":     "⚠️",
        })

    return {
        "type":      "WORKING_CAPITAL",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  insights,
        "summary": {
            "dso": dso, "dpo": dpo, "dio": dio, "ccc": ccc,
            "ar": ar, "ap": ap, "inventory": inventory, "working_capital": wc,
        },
        "charts": {
            "structure": [
                {"name": "Receivables (AR)", "value": ar,        "color": "#06B6D4"},
                {"name": "Inventory",        "value": inventory,  "color": "#F59E0B"},
                {"name": "Payables (AP)",    "value": ap,         "color": "#EF4444"},
            ],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. BALANCE SHEET BUDGET
# KPIs: Current Ratio, Quick Ratio, D/E Ratio, Equity
# ══════════════════════════════════════════════════════════════════════════════

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
            label = str(row.iloc[text_col] if text_col < len(row) else "").lower().strip()
            val   = _to_num(str(row.iloc[num_col] if num_col < len(row) else "")) or 0
            if any(x in label for x in ["total assets",    "أصول إجمالية"]):
                total_assets       = val or total_assets
            if any(x in label for x in ["total liab",      "إجمالي الخصوم"]):
                total_liabilities  = val or total_liabilities
            if any(x in label for x in ["equity", "shareholders", "حقوق ملكية"]):
                total_equity       = val or total_equity
            if any(x in label for x in ["current assets",  "أصول متداولة"]):
                current_assets     = val or current_assets
            if any(x in label for x in ["current liab",    "خصوم متداولة"]):
                current_liabilities = val or current_liabilities

    if total_assets == 0:
        return {
            "type": "BALANCE_SHEET", "kpi_cards": [], "alerts": [],
            "insights": [{"icon": "⚠️", "text": "Could not extract balance sheet data"}],
            "charts": {},
        }

    current_ratio   = current_assets / current_liabilities if current_liabilities else 0
    debt_to_equity  = total_liabilities / total_equity     if total_equity         else 0
    working_capital = current_assets - current_liabilities

    kpi_cards = [
        {"label": "Total Assets",      "value": _fmt(total_assets),
         "status": "good", "icon": "🏦"},
        {"label": "Total Liabilities", "value": _fmt(total_liabilities),
         "status": "good" if total_liabilities < total_assets else "warning", "icon": "📋"},
        {"label": "Total Equity",      "value": _fmt(total_equity),
         "status": "good" if total_equity > 0 else "critical", "icon": "💰"},
        {"label": "Current Ratio",
         "value": f"{current_ratio:.2f}x",
         "status": "good" if current_ratio >= 1.5 else "warning" if current_ratio >= 1 else "critical",
         "icon":  "⚡"},
        {"label": "Debt-to-Equity",
         "value": f"{debt_to_equity:.2f}x",
         "status": "good" if debt_to_equity < 1 else "warning" if debt_to_equity < 2 else "critical",
         "icon":  "📊"},
        {"label": "Working Capital",   "value": _fmt(working_capital),
         "status": "good" if working_capital > 0 else "critical", "icon": "💵"},
    ]

    alerts = []
    if current_ratio < 1:
        alerts.append({"severity": "Critical", "title": "Liquidity Risk",
                       "icon": "🚨",
                       "message": f"Current ratio {current_ratio:.2f}x — below 1.0"})
    if debt_to_equity > 2:
        alerts.append({"severity": "High", "title": "High Financial Leverage",
                       "icon": "⚠️",
                       "message": f"D/E ratio {debt_to_equity:.2f}x — high leverage risk"})

    return {
        "type":      "BALANCE_SHEET",
        "kpi_cards": kpi_cards,
        "alerts":    alerts,
        "insights":  [
            {"icon": "🏦", "text": f"Assets = {_fmt(total_assets)} | Liabilities = {_fmt(total_liabilities)} | Equity = {_fmt(total_equity)}"},
            {"icon": "💡", "text": "Balance Sheet shows financial position — no income metrics here"},
        ],
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
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8. PAYROLL BUDGET
# ══════════════════════════════════════════════════════════════════════════════

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
            row = df.iloc[i].fillna("").astype(str).str.lower().tolist()
            if any(any(kw in v for kw in SALARY_KW + NAME_KW) for v in row):
                header_row = i
                break
        headers  = df.iloc[header_row].fillna("").astype(str).tolist()
        data     = df.iloc[header_row + 1:].reset_index(drop=True)
        name_col   = _find_col_by_keywords(headers, NAME_KW)
        salary_col = _find_col_by_keywords(headers, SALARY_KW)
        dept_col   = _find_col_by_keywords(headers, DEPT_KW)
        if salary_col is None:
            continue
        for _, row in data.iterrows():
            salary = _to_num(str(row.iloc[salary_col]) if salary_col < len(row) else "")
            if not salary:
                continue
            employees.append({
                "name":   str(row.iloc[name_col]   if name_col   is not None and name_col   < len(row) else "N/A").strip(),
                "salary": salary,
                "dept":   str(row.iloc[dept_col]   if dept_col   is not None and dept_col   < len(row) else "Other").strip(),
            })

    if not employees:
        return {"type": "PAYROLL", "kpi_cards": [], "alerts": [], "charts": {}}

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
        {"label": "Total Payroll",  "value": _fmt(total_payroll), "status": "good", "icon": "💰"},
        {"label": "Headcount",      "value": str(len(employees)), "status": "good", "icon": "👥"},
        {"label": "Avg Salary",     "value": _fmt(avg_salary),    "status": "good", "icon": "📊"},
        {"label": "Departments",    "value": str(len(dept_summary)), "status": "good", "icon": "🏢"},
    ]
    return {
        "type": "PAYROLL", "kpi_cards": kpi_cards, "alerts": [],
        "summary": {"total_payroll": total_payroll, "headcount": len(employees), "avg_salary": avg_salary},
        "charts": {
            "by_dept": [{"name": k, "value": v["total"], "count": v["count"]}
                        for k, v in dept_summary.items()],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. CASH FLOW BUDGET
# ══════════════════════════════════════════════════════════════════════════════

def analyze_cash_flow(df_dict):
    operating = investing = financing = 0
    OP_KW  = ["operating", "operations", "تشغيلية"]
    INV_KW = ["investing", "investment", "استثمارية"]
    FIN_KW = ["financing", "finance", "تمويلية"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        text_col = _find_text_col(df)
        num_col  = _find_first_num_col(df, text_col)
        if text_col is None or num_col is None:
            continue
        for _, row in df.iterrows():
            label = str(row.iloc[text_col] if text_col < len(row) else "").lower().strip()
            val   = _to_num(str(row.iloc[num_col] if num_col < len(row) else "")) or 0
            if any(x in label for x in OP_KW):   operating += val
            elif any(x in label for x in INV_KW): investing += val
            elif any(x in label for x in FIN_KW): financing += val

    net_cash = operating + investing + financing
    kpi_cards = [
        {"label": "Operating CF", "value": _fmt(operating),
         "status": "good" if operating > 0 else "critical", "icon": "⚙️"},
        {"label": "Investing CF", "value": _fmt(investing),
         "status": "warning", "icon": "📈"},
        {"label": "Financing CF", "value": _fmt(financing),
         "status": "warning", "icon": "🏦"},
        {"label": "Net Cash Flow","value": _fmt(net_cash),
         "status": "good" if net_cash > 0 else "critical", "icon": "💵"},
    ]
    alerts = []
    if operating < 0:
        alerts.append({"severity": "Critical", "title": "Negative Operating CF",
                       "icon": "🚨",
                       "message": f"Operating CF = {_fmt(operating)} — liquidity risk"})
    return {
        "type": "CASH_FLOW", "kpi_cards": kpi_cards, "alerts": alerts,
        "summary": {"operating": operating, "investing": investing,
                    "financing": financing, "net_cash": net_cash},
        "charts": {
            "structure": [
                {"name": "Operating", "value": abs(operating), "color": "#10B981"},
                {"name": "Investing", "value": abs(investing), "color": "#3B82F6"},
                {"name": "Financing", "value": abs(financing), "color": "#8B5CF6"},
            ]
        },
        "insights": [
            {"icon": "✅" if net_cash > 0 else "🚨",
             "text": f"Net cash flow: {_fmt(net_cash)}"}
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 10. GENERAL BUDGET (fallback)
# ══════════════════════════════════════════════════════════════════════════════

def analyze_budget(df_dict, classifier_result=None):
    line_items   = []
    total_budget = total_actual = 0
    BUDGET_KW = ["budget", "plan", "allocated", "target", "مخطط", "ميزانية", "مستهدف"]
    ACTUAL_KW = ["actual", "spent", "realized", "فعلي", "منصرف", "محقق"]

    for sheet_name, df in df_dict.items():
        if df is None or df.empty:
            continue
        header_row  = _find_header_row(df)
        headers     = df.iloc[header_row].fillna("").astype(str).tolist()
        data        = df.iloc[header_row + 1:].reset_index(drop=True)
        name_col    = _find_text_col(data)
        budget_col  = _find_col_by_keywords(headers, BUDGET_KW)
        actual_col  = _find_col_by_keywords(headers, ACTUAL_KW)
        cat_col     = _find_col_by_keywords(headers, ["category", "type", "section", "نوع", "بند"])

        if budget_col is None:
            period_cols = _get_budget_cols(headers, data, name_col)
            if period_cols:
                budget_col = period_cols[-1]

        for _, row in data.iterrows():
            name = str(row.iloc[name_col]).strip() if name_col is not None and name_col < len(row) else ""
            if not name or name.lower() in ["nan", "none", "", "-", "—"]:
                continue
            if any(x in name.lower() for x in ["total", "subtotal", "grand", "مجموع", "إجمالي"]):
                continue
            budget = _to_num(str(row.iloc[budget_col])) if budget_col is not None and budget_col < len(row) else None
            actual = _to_num(str(row.iloc[actual_col])) if actual_col is not None and actual_col < len(row) else None
            cat    = str(row.iloc[cat_col]).strip() if cat_col is not None and cat_col < len(row) else "General"
            if budget is None and actual is None:
                continue
            budget = budget or 0
            actual = actual or 0
            variance = actual - budget
            variance_pct = variance / budget * 100 if budget else 0
            line_items.append({"name": name, "category": cat, "budget": budget,
                               "actual": actual, "variance": variance,
                               "variance_pct": variance_pct, "favorable": variance < 0})
            total_budget += budget
            total_actual += actual

    if not line_items:
        return {"type": "BUDGET", "kpi_cards": [], "alerts": [],
                "insights": [{"icon": "⚠️", "text": "Could not extract budget line items"}], "charts": {}}

    total_variance = total_actual - total_budget
    variance_pct   = total_variance / total_budget * 100 if total_budget else 0
    utilization    = total_actual / total_budget * 100 if total_budget else 0
    over_items     = [i for i in line_items if i["variance"] > 0 and i["budget"] > 0]

    kpi_cards = [
        {"label": "Total Budget",      "value": _fmt(total_budget), "status": "good", "icon": "📋"},
        {"label": "Total Actual",      "value": _fmt(total_actual),
         "status": "good" if utilization <= 100 else "warning", "icon": "💰"},
        {"label": "Total Variance",    "value": f"{variance_pct:+.1f}%",
         "status": "good" if abs(variance_pct) <= 5 else "warning" if abs(variance_pct) <= 15 else "critical",
         "icon":  "📊"},
        {"label": "Over Budget Items", "value": str(len(over_items)),
         "status": "critical" if over_items else "good", "icon": "⚠️"},
        {"label": "Utilization",       "value": f"{utilization:.1f}%",
         "status": "good" if 85 <= utilization <= 105 else "warning", "icon": "📈"},
        {"label": "Line Items",        "value": str(len(line_items)), "status": "good", "icon": "🗂️"},
    ]
    alerts = []
    for item in sorted(over_items, key=lambda x: x["variance_pct"], reverse=True)[:5]:
        alerts.append({"severity": "Critical" if item["variance_pct"] > 20 else "High",
                       "title": f"Over Budget: {item['name']}",
                       "message": f"Actual {_fmt(item['actual'])} vs Budget {_fmt(item['budget'])} ({item['variance_pct']:+.1f}%)",
                       "icon": "🔴"})
    cat_summary = {}
    for item in line_items:
        c = item["category"]
        cat_summary[c] = cat_summary.get(c, {"budget": 0, "actual": 0})
        cat_summary[c]["budget"] += item["budget"]
        cat_summary[c]["actual"] += item["actual"]

    return {
        "type": "BUDGET", "kpi_cards": kpi_cards, "alerts": alerts,
        "insights": [{"icon": "✅" if abs(variance_pct) <= 5 else "⚠️",
                      "text": f"Budget variance: {variance_pct:+.1f}%"}],
        "summary": {"total_budget": total_budget, "total_actual": total_actual,
                    "total_variance": total_variance, "variance_pct": variance_pct},
        "charts": {
            "by_category": [{"name": k, "value": v["budget"], "actual": v["actual"]}
                            for k, v in cat_summary.items()],
            "top_assets": sorted(line_items, key=lambda x: abs(x["variance"]), reverse=True)[:8],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 11. UNKNOWN
# ══════════════════════════════════════════════════════════════════════════════

def analyze_unknown(df_dict, classifier_result):
    scores = classifier_result.get("scores", {})
    top3   = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "type": "UNKNOWN", "kpi_cards": [],
        "suggestions": [{"type": t, "score": s} for t, s in top3 if s > 0],
        "alerts": [{"severity": "High", "title": "File Type Not Recognized", "icon": "❓",
                    "message": "Supported: P&L · Balance Sheet · Fixed Assets · Payroll · Cash Flow · Budget · Materials · Overheads · SG&A · Working Capital"}],
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER — يوجه كل ملف للـ analyzer الصح
# ══════════════════════════════════════════════════════════════════════════════

def analyze_file(file_path, classifier_result):
    file_type = classifier_result.get("type", "UNKNOWN")

    df_dict = {}
    try:
        xl = pd.ExcelFile(file_path)
        for sheet in xl.sheet_names:
            try:
                df_dict[sheet] = pd.read_excel(file_path, sheet_name=sheet, header=None)
            except:
                pass
    except Exception as e:
        return {"type": "ERROR", "error": str(e), "kpi_cards": [], "alerts": []}

    # جرب P&L أولاً — بس لو mapping لاقت Income Statement حقيقي
    from mapping import map_file
    mapped  = map_file(file_path)
    pl      = mapped.get("pl_data") or {}
    summary = pl.get("summary", {})
    items   = pl.get("line_items", [])

    if summary.get("total_revenue", 0) > 0 and summary.get("total_cogs", 0) > 0:
        # P&L حقيقي فيه Revenue و COGS
        result = analyze_pl(df_dict, summary, items)
        result["original_type"] = file_type
        return result

    # راوت حسب نوع الملف
    sheet_names_lower = [s.lower() for s in df_dict.keys()]

    # Direct Materials
    if file_type == "DIRECT_MATERIALS" or any("direct material" in s for s in sheet_names_lower):
        return analyze_direct_materials(df_dict)

    # Overheads
    if file_type == "OVERHEADS" or any("overhead" in s or "overheads" == s for s in sheet_names_lower):
        return analyze_overheads(df_dict)

    # SG&A
    if file_type == "SGA" or any(s in ["sg&a", "sga", "sga expense", "sg&a expense"] for s in sheet_names_lower):
        return analyze_sga(df_dict)

    # Fixed Assets
    if file_type == "FIXED_ASSETS" or any("fixed asset" in s for s in sheet_names_lower):
        return analyze_fixed_assets(df_dict)

    # Working Capital
    if file_type == "WORKING_CAPITAL" or any("working capital" in s for s in sheet_names_lower):
        return analyze_working_capital(df_dict)

    # Balance Sheet
    if file_type == "BALANCE_SHEET" or any("balance sheet" in s for s in sheet_names_lower):
        return analyze_balance_sheet(df_dict)

    # Cash Flow
    if file_type == "CASH_FLOW" or any("cash flow" in s for s in sheet_names_lower):
        return analyze_cash_flow(df_dict)

    # Payroll
    if file_type == "PAYROLL" or any("payroll" in s for s in sheet_names_lower):
        return analyze_payroll(df_dict)

    # Loan
    if file_type == "LOAN":
        return analyze_budget(df_dict, classifier_result)

    # General Budget (fallback)
    if file_type == "BUDGET":
        return analyze_budget(df_dict, classifier_result)

    return analyze_unknown(df_dict, classifier_result)
