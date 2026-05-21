"""
Budget vs Actual Variance Engine
"""
EXPENSE_CATEGORIES = {"COGS", "OpEx", "Non-Operating"}

def calculate_variance(actual, budget, category="Revenue"):
    var_abs = actual - budget
    var_pct = (var_abs / abs(budget)) * 100 if budget != 0 else 0
    is_expense = category in EXPENSE_CATEGORIES
    favorable = (var_abs < 0) if is_expense else (var_abs > 0)
    return {
        "actual": actual, "budget": budget, "variance_abs": var_abs,
        "variance_pct": var_pct, "favorable": favorable,
        "status": "Favorable" if favorable else ("On Target" if var_abs == 0 else "Unfavorable"),
        "severity": "Low" if abs(var_pct) <= 2 else "Medium" if abs(var_pct) <= 5 else "High" if abs(var_pct) <= 10 else "Critical",
    }

def calculate_all_variances(line_items):
    results = []
    for item in line_items:
        vals = item.get("values", {})
        actuals = {k: v for k, v in vals.items() if "budget" not in k.lower() and "plan" not in k.lower()}
        budgets = {k: v for k, v in vals.items() if "budget" in k.lower() or "plan" in k.lower()}
        if not budgets:
            results.append({**item, "variances": [], "ytd_variance": None})
            continue
        total_actual = sum(actuals.values())
        total_budget = sum(budgets.values())
        ytd_var = calculate_variance(total_actual, total_budget, item.get("category", "Revenue"))
        results.append({**item, "ytd_actual": total_actual, "ytd_budget": total_budget, "ytd_variance": ytd_var})
    return results

def variance_summary(variances):
    total_actual_rev = total_budget_rev = total_actual_exp = total_budget_exp = 0
    unfavorable_items, favorable_items = [], []
    for item in variances:
        ytd = item.get("ytd_variance")
        if not ytd:
            continue
        cat = item.get("category", "")
        if cat == "Revenue":
            total_actual_rev += item.get("ytd_actual", 0)
            total_budget_rev += item.get("ytd_budget", 0)
        elif cat in EXPENSE_CATEGORIES:
            total_actual_exp += item.get("ytd_actual", 0)
            total_budget_exp += item.get("ytd_budget", 0)
        if not ytd["favorable"] and ytd["severity"] in ("High", "Critical"):
            unfavorable_items.append({"name": item["name"], "category": cat,
                                      "variance_pct": ytd["variance_pct"], "variance_abs": ytd["variance_abs"], "severity": ytd["severity"]})
        elif ytd["favorable"]:
            favorable_items.append({"name": item["name"], "category": cat,
                                    "variance_pct": ytd["variance_pct"], "variance_abs": ytd["variance_abs"]})
    rev_var = calculate_variance(total_actual_rev, total_budget_rev, "Revenue")
    exp_var = calculate_variance(total_actual_exp, total_budget_exp, "OpEx")
    score = sum([2 if rev_var["favorable"] else (-2 if rev_var["severity"] == "Critical" else -1),
                 2 if exp_var["favorable"] else (-2 if exp_var["severity"] == "Critical" else -1)])
    health = "Excellent" if score >= 3 else "Good" if score >= 1 else "Needs Attention" if score >= -1 else "Critical"
    return {
        "revenue_variance": rev_var, "expense_variance": exp_var,
        "top_unfavorable": sorted(unfavorable_items, key=lambda x: abs(x["variance_pct"]), reverse=True)[:5],
        "top_favorable": sorted(favorable_items, key=lambda x: abs(x["variance_pct"]), reverse=True)[:5],
        "overall_health": health,
    }