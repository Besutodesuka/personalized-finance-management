import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response

from db import get_db, row_to_dict

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/expenses.csv")
def export_csv():
    with get_db() as conn:
        expenses = [row_to_dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY date")]
    if not expenses:
        raise HTTPException(404, "No expenses yet")
    buf = io.StringIO()
    fields = ["id", "date", "amount", "description", "category_id", "wallet_id", "type"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(expenses)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@router.get("/data.json")
def export_json():
    with get_db() as conn:
        return JSONResponse({
            "wallets": [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")],
            "categories": [row_to_dict(r) for r in conn.execute("SELECT * FROM categories")],
            "expenses": [row_to_dict(r) for r in conn.execute("SELECT * FROM expenses")],
            "subscriptions": [row_to_dict(r) for r in conn.execute("SELECT * FROM subscriptions")],
            "exported_at": datetime.now().isoformat(),
        })
