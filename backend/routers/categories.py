from fastapi import APIRouter, HTTPException

from db import get_db, insert, new_id, row_to_dict, update
from models import Category

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def get_categories():
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute("SELECT * FROM categories")]


@router.post("")
def create_category(cat: Category):
    item = {"id": new_id(), **cat.model_dump()}
    with get_db() as conn:
        insert(conn, "categories", item)
    return item


@router.put("/{cat_id}")
def update_category(cat_id: str, cat: Category):
    with get_db() as conn:
        r = update(conn, "categories", cat_id, cat.model_dump())
    if not r:
        raise HTTPException(404, "Category not found")
    return row_to_dict(r)


@router.delete("/{cat_id}")
def delete_category(cat_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    return {"ok": True}
