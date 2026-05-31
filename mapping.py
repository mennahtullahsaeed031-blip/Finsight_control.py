import pandas as pd
import numpy as np
import re
import math

# ══════════════════════════════════════════════════════════════════════════════
# KEYWORDS
# ══════════════════════════════════════════════════════════════════════════════
REVENUE_KEYWORDS = [
    "revenue", "sales", "income", "turnover", "receipts",
    "product sales", "service revenue", "other income",
    "إيراد", "مبيعات", "دخل", "إيرادات",
]
COGS_KEYWORDS = [
    "cogs", "cost of goods", "cost of sales", "cost of revenue",
    "direct cost", "raw materials", "direct labor", "direct labour",
    "manufacturing overhead", "production cost",
    "تكلفة المبيعات", "تكلفة البضاعة", "مواد خام", "عمالة مباشرة",
]
OPEX_KEYWORDS = [
    "salary", "salaries", "wages", "payroll",
    "sales & marketing", "marketing", "advertising", "sg&a", "sga",
    "r&d", "research", "admin", "g&a", "general", "administrative",
    "depreciation", "amortization", "d&a", "rent", "utilities", "insurance",
    "مصاريف", "رواتب", "إيجار", "تسويق", "إدارية",
]
NONOP_KEYWORDS = [
    "interest", "tax", "income tax", "taxes", "zakat",
    "other expense", "financing cost", "bank charges",
    "فائدة", "ضريبة", "زكاة",
]

MONTH_PATTERNS = [
    r'\bjan\w*\b', r'\bfeb\w*\b', r'\bmar\w*\b', r'\bapr\w*\b',
    r'\bmay\b',    r'\bjun\w*\b', r'\bjul\w*\b', r'\baug\w*\b',
    r'\bsep\w*\b', r'\boct\w*\b', r'\bnov\w*\b', r'\bdec\w*\b',
    r'\bq[1-4]\b', r'\b(19|20)\d{2}\b',
    r'\b\w{3}-\d{2,4}\b',  # Jan-22, Feb-2024 ...
]

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def classify_account(name: str) -> str:
    n = str(name).lower().strip()
    if any(k in n for k in REVENUE_KEYWORDS):  return "Revenue"
    if any(k in n for k in COGS_KEYWORDS):     return "COGS"
    if any(k in n for k in NONOP_KEYWORDS):    return "Non-Operating"
    if any(k in n for k in OPEX_KEYWORDS):     return "OpEx"
    return "Other"


# صفوف بيتم تجاهلها — subtotals وليست بنود حقيقية
SKIP_EXACT = {
    "total", "subtotal", "grand total", "مجموع", "إجمالي",
    "fiscal year", "prepared by", "reviewed", "version",
    "annual budget", "budget plan",
    "operating expenses",     # section header
    "non-operating",          # section header
    "gross profit",           # subtotal
    "ebit", "ebitda", "ebt",  # subtotals
    "net income", "net profit",  # subtotals
}

def is_skip_row(name: str) -> bool:
    n = str(name).strip()
    if not n or n in ["nan", "None", "", "-", "—"]:
        return True
    nl = n.lower()
    if nl in SKIP_EXACT:
        return True
    if nl.startswith(("total ", "subtotal", "grand total", "مجموع", "إجمالي")):
        return True
    # section headers بالكابيتال كلها
    if n == n.upper() and len(n) > 3 and not n.replace(" ", "").isnumeric():
        return True
    # نسب مئوية
    if nl.startswith("as a %") or nl.startswith("% of"):
        return True
    return False


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


def _find_header_row(df: pd.DataFrame) -> int:
    """يلاقي الصف اللي فيه أسماء الأعمدة"""
    best_row, best_score = 0, 0
    for i in range(min(15, len(df))):
        row_vals = df.iloc[i].fillna("").astype(str).tolist()
        score = 0
        score += sum(1 for v in row_vals
                     if any(re.search(p, v.lower()) for p in MONTH_PATTERNS))
        score += sum(2 for v in row_vals
                     if any(x in v.lower() for x in
                            ["category", "line item", "account", "description", "بند", "حساب"]))
        score += sum(1 for v in row_vals
                     if any(x in v.lower() for x in
                            ["actual", "budget", "plan", "فعلي", "q1", "q2", "q3", "q4",
                             "fy", "last year", "next year", "prior", "in '000", "in '000s"]))
        if score > best_score:
            best_score, best_row = score, i

    # تحقق إن الصف التالي فيه أرقام
    for i in range(best_row, min(best_row + 3, len(df) - 1)):
        next_row = df.iloc[i + 1].fillna("").astype(str)
        nums = sum(1 for v in next_row if _to_num(v) is not None)
        if nums >= 2:
            return i
    return best_row


def _find_account_col(data: pd.DataFrame) -> int:
    """يلاقي عمود أسماء البنود"""
    best_ci, best_score = 0, -1
    for ci in range(min(5, len(data.columns))):
        col = data.iloc[:, ci].fillna("").astype(str).str.strip()
        text_count = sum(
            1 for v in col
            if len(v) > 2
            and v not in ["nan", "None", "", "-", "—"]
            and _to_num(v) is None  # مش رقم
        )
        if text_count > best_score:
            best_score = text_count
            best_ci    = ci
    return best_ci


def _find_category_col(data: pd.DataFrame, acct_col: int) -> int:
    """يلاقي عمود الـ Category لو موجود"""
    CAT_VALS = ["revenue", "cogs", "opex", "operating", "non-op", "non-operating",
                "إيراد", "تكلفة", "مصاريف", "total", "subtotal"]
    for ci in range(min(6, len(data.columns))):
        if ci == acct_col:
            continue
        col = data.iloc[:, ci].fillna("").astype(str).str.lower()
        hits = sum(1 for v in col if any(x in v for x in CAT_VALS))
        if hits / max(len(col), 1) > 0.15:
            return ci
    return -1


def _find_period_cols(headers: list, data: pd.DataFrame, acct_col: int, cat_col: int) -> list:
    """
    يلاقي أعمدة الأرقام الحقيقية:
    - يستبعد أعمدة الـ Growth% (avg_abs < 2)
    - يستبعد أعمدة الـ NaN (separators)
    - لو في مجموعتين (Last Year + Budget) → يختار المجموعة الثانية (Budget)
    """
    candidates = []
    for ci, h in enumerate(headers):
        if ci == acct_col or ci == cat_col:
            continue
        if ci >= len(data.columns):
            continue
        col_nums = [_to_num(str(v)) for v in data.iloc[:, ci]]
        valid    = [v for v in col_nums if v is not None]
        if not valid:
            continue
        fill_ratio = len(valid) / max(len(data), 1)
        if fill_ratio < 0.20:
            continue
        avg_abs = sum(abs(v) for v in valid) / len(valid)
        if avg_abs < 2:
            continue  # Growth% columns
        candidates.append(ci)

    if not candidates:
        return []

    # لو في gap كبير في الـ indices → مجموعتان → خد الثانية (Budget)
    max_gap     = 0
    split_after = -1
    for i in range(len(candidates) - 1):
        gap = candidates[i + 1] - candidates[i]
        if gap > 1 and gap > max_gap:
            max_gap     = gap
            split_after = i

    if split_after >= 0:
        return candidates[split_after + 1:]

    return candidates


# ══════════════════════════════════════════════════════════════════════════════
# SHEET PARSER
# ══════════════════════════════════════════════════════════════════════════════
def _parse_pl_sheet(df: pd.DataFrame, sheet_name: str) -> dict:
    result = {"sheet": sheet_name, "line_items": [], "periods": [], "summary": {}}

    if df is None or df.empty or len(df) < 3:
        return result

    header_row  = _find_header_row(df)
    headers     = df.iloc[header_row].fillna("").astype(str).tolist()
    data        = df.iloc[header_row + 1:].reset_index(drop=True)

    if len(data) < 2:
        return result

    acct_col    = _find_account_col(data)
    cat_col     = _find_category_col(data, acct_col)
    period_cols = _find_period_cols(headers, data, acct_col, cat_col)

    if not period_cols:
        return result

    result["periods"] = [headers[ci] for ci in period_cols]

    revenues, cogs_items, opex_items, nonop_items = [], [], [], []

    for ri in range(len(data)):
        row       = data.iloc[ri]
        acct_name = str(row.iloc[acct_col]).strip() if acct_col < len(row) else ""

        if is_skip_row(acct_name):
            continue

        # جمع الأرقام
        values = {}
        for ci in period_cols:
            if ci < len(row):
                v = _to_num(str(row.iloc[ci]))
                if v is not None:
                    values[str(headers[ci])] = v

        if not values:
            continue

        # تصنيف — أولاً من عمود Category
        category = "Other"
        if cat_col >= 0 and cat_col < len(row):
            cat_val = str(row.iloc[cat_col]).strip().lower()
            if any(x in cat_val for x in ["revenue", "إيراد", "مبيعات"]):
                category = "Revenue"
            elif any(x in cat_val for x in ["cogs", "cost", "تكلفة"]):
                category = "COGS"
            elif any(x in cat_val for x in ["opex", "operating", "مصاريف", "رواتب"]):
                category = "OpEx"
            elif any(x in cat_val for x in ["non-op", "interest", "tax", "فائدة", "ضريبة"]):
                category = "Non-Operating"

        # لو Other → صنف من اسم البند
        if category == "Other":
            category = classify_account(acct_name)

        if category == "Other":
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

    if not revenues:
        return result

    total_rev   = sum(i["total"] for i in revenues)
    total_cogs  = sum(abs(i["total"]) for i in cogs_items)
    total_opex  = sum(abs(i["total"]) for i in opex_items)
    total_nonop = sum(abs(i["total"]) for i in nonop_items)

    gross_profit = total_rev - total_cogs
    ebit         = gross_profit - total_opex
    net_income   = ebit - total_nonop

    if total_rev == 0:
        return result

    result["summary"] = {
        "total_revenue": total_rev,
        "total_cogs":    total_cogs,
        "gross_profit":  gross_profit,
        "gross_margin":  gross_profit / total_rev,
        "total_opex":    total_opex,
        "ebit":          ebit,
        "ebit_margin":   ebit / total_rev,
        "total_nonop":   total_nonop,
        "net_income":    net_income,
        "net_margin":    net_income / total_rev,
    }

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SHEET SELECTOR
# ══════════════════════════════════════════════════════════════════════════════
def _score_sheet_name(name: str) -> int:
    nl = name.lower()
    if any(x in nl for x in ["income statement", "income_statement"]):  return 10
    if any(x in nl for x in ["p&l", "profit & loss", "profit loss"]):   return 9
    if any(x in nl for x in ["profit", "pl "]):                         return 8
    if any(x in nl for x in ["financial statements", "fin stat"]):       return 7
    if any(x in nl for x in ["budget", "actual"]):                       return 6
    if any(x in nl for x in ["أرباح", "دخل", "قائمة"]):                 return 8
    return 1


def _find_pl_sheet(xl, sheet_names: list):
    priority = sorted(sheet_names, key=_score_sheet_name, reverse=True)

    best_result  = None
    best_score   = 0

    for sname in priority:
        try:
            df_raw = pd.read_excel(xl, sheet_name=sname, header=None)
            if df_raw.empty or len(df_raw) < 3:
                continue
            parsed = _parse_pl_sheet(df_raw, sname)
            rev    = parsed.get("summary", {}).get("total_revenue", 0)
            items  = len(parsed.get("line_items", []))
            # أفضل نتيجة = revenue حقيقي + أكتر line items
            name_bonus = _score_sheet_name(sname)
            cogs_bonus = 2 if parsed.get("summary", {}).get("total_cogs", 0) > 0 else 1
            quality = rev * (1 + items * 0.1) * name_bonus * cogs_bonus if items >= 2 else 0
            if quality > best_score:
                best_score  = quality
                best_result = parsed
        except Exception:
            continue

    return best_result


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def read_excel_smart(file_path: str) -> dict:
    result = {"pl_data": None, "metadata": {}, "parse_log": []}
    try:
        xl          = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        result["parse_log"].append(f"Sheets: {sheet_names}")

        pl = _find_pl_sheet(xl, sheet_names)
        if pl and pl.get("summary", {}).get("total_revenue", 0) > 0:
            result["pl_data"] = pl
            s = pl["summary"]
            result["parse_log"].append(
                f"✅ P&L found in: '{pl['sheet']}' | "
                f"Revenue: {s['total_revenue']:,.0f} | "
                f"GP%: {s['gross_margin']*100:.1f}% | "
                f"Net%: {s['net_margin']*100:.1f}% | "
                f"Items: {len(pl['line_items'])}"
            )
        else:
            result["parse_log"].append("❌ No P&L data found")

        result["metadata"] = {
            "file":         file_path,
            "sheets_count": len(sheet_names),
            "sheet_names":  sheet_names,
        }
    except Exception as e:
        result["error"]    = str(e)
        result["parse_log"].append(f"❌ Error: {e}")
    return result


def map_file(file_path: str) -> dict:
    return read_excel_smart(file_path)
