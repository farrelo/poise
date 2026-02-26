from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from ..models.trade import Trade
from ..models.trade_group import TradeGroup

_BPS = Decimal("10000")


def daily_pnl(trades: list[Trade]) -> list[tuple[str, Decimal]]:
    """
    Aggregates net P&L per calendar day.

    Per fill:
      SELL → +price × size − fee
      BUY  → −price × size − fee
      fee  = price × size × fee_rate_bps / 10000

    Returns a list of (date_str, pnl) sorted newest-first.
    """
    buckets: dict[str, Decimal] = defaultdict(Decimal)

    for trade in trades:
        dt = datetime.fromtimestamp(int(trade.match_time))
        day = dt.strftime("%Y-%m-%d")

        gross = trade.price * trade.size
        fee = gross * trade.fee_rate_bps / _BPS

        if trade.side == "SELL":
            buckets[day] += gross - fee
        else:  # BUY
            buckets[day] -= gross + fee

    return sorted(buckets.items(), reverse=True)


def total_pnl(daily: list[tuple[str, Decimal]]) -> Decimal:
    """Sums all daily P&L values into a single total."""
    return sum((pnl for _, pnl in daily), Decimal("0"))


def trade_pnl(trade: Trade) -> Decimal:
    """
    Net cash flow for a single fill.

    SELL → +price × size − fee  (cash received)
    BUY  → −(price × size + fee)  (cash spent)
    """
    gross = trade.price * trade.size
    fee = gross * trade.fee_rate_bps / _BPS
    if trade.side == "SELL":
        return gross - fee
    else:
        return -(gross + fee)


def group_trades(trades: list[Trade]) -> list[TradeGroup]:
    """
    Groups individual fills by (market, outcome) and computes per-position aggregates.

    Returns groups sorted by most recent fill time, newest first.
    """
    buckets: dict[tuple[str, str], list[Trade]] = defaultdict(list)
    for t in trades:
        buckets[(t.market, t.outcome)].append(t)

    result = []
    for (market, outcome), fills in buckets.items():
        last_match_time = max(fills, key=lambda t: int(t.match_time)).match_time

        buy_fills = [t for t in fills if t.side == "BUY"]
        if buy_fills:
            total_buy_size = sum(t.size for t in buy_fills)
            total_buy_value = sum(t.price * t.size for t in buy_fills)
            avg_buy_price = total_buy_value / total_buy_size if total_buy_size else Decimal("0")
            total_bought = total_buy_value
        else:
            avg_buy_price = Decimal("0")
            total_bought = Decimal("0")

        pnl = sum((trade_pnl(t) for t in fills), Decimal("0"))

        first = fills[0]
        result.append(TradeGroup(
            market=market,
            market_title=first.market_title,
            category=first.category,
            outcome=outcome,
            last_match_time=last_match_time,
            avg_buy_price=avg_buy_price,
            total_bought=total_bought,
            pnl=pnl,
        ))

    return sorted(result, key=lambda g: int(g.last_match_time), reverse=True)
