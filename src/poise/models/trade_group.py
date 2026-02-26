from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TradeGroup:
    market: str
    market_title: str
    category: str
    outcome: str
    last_match_time: str    # most recent fill timestamp
    avg_buy_price: Decimal  # weighted avg price of BUY fills
    total_bought: Decimal   # total $ spent on BUY fills
    pnl: Decimal            # net cash flow across all fills
