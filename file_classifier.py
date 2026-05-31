import pandas as pd
import re

FILE_SIGNATURES = {
    "P&L": {
        "keywords": [
            "revenue","sales","income","cogs","cost of goods","gross profit",
            "operating","net income","net profit","ebitda","turnover",
            "income statement","profit","loss","p&l","gross margin",
            "إيراد","مبيعات","دخل","تكلفة","أرباح","صافي","إجمالي الربح",
        ],
        "label": "Income Statement (P&L)",
        "icon": "📊",
        "color": "#06B6D4",
    },
    "BALANCE_SHEET": {
        "keywords": [
            "assets","liabilities","equity","receivable","payable",
            "retained","shareholders","balance sheet","current assets",
            "fixed assets","total assets","total liabilities",
            "أصول","خصوم","حقوق","ذمم","ميزانية عمومية","رأس المال",
        ],
        "label": "Balance Sheet",
        "icon": "🏦",
        "color": "#8B5CF6",
    },
    "CASH_FLOW": {
        "keywords": [
            "cash flow","cash from","operating activities","investing activities",
            "financing activities","net cash","free cash","fcf",
            "تدفق","نقدي","تشغيلية","استثمارية","تمويلية",
        ],
        "label": "Cash Flow Statement",
        "icon": "💸",
        "color": "#10B981",
    },
    "FIXED_ASSETS": {
        "keywords": [
            "fixed assets","equipment","machinery","vehicles","furniture",
            "depreciation","accumulated depreciation","useful life",
            "capital expenditure","capex","building","land","construction",
            "أصول ثابتة","معدات","آلات","مركبات","استهلاك","مبانى",
        ],
        "label": "Fixed Assets / CapEx Budget",
        "icon": "🏗️",
        "color": "#F59E0B",
    },
    "PAYROLL": {
        "keywords": [
            "salary","salaries","payroll","employee","staff","wages",
            "headcount","bonus","allowance","deduction","basic pay",
            "net pay","gross pay","hr budget",
            "رواتب","موظفين","مرتبات","بدلات","خصومات","أجور",
        ],
        "label": "Payroll / HR Budget",
        "icon": "👥",
        "color": "#EC4899",
    },
    "WORKING_CAPITAL": {
        "keywords": [
            "working capital","current ratio","quick ratio",
            "receivables days","payables days","inventory days",
            "cash conversion cycle","liquidity",
            "رأس المال العامل","أصول متداولة","خصوم متداولة",
        ],
        "label": "Working Capital Budget",
        "icon": "💵",
        "color": "#14B8A6",
    },
    "LOAN": {
        "keywords": [
            "loan","repayment","installment","principal","interest expense",
            "amortization","remaining balance","debt schedule",
            "قرض","سداد","قسط","أصل","فائدة","رصيد متبقي",
        ],
        "label": "Loan Repayment Schedule",
        "icon": "🏦",
        "color": "#F43F5E",
    },
    "BUDGET": {
        "keywords": [
            "budget","annual budget","allocated","allocation","planned",
            "variance","actual vs budget","target","forecast",
            "raw materials","direct labor","direct materials","overhead",
            "production cost","manufacturing cost","production budget",
            "units to produce","units produced","output",
            "cogs budget","cost of goods budget","cost of sales budget",
            "sg&a","selling expenses","general expenses","administrative",
            "marketing expenses","distribution cost",
            "q1","q2","q3","q4","quarter","annual","monthly","yearly",
            "total budget","department budget","master budget",
            "amount","value","subtotal",
            "ميزانية","مخصص","انحراف","خطة","مستهدف",
            "مواد خام","عمالة مباشرة","تكاليف إنتاج",
            "مصاريف بيع","مصاريف إدارية","ربع سنوي",
        ],
        "label": "Budget Plan",
        "icon": "📋",
        "color": "#F97316",
    },
}


PL_MUST_KEYWORDS = [
    "revenue", "gross profit", "net income",
    "cost of goods", "operating expenses",
    "إيراد", "إجمالي الربح", "صافي الدخل",
]

def _extract_all_text(file_path: str) -> str:
    """يستخرج كل النصوص من الملف"""
    all_text = ""
    try:
        xl = pd.ExcelFile(file_path)

        # أسماء الشيتات
        for sheet in xl.sheet_names:
            all_text += " " + sheet.lower()

        # محتوى كل شيت (أول 100 صف)
        for sheet in xl.sheet_names:
            try:
                df = pd.read_excel(
                    file_path,
                    sheet_name=sheet,
                    header=None,
                    nrows=100
                )
                for col in df.columns:
                    col_text = df[col].astype(str).str.lower().str.strip()
                    all_text += " " + " ".join(col_text.tolist())
            except Exception:
                continue

    except Exception:
        return ""

    all_text = re.sub(r'[^\w\s\u0600-\u06FF&./%-]', ' ', all_text)
    return all_text


def _classify_by_filename(file_path: str) -> str:
    """يصنف الملف من اسمه لو مش لاقي keywords كافية"""
    name = file_path.lower()

    if any(x in name for x in ["p&l", "income statement", "profit loss",
                                "profit & loss", "income_statement"]):
        return "P&L"
    if any(x in name for x in ["balance sheet", "balance_sheet"]):
        return "BALANCE_SHEET"
    if any(x in name for x in ["cash flow", "cashflow", "cash_flow"]):
        return "CASH_FLOW"
    if any(x in name for x in ["fixed asset", "fixed_asset", "capex",
                                "capital expenditure"]):
        return "FIXED_ASSETS"
    if any(x in name for x in ["payroll", "salary", "salaries", "hr budget",
                                "human resource"]):
        return "PAYROLL"
    if any(x in name for x in ["working capital", "liquidity"]):
        return "WORKING_CAPITAL"
    if any(x in name for x in ["loan", "repayment", "debt schedule"]):
        return "LOAN"
    if any(x in name for x in ["budget", "plan", "forecast", "projection",
                                "cogs", "materials", "labor", "overhead",
                                "sg&a", "selling", "production", "manufacturing",
                                "direct", "indirect", "variance"]):
        return "BUDGET"
    return "UNKNOWN"


def classify_file(file_path: str) -> dict:
    """
    يصنف الملف المالي ويرجع نوعه مع الـ confidence
    """
    
    try:
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
    except Exception as e:
        return {
            "type":        "ERROR",
            "label":       "Error reading file",
            "icon":        "❌",
            "color":       "#EF4444",
            "confidence":  0,
            "sheet_names": [],
            "scores":      {},
            "error":       str(e),
        }

   
    all_text = _extract_all_text(file_path)

    
    scores = {}
    for file_type, sig in FILE_SIGNATURES.items():
        scores[file_type] = sum(1 for kw in sig["keywords"] if kw in all_text)

    # ── STEP 2: P&L Override ──────────────────────────────────────────────
    # لو الملف فيه 3+ من الكلمات الأساسية دي → P&L مؤكد بغض النظر عن باقي الـ scores
    pl_hits = sum(1 for kw in PL_MUST_KEYWORDS if kw in all_text)

    if pl_hits >= 3:
        best_type  = "P&L"
        best_score = max(scores["P&L"], pl_hits)

    else:
       
        best_type  = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score < 2:
            filename_type = _classify_by_filename(file_path)
            if filename_type != "UNKNOWN":
                best_type  = filename_type
                best_score = max(best_score, 1)

     
        if best_score == 0 or best_type == "UNKNOWN":
            best_type  = "BUDGET"
            best_score = 1

    sig        = FILE_SIGNATURES.get(best_type, FILE_SIGNATURES["BUDGET"])
    confidence = min(best_score / 8 * 100, 100)

    return {
        "type":        best_type,
        "label":       sig["label"],
        "icon":        sig["icon"],
        "color":       sig["color"],
        "confidence":  round(confidence, 0),
        "sheet_names": sheet_names,
        "scores":      scores,
    }
