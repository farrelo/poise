import json
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal

from ..api.clob import ClobAPI
from ..api.data import DataAPI
from ..api.gamma import GammaAPI
from ..engine.pnl import daily_pnl, group_trades, total_pnl
from ..models.position import Position
from ..models.trade import Trade
from ..models.trade_group import TradeGroup

def _category_from_slug(slug: str) -> str:
    prefix = slug.split("-")[0] if slug else ""
    return prefix


def _current_price_for_outcome(market_info: dict, outcome: str) -> Decimal:
    """Extract the current price for a named outcome from a Gamma market dict."""
    try:
        raw_outcomes = market_info.get("outcomes", "[]")
        raw_prices = market_info.get("outcomePrices", "[]")
        outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes
        prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
        target = outcome.strip().lower()
        for i, o in enumerate(outcomes):
            if str(o).strip().lower() == target:
                return Decimal(str(prices[i]))
    except Exception:
        pass
    return Decimal("0")


class AccountService:
    """Orchestrates API calls and produces typed, validated domain objects."""

    _SETTLED = {"MATCHED", "MINED", "CONFIRMED"}

    def __init__(self, api: ClobAPI, gamma: GammaAPI, data: DataAPI):
        self._api = api
        self._gamma = gamma
        self._data = data
        self.wallet_address = api.wallet_address

    def get_wallet_address(self) -> str:
        return self.wallet_address

    def get_balance(self) -> Decimal:
        raw = self._api.get_balance_allowance()
        return Decimal(raw.get("balance", "0")) / Decimal("1000000")

    def get_trades(self) -> list[Trade]:
        raw_trades = self._api.get_trades()
        trades = []
        for t in raw_trades:
            trades.append(Trade(
                id=t["id"],
                market=t["market"],
                asset_id=t["asset_id"],
                side=t["side"],
                size=Decimal(t["size"]),
                price=Decimal(t["price"]),
                fee_rate_bps=Decimal(t["fee_rate_bps"]),
                status=t["status"],
                match_time=t["match_time"],
                outcome=t["outcome"],
                transaction_hash=t["transaction_hash"],
                trader_side=t["trader_side"],
            ))
        return trades

    def get_trade_groups(self) -> list[TradeGroup]:
        """
        Returns all positions grouped by (conditionId, outcome), newest first.

        Uses the Data API as the primary source so that:
        - Market titles are always present (no Gamma lookup needed)
        - REDEEM activities (claimed winnings) are included in PnL
        """
        activities = self._data.get_activity()

        # Build Trade objects from TRADE activities
        trades: list[Trade] = []
        for a in activities:
            if a["type"] != "TRADE":
                continue
            trades.append(Trade(
                id=a["transactionHash"],
                market=a["conditionId"],
                asset_id=a.get("asset", ""),
                side=a["side"],
                size=Decimal(str(a["size"])),
                price=Decimal(str(a["price"])),
                fee_rate_bps=Decimal("0"),
                status="CONFIRMED",
                match_time=str(a["timestamp"]),
                outcome=a["outcome"],
                transaction_hash=a["transactionHash"],
                trader_side="",
                market_title=a["title"],
                category=_category_from_slug(a["slug"]),
            ))

        groups = group_trades(trades)

        # Pre-group REDEEM activities by conditionId
        redeems: dict[str, list[dict]] = defaultdict(list)
        for a in activities:
            if a["type"] == "REDEEM":
                redeems[a["conditionId"]].append(a)

        # Augment each group's PnL with any REDEEM for the same market
        result: list[TradeGroup] = []
        grouped_markets: set[str] = set()
        for g in groups:
            grouped_markets.add(g.market)
            market_redeems = redeems.get(g.market, [])
            if market_redeems:
                redeem_total = sum(Decimal(str(r["usdcSize"])) for r in market_redeems)
                latest_redeem = str(max(int(r["timestamp"]) for r in market_redeems))
                new_last_time = str(max(int(g.last_match_time), int(latest_redeem)))
                result.append(replace(g, pnl=g.pnl + redeem_total, last_match_time=new_last_time))
            else:
                result.append(g)

        # Handle REDEEM-only entries (claimed with no corresponding TRADE in the data)
        for cid, market_redeems in redeems.items():
            if cid in grouped_markets:
                continue
            redeem_total = sum(Decimal(str(r["usdcSize"])) for r in market_redeems)
            latest = max(market_redeems, key=lambda r: int(r["timestamp"]))
            result.append(TradeGroup(
                market=cid,
                market_title=latest["title"],
                category=_category_from_slug(latest["slug"]),
                outcome="—",
                last_match_time=str(latest["timestamp"]),
                avg_buy_price=Decimal("0"),
                total_bought=Decimal("0"),
                pnl=redeem_total,
            ))

        return sorted(result, key=lambda g: int(g.last_match_time), reverse=True)

    def _enrich_trades(self, trades: list[Trade]) -> list[Trade]:
        """Adds market_title and category from the Gamma API."""
        if not trades:
            return trades
        condition_ids = list({t.market for t in trades})
        try:
            markets = self._gamma.get_markets_by_condition_ids(condition_ids)
            market_map = {m.get("conditionId", ""): m for m in markets}
        except Exception:
            market_map = {}
        result = []
        for t in trades:
            info = market_map.get(t.market, {})
            title = info.get("question") or info.get("title") or ""
            slug = info.get("slug", "")
            category = _category_from_slug(slug)
            result.append(replace(t, market_title=title, category=category))
        return result

    def get_last_trades(self, n: int = 20) -> list[Trade]:
        """Returns the last n settled fills, enriched with market metadata."""
        all_trades = self.get_trades()
        settled = sorted(
            (t for t in all_trades if t.status in self._SETTLED),
            key=lambda t: int(t.match_time),
            reverse=True,
        )[:n]
        return self._enrich_trades(settled)

    def _activities_as_trades(self, activities: list[dict]) -> list[Trade]:
        """
        Converts data API activities to Trade objects for use in PnL calculations.

        TRADE  → converted directly (fee_rate_bps=0 matches actual API values).
        REDEEM → converted as a SELL at effective price usdcSize/size
                 (1.00 for winning claims, 0.50 for 50-50 resolutions, etc.).
        """
        trades: list[Trade] = []
        for a in activities:
            if a["type"] == "TRADE":
                trades.append(Trade(
                    id=a["transactionHash"],
                    market=a["conditionId"],
                    asset_id=a.get("asset", ""),
                    side=a["side"],
                    size=Decimal(str(a["size"])),
                    price=Decimal(str(a["price"])),
                    fee_rate_bps=Decimal("0"),
                    status="CONFIRMED",
                    match_time=str(a["timestamp"]),
                    outcome=a["outcome"],
                    transaction_hash=a["transactionHash"],
                    trader_side="",
                ))
            elif a["type"] == "REDEEM":
                size = Decimal(str(a["size"]))
                if not size:
                    continue
                price = Decimal(str(a["usdcSize"])) / size
                trades.append(Trade(
                    id=a["transactionHash"],
                    market=a["conditionId"],
                    asset_id="",
                    side="SELL",
                    size=size,
                    price=price,
                    fee_rate_bps=Decimal("0"),
                    status="CONFIRMED",
                    match_time=str(a["timestamp"]),
                    outcome="",
                    transaction_hash=a["transactionHash"],
                    trader_side="",
                ))
        return trades

    def get_open_positions(self) -> list[Position]:
        """
        Returns positions where the user still holds shares (not settled/redeemed).

        Sorted by most recent BUY timestamp, newest first.
        Current prices are fetched from the Gamma API.
        """
        activities = self._data.get_activity()

        # Markets with a REDEEM are settled — exclude them from open positions
        redeemed: set[str] = {a["conditionId"] for a in activities if a["type"] == "REDEEM"}

        # Group TRADE fills by (conditionId, outcome)
        buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
        meta: dict[str, dict] = {}  # conditionId → {title, slug}
        for a in activities:
            if a["type"] != "TRADE":
                continue
            key = (a["conditionId"], a["outcome"])
            buckets[key].append(a)
            if a["conditionId"] not in meta:
                meta[a["conditionId"]] = {"title": a["title"], "slug": a["slug"]}

        open_raw = []
        for (cid, outcome), fills in buckets.items():
            if cid in redeemed:
                continue
            buys = [f for f in fills if f["side"] == "BUY"]
            sells = [f for f in fills if f["side"] == "SELL"]
            total_buy_size = sum(Decimal(str(f["size"])) for f in buys)
            total_sell_size = sum(Decimal(str(f["size"])) for f in sells)
            net_shares = total_buy_size - total_sell_size
            if net_shares <= Decimal("0"):
                continue
            total_buy_value = sum(
                Decimal(str(f["price"])) * Decimal(str(f["size"])) for f in buys
            )
            avg_price = total_buy_value / total_buy_size if total_buy_size else Decimal("0")
            last_buy_time = str(max(int(f["timestamp"]) for f in buys))
            open_raw.append({
                "conditionId": cid,
                "outcome": outcome,
                "avg_buy_price": avg_price,
                "net_shares": net_shares,
                "total_bought": total_buy_value,
                "last_buy_time": last_buy_time,
                "title": meta[cid]["title"],
                "slug": meta[cid]["slug"],
            })

        open_raw.sort(key=lambda p: int(p["last_buy_time"]), reverse=True)

        # Fetch current prices and active status from Gamma API
        condition_ids = list({p["conditionId"] for p in open_raw})
        try:
            markets = self._gamma.get_markets_by_condition_ids(condition_ids)
            market_map: dict[str, dict] = {m["conditionId"]: m for m in markets}
        except Exception:
            market_map = {}

        # Build positions, skipping dust entries.
        # A position is only shown when its current market value exceeds $0.01.
        # This handles both lost outcomes (price ≈ 0) and residual micro-lots
        # left over from partial fills (net_shares × price ≤ $0.01).
        result: list[Position] = []
        for p in open_raw:
            info = market_map.get(p["conditionId"], {})
            price = _current_price_for_outcome(info, p["outcome"])
            if price * p["net_shares"] <= Decimal("0.01"):
                continue
            result.append(Position(
                market=p["conditionId"],
                market_title=p["title"],
                category=_category_from_slug(p["slug"]),
                outcome=p["outcome"],
                avg_buy_price=p["avg_buy_price"],
                current_price=price,
                net_shares=p["net_shares"],
                total_bought=p["total_bought"],
                last_buy_time=p["last_buy_time"],
            ))
        return result

    def get_pnl_summary(self) -> tuple[Decimal, list[tuple[str, Decimal]]]:
        """Returns (total_pnl, daily_pnl_list) using the Data API as source.

        Includes both TRADE fills and REDEEM (claimed winnings) so the numbers
        are consistent with the Trades screen.
        """
        activities = self._data.get_activity()
        trades = self._activities_as_trades(activities)
        daily = daily_pnl(trades)
        return total_pnl(daily), daily
