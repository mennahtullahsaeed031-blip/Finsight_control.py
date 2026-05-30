import pandas as pd
import numpy as np
import re

REVENUE_KEYWORDS = [
    "revenue","sales","income","turnover","receipts",
    "product sales","service revenue","other income",
    "إيراد","مبيعات","دخل","إيرادات",
]
COGS_KEYWORDS = [
    "cogs","cost of goods","cost of sales","cost of revenue",
    "direct cost","raw materials","direct labor","direct labour",
    "manufacturing overhead","depreciation — plant","production cost",
    "تكلفة المبيعات","تكلفة البضاعة","مواد خام","عمالة مباشرة",
]
OPEX_KEYWORDS = [
    "operating","salary","salaries","wages","payroll",
    "sales & marketing","marketing","advertising",
    "r&d","research","admin","g&a","general","administrative",
    "depreciation","amortization","rent","utilities","insurance",
    "مصاريف","رواتب","إيجار","تسويق","إدارية",
]
NONOP_KEYWORDS = [
    "interest","tax","income tax","zakat","other expense",
    "financing cost","bank charges",
    "فائدة","ضريبة","زكاة",
]
SKIP_KEYWORDS = [
    "total","subtotal","grand total","مجموع","إجمالي",
    "fiscal year","prepared by","reviewed","version",
    "annual budget","budget plan",
]

MONTH_PATTERNS = [
    r'\bjan\w*\b', r'\bfeb\w*\b', r'\bmar\w*\b', r'\bapr\w*\b',
    r'\bmay\b',    r'\bjun\w*\b', r'\bjul\w*\b', r'\baug\w*\b',
    r'\bsep\w*\b', r'\boct\w*\b', r'\bnov\w*\b', r'\bdec\w*\b',
    r'\bq[1-4]\b', r'\b(19|20)\d{2}\b',
    r'\bjan-\d{2}\b', r'\bfeb-\d{2}\b', r'\bmar-\d{2}\b',
]

def classify_account(name: str) -> str:
    n = str(name).lower().strip()
    if any(k in n for k in REVENUE_KEYWORDS):  return "Revenue"
    if any(k in n for k in COGS_KEYWORDS):     return "COGS"
    if any(k in n for k in NONOP_KEYWORDS):    return "Non-Operating"
    if any(k in n for k in OPEX_KEYWORDS):     return "OpEx"
    return "Other"

def is_skip_row(name: str) -> bool:
    n = str(name).lower().strip()
    return any(k in n for k in SKIP_KEYWORDS)

def _to_num(val):
    if val is None: return None
    try:
        if isinstance(val, (int, float)):
            return float(val) if not np.isnan(val) else None
    except: pass
    s = str(val).strip().replace(",","").replace(" ","")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:    return float(s)
    except: return None

def _find_header_row(df: pd.DataFrame) -> int:
    """
    بيدور على الصف اللي فيه أسماء الشهور أو Column Headers
    بيبص في أول 15 صف
    """
    best_row, best_score = 0, 0
    for i in range(min(15, len(df))):
        row_vals = df.iloc[i].astype(str).tolist()
        score = 0
        # نقطة لكل شهر
        score += sum(1 for v in row_vals
                     if any(re.search(p, v.lower()) for p in MONTH_PATTERNS))
        # نقطتين لو فيه "actual" أو "budget"
        score += sum(2 for v in row_vals
                     if any(x in v.lower() for x in
                            ["actual","budget","plan","فعلي","مخطط"]))
        # نقطتين لو فيه "line item" أو "account"
        score += sum(2 for v in row_vals
                     if any(x in v.lower() for x in
                            ["line item","account","description","category",
                             "بند","حساب"]))
        if score > best_score:
            best_score, best_row = score, i

    return best_row

def _find_account_col(data: pd.DataFrame) -> int:
    """بيلاقي عمود أسماء البنود"""
    for ci in range(min(5, len(data.columns))):
        col = data.iloc[:, ci].astype(str)
        text_count = sum(
            1 for v in col
            if len(v.strip()) > 2
            and not v.strip().replace(".","").replace("-","").replace(",","").isnumeric()
            and v.strip() not in ["nan","None",""]
        )
        if text_count / max(len(col), 1) > 0.3:
            return ci
    return 0

def _find_category_col(data: pd.DataFrame, acct_col: int) -> int:
    """
    بيدور على عمود الـ Category (Revenue/COGS/OpEx)
    زي الملف بتاعك اللي فيه Category column
    """
    for ci in range(len(data.columns)):
        if ci == acct_col: continue
        col = data.iloc[:, ci].astype(str).str.lower()
        cat_hits = sum(1 for v in col
                       if any(x in v for x in
                              ["revenue","cogs","opex","operating","non-op",
                               "total","subtotal","إيراد","تكلفة"]))
        if cat_hits / max(len(col), 1) > 0.2:
            return ci
    return -1

def _parse_pl_sheet(df: pd.DataFrame, sheet_name: str) -> dict:
    result = {
        "sheet": sheet_name,
        "line_items": [],
        "periods": [],
        "summary": {}
    }

    # إيجاد الـ header row
    header_row = _find_header_row(df)
    headers    = df.iloc[header_row].astype(str).tolist()
    data       = df.iloc[header_row + 1:].reset_index(drop=True)

    if len(data) < 2:
        return result

    # إيجاد عمود الأسماء
    acct_col = _find_account_col(data)

    # إيجاد عمود الـ Category (لو موجود)
    cat_col  = _find_category_col(data, acct_col)

    # إيجاد أعمدة الأرقام
    period_cols = []
    for ci, h in enumerate(headers):
        if ci == acct_col or ci == cat_col:
            continue
        if ci >= len(data.columns):
            continue
        col_nums = data.iloc[:, ci].apply(_to_num)
        fill_ratio = col_nums.notna().sum() / max(len(col_nums), 1)
        if fill_ratio > 0.25:
            period_cols.append(ci)

    result["periods"] = [headers[ci] for ci in period_cols]

    # قراءة البنود
    revenues, cogs_items, opex_items, nonop_items = [], [], [], []

    for ri in range(len(data)):
        row      = data.iloc[ri]
        acct_raw = row.iloc[acct_col] if acct_col < len(row) else ""
        acct_name = str(acct_raw).strip()

        # تجاهل الصفوف الفاضية أو المجاميع
        if not acct_name or acct_name in ["nan","None","","-","—"]:
            continue
        if is_skip_row(acct_name):
            continue

        # جمع الأرقام
        values = {}
        for ci in period_cols:
            if ci < len(row):
                v = _to_num(row.iloc[ci])
                if v is not None:
                    values[str(headers[ci])] = v

        if not values:
            continue

        # تصنيف البند
        # أولاً: من عمود الـ Category لو موجود
        if cat_col >= 0 and cat_col < len(row):
            cat_val = str(row.iloc[cat_col]).strip().lower()
            if "revenue" in cat_val or "إيراد" in cat_val:
                category = "Revenue"
            elif "cogs" in cat_val or "تكلفة" in cat_val:
                category = "COGS"
            elif "opex" in cat_val or "operating" in cat_val:
                category = "OpEx"
            elif "non-op" in cat_val or "فائدة" in cat_val:
                category = "Non-Operating"
            else:
                category = classify_account(acct_name)
        else:
            category = classify_account(acct_name)

        # لو Other — حاول تفهم من السياق
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

    # لو مفيش Revenue — ممكن الملف مش P&L
    if not revenues:
        return result

    # حساب الـ Summary
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
    }

    return result

def _find_pl_sheet(xl, sheet_names: list):
    """
    بيجرب كل الشيتات ويرجع أحسن P&L
    """
    # أولاً: الشيتات اللي اسمها يشبه P&L
    priority = []
    for sname in sheet_names:
        sl = sname.lower()
        if any(x in sl for x in ["p&l","pl","income","profit","budget",
                                   "statement","أرباح","دخل","ميزانية"]):
            priority.insert(0, sname)
        else:
            priority.append(sname)

    for sname in priority:
        try:
            df_raw = pd.read_excel(xl, sheet_name=sname, header=None)
            parsed = _parse_pl_sheet(df_raw, sname)
            # لو لاقى revenue items → ده الشيت الصح
            if parsed.get("summary", {}).get("total_revenue", 0) > 0:
                return parsed
        except Exception:
            continue
    return None

def read_excel_smart(file_path: str) -> dict:
    result = {
        "pl_data": None,
        "metadata": {},
        "parse_log": []
    }
    try:
        xl          = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        result["parse_log"].append(f"Sheets: {sheet_names}")

        pl = _find_pl_sheet(xl, sheet_names)
        if pl and pl.get("summary", {}).get("total_revenue", 0) > 0:
            result["pl_data"] = pl
            result["parse_log"].append(
                f"✅ P&L found in: {pl['sheet']} | "
                f"Revenue: {pl['summary']['total_revenue']:,.0f} | "
                f"Items: {len(pl['line_items'])}"
            )
        else:
            result["parse_log"].append("❌ No P&L data found")

        result["metadata"] = {
            "file": file_path,
            "sheets_count": len(sheet_names),
            "sheet_names":  sheet_names,
        }
    except Exception as e:
        result["error"]    = str(e)
        result["parse_log"].append(f"❌ Error: {e}")
    return result

def map_file(file_path: str) -> dict:
    return read_excel_smart(file_path)
