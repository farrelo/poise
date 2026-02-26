from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Position:
    market: str
    market_title: str
    category: str
    outcome: str
    avg_buy_price: Decimal
    current_price: Decimal
    net_shares: Decimal
    total_bought: Decimal
    last_buy_time: str