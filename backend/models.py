"""Pydantic request/response schemas."""
from typing import Optional

from pydantic import BaseModel


class Wallet(BaseModel):
    name: str
    budget: float
    color: str = "#6366f1"
    icon: str = "💰"


class Category(BaseModel):
    name: str
    wallet_id: str
    type: str = "daily"


class Expense(BaseModel):
    date: str
    amount: float
    description: str
    category_id: str
    wallet_id: str
    type: str = "planned"


class Subscription(BaseModel):
    name: str
    amount: float
    billing_day: int = 1
    billing_cycle: str = "monthly"  # 'monthly' | 'yearly'
    renewal_date: Optional[str] = None  # YYYY-MM-DD, used for yearly
    wallet_id: str
    active: bool = True


class MasterWalletAdjust(BaseModel):
    amount: float  # positive = add, negative = subtract


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: list[ChatHistoryItem] = []
