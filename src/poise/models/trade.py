from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Trade:
    id: str
    market: str
    asset_id: str
    side: str
    size: Decimal
    price: Decimal
    fee_rate_bps: Decimal
    status: str
    match_time: str
    outcome: str
    transaction_hash: str
    trader_side: str
    market_title: str = ""
    category: str = ""
