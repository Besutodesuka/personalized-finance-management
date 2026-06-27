from fastapi import APIRouter, HTTPException

from db import get_db, row_to_dict
from models import MasterWalletAdjust

router = APIRouter(prefix="/api/master-wallet", tags=["master-wallet"])


def _balance(conn) -> float:
    row = conn.execute("SELECT balance FROM master_wallet WHERE id=1").fetchone()
    return row["balance"] if row else 0


@router.get("")
def get_master_wallet():
    with get_db() as conn:
        return {"balance": _balance(conn)}


@router.post("/adjust")
def adjust_master_wallet(body: MasterWalletAdjust):
    with get_db() as conn:
        conn.execute("UPDATE master_wallet SET balance=balance+? WHERE id=1", (body.amount,))
        return {"balance": _balance(conn)}


@router.post("/refill")
def refill_wallets():
    """Distribute each wallet's monthly budget out of the master balance."""
    with get_db() as conn:
        wallets = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
        total = sum(w["budget"] for w in wallets)
        balance = _balance(conn)
        if balance < total:
            raise HTTPException(400, f"Insufficient balance. Need ฿{total:,.0f}, have ฿{balance:,.0f}")
        conn.execute("UPDATE master_wallet SET balance=balance-? WHERE id=1", (total,))
        new_balance = _balance(conn)
    return {
        "ok": True,
        "deducted": total,
        "new_balance": new_balance,
        "distributions": [{"wallet": w["name"], "amount": w["budget"]} for w in wallets],
    }
