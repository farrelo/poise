import asyncio
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from ..engine.sizing import unit_bet
from ..models.position import Position
from ..models.trade_group import TradeGroup
from ..services.account import AccountService

_FMT = Decimal("0.01")
_POS_PAGE_SIZE = 20


def _trunc(text: str, width: int) -> str:
    """Truncate text to fit within width chars, appending … if needed."""
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _color_pnl(amount: Decimal) -> str:
    val = abs(amount).quantize(_FMT, rounding=ROUND_HALF_UP)
    if amount > 0:
        return f"[green]+${val}[/green]"
    elif amount < 0:
        return f"[red]-${val}[/red]"
    return "[cyan]$0.00[/cyan]"


def _bar(pct: Decimal, width: int) -> str:
    filled = round(float(pct) / 100 * width)
    return "[green]" + "█" * filled + "[/green][dim]" + "░" * (width - filled) + "[/dim]"


class HomeScreen(Screen):
    CSS = """
    HomeScreen {
        background: $surface;
    }

    #outer-layout {
        height: 1fr;
    }

    /* ── Left panel: account summary + P&L ── */
    #left-panel {
        width: 1fr;
        padding: 1 2;
    }

    .card {
        border: round $primary;
        padding: 1 2;
        margin-bottom: 1;
        height: auto;
    }

    .card-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .row {
        height: 1;
        margin-bottom: 0;
    }

    .label {
        width: 1fr;
        color: $text-muted;
    }

    .value {
        width: auto;
        color: $accent;
        text-style: bold;
    }

    .divider {
        border-bottom: solid $primary;
        height: 1;
        margin: 1 0;
    }

    #pnl-total {
        width: auto;
        color: $accent;
        text-style: bold;
    }

    #pnl-content {
        width: 1fr;
        margin-top: 1;
    }

    /* ── Right panel: current positions ── */
    #right-panel {
        width: 3fr;
        border-left: solid $primary;
        padding: 1 2;
    }

    #positions-card {
        height: 24;
        border: round $primary;
        padding: 1 2;
    }

    #pos-table {
        height: 1fr;
        width: 1fr;
        margin: 1 0;
    }

    #pos-pagination {
        height: 3;
        align: center middle;
        border-top: solid $panel;
    }

    #pos-pagination Button {
        width: 5;
        min-width: 5;
        height: 3;
    }

    #pos-page-label {
        height: 3;
        width: 12;
        content-align: center middle;
        color: $text-muted;
    }

    #category-card {
        height: auto;
        border: round $primary;
        padding: 1 2;
        margin-top: 1;
    }

    #cat-content {
        margin-top: 1;
    }
    """

    def __init__(self, service: AccountService) -> None:
        super().__init__()
        self._service = service
        self._all_positions: list[Position] = []
        self._pos_page: int = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="outer-layout"):
            with VerticalScroll(id="left-panel"):
                with Vertical(classes="card"):
                    yield Label("Account Summary", classes="card-title")
                    with Horizontal(classes="row"):
                        yield Label("Account", classes="label")
                        yield Static("...", id="address", classes="value")
                    with Horizontal(classes="row"):
                        yield Label("Balance", classes="label")
                        yield Static("...", id="balance", classes="value")
                    with Horizontal(classes="row"):
                        yield Label("Unit Bet (5%)", classes="label")
                        yield Static("...", id="unit-bet", classes="value")
                with Vertical(classes="card"):
                    yield Label("P&L Summary", classes="card-title")
                    with Horizontal(classes="row"):
                        yield Label("Total Volume", classes="label")
                        yield Static("...", id="total-volume", classes="value")
                    with Horizontal(classes="row"):
                        yield Label("Total PnL", classes="label")
                        yield Static("...", id="pnl-total")
                    yield Static("", classes="divider")
                    yield Label("Daily Summary", classes="card-title")
                    yield Static("Loading...", id="pnl-content")
            with VerticalScroll(id="right-panel"):
                with Vertical(id="positions-card"):
                    yield Label("Current Position", classes="card-title")
                    yield DataTable(id="pos-table", cursor_type="row")
                    with Horizontal(id="pos-pagination"):
                        yield Button("<", id="pos-prev", disabled=True)
                        yield Label("—", id="pos-page-label")
                        yield Button(">", id="pos-next", disabled=True)
                with Vertical(id="category-card"):
                    yield Label("Category Breakdown", classes="card-title")
                    yield Static("[dim]Loading...[/dim]", id="cat-content")
        yield Footer()

    _COL_WIDTHS = (40, 8, 14, 16, 8, 8, 8)
    _CAT_WIDTHS = (10, 12)
    _BAR_WIDTH = 20

    async def on_mount(self) -> None:
        pos_table = self.query_one("#pos-table", DataTable)
        for label, w in zip(
            ("Market", "Category", "Outcome", "Avg → Now", "Traded", "To Win", "Value"),
            self._COL_WIDTHS,
        ):
            pos_table.add_column(label, width=w)

        address, balance, (total, daily), positions, groups = await asyncio.gather(
            asyncio.to_thread(self._service.get_wallet_address),
            asyncio.to_thread(self._service.get_balance),
            asyncio.to_thread(self._service.get_pnl_summary),
            asyncio.to_thread(self._service.get_open_positions),
            asyncio.to_thread(self._service.get_trade_groups),
        )

        bet = unit_bet(balance)
        self._refresh_address(address)
        self._refresh_summary(balance, bet)
        volume = sum(g.total_bought for g in groups)
        self._refresh_pnl(total, daily, volume)
        self._all_positions = positions
        self._render_positions()
        self._render_category_breakdown(groups)

    def _refresh_address(self, address: str) -> None:
        if not address or len(address) < 6:
            short = address
        else:
            short = f"{address[:2]}....{address[-4:]}"
        self.query_one("#address", Static).update(short)

    def _refresh_summary(self, balance: Decimal, bet: Decimal) -> None:
        self.query_one("#balance", Static).update(
            f"${balance.quantize(_FMT, rounding=ROUND_HALF_UP)}"
        )
        self.query_one("#unit-bet", Static).update(
            f"${bet.quantize(_FMT, rounding=ROUND_HALF_UP)}"
        )

    def _refresh_pnl(self, total: Decimal, daily: list[tuple[str, Decimal]], volume: Decimal = Decimal("0")) -> None:
        self.query_one("#total-volume", Static).update(
            f"${volume.quantize(_FMT, rounding=ROUND_HALF_UP)}"
        )
        self.query_one("#pnl-total", Static).update(_color_pnl(total))
        if not daily:
            self.query_one("#pnl-content", Static).update("[dim]No trades found.[/dim]")
            return
        lines = [f"{day}    {_color_pnl(pnl)}" for day, pnl in daily]
        self.query_one("#pnl-content", Static).update("\n".join(lines))

    def _render_positions(self) -> None:
        table = self.query_one("#pos-table", DataTable)
        table.clear()

        total = len(self._all_positions)
        total_pages = max(1, (total + _POS_PAGE_SIZE - 1) // _POS_PAGE_SIZE)
        self._pos_page = min(self._pos_page, total_pages - 1)
        start = self._pos_page * _POS_PAGE_SIZE
        page_items = self._all_positions[start : start + _POS_PAGE_SIZE]

        w = self._COL_WIDTHS
        for p in page_items:
            name = _trunc(p.market_title or p.market, w[0])
            cat = _trunc(p.category, w[1])
            outcome = _trunc(p.outcome, w[2])
            avg_now = _trunc(
                f"${p.avg_buy_price.quantize(_FMT, rounding=ROUND_HALF_UP)}"
                f" → ${p.current_price.quantize(_FMT, rounding=ROUND_HALF_UP)}",
                w[3],
            )
            traded = _trunc(f"${p.total_bought.quantize(_FMT, rounding=ROUND_HALF_UP)}", w[4])
            to_win = _trunc(f"${p.net_shares.quantize(_FMT, rounding=ROUND_HALF_UP)}", w[5])
            value = _trunc(
                f"${(p.net_shares * p.current_price).quantize(_FMT, rounding=ROUND_HALF_UP)}",
                w[6],
            )
            table.add_row(name, cat, outcome, avg_now, traded, to_win, value)

        label = self.query_one("#pos-page-label", Label)
        label.update(f"{self._pos_page + 1} / {total_pages}")
        self.query_one("#pos-prev", Button).disabled = self._pos_page == 0
        self.query_one("#pos-next", Button).disabled = self._pos_page >= total_pages - 1

    def _render_category_breakdown(self, groups: list[TradeGroup]) -> None:
        traded: dict[str, Decimal] = defaultdict(Decimal)
        pnl_map: dict[str, Decimal] = defaultdict(Decimal)
        for g in groups:
            cat = g.category or "—"
            traded[cat] += g.total_bought
            pnl_map[cat] += g.pnl

        total = sum(traded.values())
        widget = self.query_one("#cat-content", Static)
        if not total:
            widget.update("[dim]No data.[/dim]")
            return

        cw = self._CAT_WIDTHS
        rows = sorted(traded.keys(), key=lambda c: traded[c], reverse=True)
        lines = []
        for cat in rows:
            pct = traded[cat] / total * Decimal("100")
            pct_str = f"{float(pct):5.1f}%"
            traded_str = f"${traded[cat].quantize(_FMT, rounding=ROUND_HALF_UP)}"
            cat_col = _trunc(cat, cw[0]).ljust(cw[0])
            traded_col = _trunc(traded_str, cw[1]).rjust(cw[1])
            lines.append(
                f"[bold]{cat_col}[/bold] {_bar(pct, self._BAR_WIDTH)} {pct_str}"
                f"  traded: [cyan]{traded_col}[/cyan]  pnl: {_color_pnl(pnl_map[cat])}"
            )
        widget.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        total_pages = max(
            1, (len(self._all_positions) + _POS_PAGE_SIZE - 1) // _POS_PAGE_SIZE
        )
        btn_id = event.button.id
        if btn_id == "pos-prev" and self._pos_page > 0:
            self._pos_page -= 1
            self._render_positions()
        elif btn_id == "pos-next" and self._pos_page < total_pages - 1:
            self._pos_page += 1
            self._render_positions()
