
import pandas as pd
import re

FILE_SIGNATURES = {
    "P&L": {
        "keywords": ["revenue","sales","cogs","cost of goods","gross profit",
                     "operating expense","opex","ebitda","net income","net profit",
                     "إيراد","مبيعات","تكلفة","أرباح","صافي"],
        "min_score": 2,
        "kpis": ["gross_margin","net_margin","ebitda_margin","opex_ratio","revenue_growth"],
        "label": "Income Statement (P&L)",
        "icon": "📊",
        "color": "#06B6D4",
    },
    "BALANCE_SHEET": {
        "keywords": ["assets","liabilities","equity","current assets","fixed assets",
                     "accounts receivable","accounts payable","retained earnings",
                     "total assets","total liabilities","shareholders",
                     "أصول","خصوم","حقوق ملكية","ذمم"],
        "min_score": 2,
        "kpis": ["current_ratio","debt_to_equity","asset_turnover","working_capital"],
        "label": "Balance Sheet",
        "icon": "🏦",
        "color": "#8B5CF6",
    },
    "CASH_FLOW": {
        "keywords": ["cash flow","operating activities","investing activities",
                     "financing activities","net cash","capex","capital expenditure",
                     "cash from","free cash flow","fcf",
                     "تدفق نقدي","أنشطة تشغيلية","أنشطة استثمارية"],
        "min_score": 2,
        "kpis": ["operating_cash_flow","free_cash_flow","capex_ratio","cash_conversion"],
        "label": "Cash Flow Statement",
        "icon": "💸",
        "color": "#10B981",
    },
    "FIXED_ASSETS": {
        "keywords": ["fixed assets","asset","equipment","machinery","vehicles",
                     "furniture","buildings","land","depreciation","accumulated",
                     "capex","asset category","asset type","useful life",
                     "أصول ثابتة","معدات","آلات","مبانى","استهلاك"],
        "min_score": 2,
        "kpis": ["capex_utilization","budget_variance","depreciation_impact","top_categories"],
        "label": "Fixed Assets / CapEx Budget",
        "icon": "🏗️",
        "color": "#F59E0B",
    },
    "PAYROLL": {
        "keywords": ["salary","salaries","payroll","employee","staff","wages",
                     "headcount","department","bonus","allowance","deduction",
                     "رواتب","موظفين","مرتبات","بدلات","خصومات"],
        "min_score": 2,
        "kpis": ["total_payroll","avg_salary","headcount","payroll_to_revenue"],
        "label": "Payroll / HR Budget",
        "icon": "👥",
        "color": "#EC4899",
    },
    "REVENUE_FORECAST": {
        "keywords": ["forecast","projection","projected","target","plan",
                     "revenue forecast","sales forecast","pipeline",
                     "توقع","مستهدف","خطة مبيعات"],
        "min_score": 2,
        "kpis": ["forecast_accuracy","target_achievement","growth_rate"],
        "label": "Revenue Forecast",
        "icon": "🔮",
        "color": "#3B82F6",
    },
    "BUDGET": {
        "keywords": ["budget","annual budget","department budget","allocated",
                     "allocation","variance","actual vs budget",
                     "ميزانية","مخصص","انحراف"],
        "min_score": 2,
        "kpis": ["budget_utilization","variance","burn_rate"],
        "label": "Budget Plan",
        "icon": "📋",
        "color": "#F97316",
    },
}

def classify_file(file_path: str) -> dict:
    """
    يقرأ الملف ويحدد نوعه قبل أي تحليل
    Returns: {type, label, icon, color, confidence, kpis, all_text}
    """
    try:
        xl = pd.ExcelFile(file_path)
        all_text = ""

        # اجمع كل النصوص من كل الشيتات
        for sheet in xl.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet, header=None)
            all_text += " " + sheet.lower()
            for col in df.columns:
                all_text += " " + " ".join(df[col].astype(str).str.lower().tolist())

        # احسب score لكل نوع
        scores = {}
        for file_type, sig in FILE_SIGNATURES.items():
            score = sum(1 for kw in sig["keywords"] if kw in all_text)
            scores[file_type] = score

        # النوع اللي جاب أعلى score
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        sig = FILE_SIGNATURES[best_type]

        # لو الـ score منخفض جداً → Unknown
        if best_score < sig["min_score"]:
            best_type = "UNKNOWN"

        confidence = min(best_score / 6 * 100, 100)

        return {
            "type":       best_type,
            "label":      FILE_SIGNATURES.get(best_type, {}).get("label", "Unknown File"),
            "icon":       FILE_SIGNATURES.get(best_type, {}).get("icon", "📄"),
            "color":      FILE_SIGNATURES.get(best_type, {}).get("color", "#8BA3C7"),
            "confidence": round(confidence, 0),
            "kpis":       FILE_SIGNATURES.get(best_type, {}).get("kpis", []),
            "scores":     scores,
            "sheet_names": xl.sheet_names,
        }

    except Exception as e:
        return {"type": "ERROR", "label": "Error reading file",
                "icon": "❌", "color": "#EF4444", "confidence": 0,
                "kpis": [], "error": str(e)}