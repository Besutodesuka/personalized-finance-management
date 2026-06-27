from datetime import datetime
from typing import Optional

from fastapi import APIRouter

from db import get_db, row_to_dict

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(month: Optional[str] = None):
    if not month:
        month = datetime.now().strftime("%Y-%m")

    with get_db() as conn:
        wallets = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
        expenses = [row_to_dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE date LIKE ?", (f"{month}%",)
        )]
        subscriptions = [row_to_dict(r) for r in conn.execute("SELECT * FROM subscriptions")]

    active_subs = [s for s in subscriptions if s["active"]]
    sub_total = sum(s["amount"] for s in active_subs)
    total_spent = sum(e["amount"] for e in expenses)
    total_budget = sum(w["budget"] for w in wallets)
    days_passed = max(datetime.now().day, 1)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_expenses = [e for e in expenses if e["date"] == today_str]

    wallet_breakdown = []
    for w in wallets:
        spent = sum(e["amount"] for e in expenses if e["wallet_id"] == w["id"])
        wallet_breakdown.append({
            "wallet": w,
            "spent": spent,
            "budget": w["budget"],
            "remaining": w["budget"] - spent,
            "pct": round(spent / w["budget"] * 100, 1) if w["budget"] else 0,
        })

    daily: dict = {}
    for e in expenses:
        daily[e["date"]] = daily.get(e["date"], 0) + e["amount"]

    return {
        "month": month,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "daily_average": round(total_spent / days_passed, 2),
        "wallet_breakdown": wallet_breakdown,
        "subscription_total": sub_total,
        "active_subscriptions": active_subs,
        "unexpected_count": len([e for e in expenses if e["type"] == "unexpected"]),
        "today_spent": sum(e["amount"] for e in today_expenses),
        "today_count": len(today_expenses),
        "recent_expenses": sorted(expenses, key=lambda x: x["date"], reverse=True)[:10],
        "daily_chart": sorted(
            [{"date": k, "amount": v} for k, v in daily.items()], key=lambda x: x["date"]
        ),
    }
