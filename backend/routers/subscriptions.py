from fastapi import APIRouter, HTTPException

from db import get_db, insert, new_id, row_to_dict, update
from models import Subscription

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("")
def get_subscriptions():
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute("SELECT * FROM subscriptions")]


@router.post("")
def create_subscription(sub: Subscription):
    item = {"id": new_id(), **sub.model_dump()}
    with get_db() as conn:
        insert(conn, "subscriptions", item)
    return item


@router.put("/{sub_id}")
def update_subscription(sub_id: str, sub: Subscription):
    with get_db() as conn:
        r = update(conn, "subscriptions", sub_id, sub.model_dump())
    if not r:
        raise HTTPException(404, "Subscription not found")
    return row_to_dict(r)


@router.delete("/{sub_id}")
def delete_subscription(sub_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
    return {"ok": True}
