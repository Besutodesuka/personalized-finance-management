from fastapi import APIRouter, HTTPException

from db import get_db, insert, new_id, row_to_dict, update
from models import Wallet

router = APIRouter(prefix="/api/wallets", tags=["wallets"])


@router.get("")
def get_wallets():
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]


@router.post("")
def create_wallet(wallet: Wallet):
    item = {"id": new_id(), **wallet.model_dump()}
    with get_db() as conn:
        insert(conn, "wallets", item)
    return item


@router.put("/{wallet_id}")
def update_wallet(wallet_id: str, wallet: Wallet):
    with get_db() as conn:
        r = update(conn, "wallets", wallet_id, wallet.model_dump())
    if not r:
        raise HTTPException(404, "Wallet not found")
    return row_to_dict(r)


@router.delete("/{wallet_id}")
def delete_wallet(wallet_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM wallets WHERE id=?", (wallet_id,))
    return {"ok": True}
