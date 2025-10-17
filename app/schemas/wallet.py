from datetime import datetime
from .common import ORMModel
class WalletOut(ORMModel):
    id: str
    member_id: str
    balance: int
    updated_at: datetime
class TransactionOut(ORMModel):
    id: str
    wallet_id: str
    amount: int
    type: str
    reason: str | None
    created_at: datetime
