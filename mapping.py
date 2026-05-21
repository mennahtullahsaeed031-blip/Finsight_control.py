

import pandas as pd
import numpy as np
import re


REVENUE_KEYWORDS = [
    "revenue", "sales", "income", "turnover", "receipts", "earnings",
    "net sales", "gross sales", "total sales", "total revenue",
    "service revenue", "product revenue", "fee", "fees", "billing",
    "إيراد", "مبيعات", "دخل", "إيرادات", "مبيعات صافية",
]
COGS_KEYWORDS = [
    "cogs", "cost of goods", "cost of sales", "cost of revenue",
    "direct cost", "direct costs", "cost of service", "cost of services",
    "material cost", "materials", "production cost", "manufacturing",
    "تكلفة المبيعات", "تكلفة البضاعة", "تكلفة الخدمات", "تكلفة مباشرة",
]
OPEX_KEYWORDS = [
    "operating", "salary", "salaries", "wages", "payroll", "compensation",
    "rent", "utilities", "electricity", "water", "insurance",
    "marketing", "advertising", "promotion", "sales & marketing",
    "r&d", "research", "development", "research and development",
    "admin", "g&a", "general", "administrative", "management",
    "depreciation", "amortization", "d&a",
    "travel", "training", "software", "subscription", "office",
    "مصاريف", "رواتب", "إيجار", "تسويق", "إدارية", "تشغيلية",
    "استهلاك", "مصروف",
]
NONOP_KEYWORDS = [
    "interest", "interest expense", "interest income",
    "tax", "income tax", "tax expense", "zakat",
    "extraordinary", "other income", "other expense",
    "gain", "loss", "forex", "exchange",
    "فائدة", "ضريبة", "زكاة", "أرباح أخرى", "خسائر أخرى",
]

MONTH_PATTERNS = [
    r'\bjan\w*\b', r'\bfeb\w*\b', r'\bmar\w*\b', r'\bapr\w*\b',
    r'\bmay\b',    r'\bjun\w*\b', r'\bjul\w*\b', r'\baug\w*\b',
    r'\bsep\w*\b', r'\boct\w*\b', r'\bnov\w*\b', r'\bdec\w*\b',
    r'\bq[1-4]\b', r'\bquarter\s*[1-4]\b',
    r'\b(19|20)\d{2}\b',
    r'\b(يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر)\b',
]

def classify_account(name: str) -> str:
    """تصنيف ذكي — بيجرب أكتر من طريقة"""
    n = str(name).lower().strip()
    
    # أولاً: exact match أو contains
    if any(k in n for k in REVENUE_KEYWORDS):
        return "Revenue"
    if any(k in n for k in COGS_KEYWORDS):
        return "COGS"
    if any(k in n for k in NONOP_KEYWORDS):
        return "Non-Operating"
    if any(k in n for k in OPEX_KEYWORDS):
        return "OpEx"
    
    if "total" in n or "subtotal" in n or "مجموع" in n or "إجمالي" in n:
        return "Total"
    
    
    return "Other"

def detect_actual_budget(col_name: str) -> str:
    c = str(col_name).lower()
    if any(x in c for x in ["actual", "act", "real", "فعلي", "realized", "achieved"]):
        return "Actual"
    if any(x in c for x in ["budget", "bud", "plan", "target", "forecast", "proj",
                              "ميزانية", "مخطط", "مستهدف", "توقع"]):
        return "Budget"
    return "Actual"

def _find_header_row(df: pd.DataFrame) -> int:
    """بيدور على الصف اللي فيه أسماء الأعمدة الحقيقية"""
    best_row, best_score = 0, 0
    for i in range(min(15, len(df))): 
        row_vals = df.iloc[i].astype(str).tolist()
        score = 0
        score += sum(1 for v in row_vals
                     if any(re.search(p, v.lower()) for p in MONTH_PATTERNS))
        score += sum(1 for v in row_vals
                     if any(x in v.lower() for x in
                            ["actual","budget","plan","q1","q2","q3","q4",
                             "jan","feb","mar","فعلي","مخطط"]))
        # بونص لو الصف فيه كلمة "account" أو "description"
        score += sum(2 for v in row_vals
                     if any(x in v.lower() for x in
                            ["account","description","item","category","بند","حساب"]))
        if score > best_score:
            best_score, best_row = score, i
    return best_row

def _find_account_column(data: pd.DataFrame) -> int:
    """بيلاقي العمود اللي فيه أسماء البنود"""
    for ci in range(min(5, len(data.columns))):
        col = data.iloc[:, ci].astype(str)
        # لو أكتر من 40% من القيم نصوص طويلة → ده عمود الحسابات
        text_count = sum(1 for v in col
                         if len(v.strip()) > 2
                         and not v.strip().replace('.','').replace('-','').replace(',','').isnumeric()
                         and v.strip() not in ["nan","None",""])
        if text_count / max(len(col), 1) > 0.35:
            return ci
    return 0

def _extract_number(val) -> float | None:
    """بيحول أي قيمة لرقم حتى لو فيها فاصلة أو قوسين"""
    if pd.isna(val):
        return None
    s = str(val).strip().replace(",", "").replace(" ", "")

    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except:
        return None

def _parse_pl_sheet(df: pd.DataFrame, sheet_name: str) -> dict:
    result = {
        "sheet": sheet_name,
        "line_items": [],
        "periods": [],
        "period_types": [],
        "summary": {}
    }

    header_row = _find_header_row(df)
    headers    = df.iloc[header_row].astype(str).tolist()
    data       = df.iloc[header_row + 1:].reset_index(drop=True)

    if len(data) < 2:
        return result

    acct_col = _find_account_column(data)

    # إيجاد أعمدة الأرقام
    period_cols = []
    for ci, h in enumerate(headers):
        if ci == acct_col or ci >= len(data.columns):
            continue
        col_series = data.iloc[:, ci].apply(_extract_number)
        fill_ratio = col_series.notna().sum() / max(len(col_series), 1)
        if fill_ratio > 0.25:  # خفضناها من 0.3 لـ 0.25 عشان نلتقط أكتر
            period_cols.append((ci, h, detect_actual_budget(h)))

    result["periods"]      = [h for _, h, _ in period_cols]
    result["period_types"] = [t for _, _, t in period_cols]

    # قراءة البنود
    revenues, cogs_items, opex_items, nonop_items = [], [], [], []

    for ri in range(len(data)):
        row      = data.iloc[ri]
        acct_raw = row.iloc[acct_col] if acct_col < len(row) else ""
        acct_name = str(acct_raw).strip()

        if not acct_name or acct_name in ["nan", "None", "", "-", "—"]:
            continue

        values = {}
        for ci, h, ptype in period_cols:
            if ci < len(row):
                v = _extract_number(row.iloc[ci])
                if v is not None:
                    values[h] = v

        if not values:
            continue

        category = classify_account(acct_name)
        if category == "Total":   
            continue

        item = {
            "name":     acct_name,
            "category": category,
            "values":   values,
            "total":    sum(values.values()),
        }
        result["line_items"].append(item)

        if category == "Revenue":         revenues.append(item)
        elif category == "COGS":          cogs_items.append(item)
        elif category == "OpEx":          opex_items.append(item)
        elif category == "Non-Operating": nonop_items.append(item)

    
    if not revenues and result["line_items"]:
        max_item = max(result["line_items"], key=lambda x: x["total"])
        max_item["category"] = "Revenue"
        revenues.append(max_item)

    total_rev   = sum(i["total"] for i in revenues)
    total_cogs  = sum(i["total"] for i in cogs_items)
    total_opex  = sum(i["total"] for i in opex_items)
    total_nonop = sum(i["total"] for i in nonop_items)
    gross_profit = total_rev - total_cogs
    ebit         = gross_profit - total_opex
    net_income   = ebit - total_nonop

    result["summary"] = {
        "total_revenue":  total_rev,
        "total_cogs":     total_cogs,
        "gross_profit":   gross_profit,
        "gross_margin":   gross_profit / total_rev if total_rev else 0,
        "total_opex":     total_opex,
        "ebit":           ebit,
        "ebit_margin":    ebit / total_rev if total_rev else 0,
        "total_nonop":    total_nonop,
        "net_income":     net_income,
        "net_margin":     net_income / total_rev if total_rev else 0,
        "revenue_items":  len(revenues),
        "cogs_items":     len(cogs_items),
        "opex_items":     len(opex_items),
    }

    return result

def _find_pl_sheet(sheets_info, xl, sheet_names):
    pl_candidates = []
    for sname in sheet_names:
        sl = sname.lower()
        if any(x in sl for x in ["p&l","pl","profit","income","statement",
                                   "أرباح","خسائر","دخل","نتائج"]):
            pl_candidates.insert(0, sname)
        else:
            pl_candidates.append(sname)

    for sname in pl_candidates:
        try:
            df_raw = pd.read_excel(xl, sheet_name=sname, header=None)
            parsed = _parse_pl_sheet(df_raw, sname)
            if parsed and len(parsed.get("line_items", [])) > 1:  
                return parsed
        except Exception:
            continue
    return None

def read_excel_smart(file_path: str) -> dict:
    result = {"sheets": {}, "pl_data": None, "metadata": {}, "parse_log": []}
    try:
        xl          = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        result["parse_log"].append(f"Found {len(sheet_names)} sheets: {sheet_names}")

        for sheet in sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet, header=None)
            result["sheets"][sheet] = {"name": sheet, "rows": len(df), "cols": len(df.columns)}

        pl = _find_pl_sheet(result["sheets"], xl, sheet_names)
        if pl:
            result["pl_data"] = pl
            result["parse_log"].append(f"✅ Parsed P&L from sheet: {pl['sheet']}")
            result["parse_log"].append(f"   Line items found: {len(pl['line_items'])}")
            result["parse_log"].append(f"   Revenue: {pl['summary'].get('total_revenue', 0):,.0f}")
        else:
            result["parse_log"].append("❌ Could not find P&L sheet")

        result["metadata"] = {"file": file_path, "sheets_count": len(sheet_names), "sheet_names": sheet_names}
    except Exception as e:
        result["error"] = str(e)
        result["parse_log"].append(f"❌ Error: {e}")
    return result

def map_file(file_path: str) -> dict:
    return read_excel_smart(file_path)