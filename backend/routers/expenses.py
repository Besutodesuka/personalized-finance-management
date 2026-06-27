from typing import Optional

from fastapi import APIRouter, HTTPException

from db import get_db, insert, new_id, row_to_dict, update
from models import Expense

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("")
def get_expenses(month: Optional[str] = None, wallet_id: Optional[str] = None):
    query = "SELECT * FROM expenses WHERE 1=1"
    params: list = []
    if month:
        query += " AND date LIKE ?"
        params.append(f"{month}%")
    if wallet_id:
        query += " AND wallet_id=?"
        params.append(wallet_id)
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute(query, params)]


@router.post("")
def create_expense(expense: Expense):
    item = {"id": new_id(), **expense.model_dump()}
    with get_db() as conn:
        insert(conn, "expenses", item)
    return item


@router.put("/{expense_id}")
def update_expense(expense_id: str, expense: Expense):
    with get_db() as conn:
        r = update(conn, "expenses", expense_id, expense.model_dump())
    if not r:
        raise HTTPException(404, "Expense not found")
    return row_to_dict(r)


@router.delete("/{expense_id}")
def delete_expense(expense_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    return {"ok": True}
