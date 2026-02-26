import asyncio
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label

from ..models.trade_group import TradeGroup
from ..services.account import AccountService

_FMT = Decimal("0.01")
_PAGE_SIZE = 50


def _trunc(text: str, width: int) -> str:
    """Truncate text to fit within width chars, appending … if needed."""
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _fmt_pnl(pnl: Decimal) -> str:
    val = abs(pnl).quantize(_FMT, rounding=ROUND_HALF_UP)
    if pnl > 0:
        return f"[green]+${val}[/green]"
    elif pnl < 0:
        return f"[red]-${val}[/red]"
    return "[cyan]$0.00[/cyan]"


def _cat_to_btn_suffix(cat: str) -> str:
    """Convert a category key to a safe button id suffix."""
    return "other" if cat == "—" else cat


def _btn_suffix_to_cat(suffix: str) -> str:
    return "—" if suffix == "other" else suffix


class TradesScreen(Screen):
    CSS = """
    TradesScreen {
        background: $surface;
    }

    #main-layout {
        height: 1fr;
    }

    #table-area {
        width: 1fr;
    }

    DataTable {
        margin: 1 2 0 2;
        height: 1fr;
    }

    #trade-pagination {
        height: 3;
        align: center middle;
        padding: 0 2;
        border-top: solid $panel;
    }

    #trade-pagination Button {
        width: 5;
        min-width: 5;
        height: 3;
    }

    #trade-page-label {
        height: 3;
        width: 12;
        content-align: center middle;
        color: $text-muted;
    }

    #filter-panel {
        width: 26;
        padding: 1 1;
        border-left: solid $primary;
    }

    .filter-btn {
        width: 100%;
        margin-bottom: 1;
    }

    .filter-btn.active {
        background: $accent;
        color: $background;
        text-style: bold;
    }
    """

    def __init__(self, service: AccountService) -> None:
        super().__init__()
        self._service = service
        self._all_groups: list[TradeGroup] = []
        self._active_filters: set[str] = set()
        self._trade_page: int = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-layout"):
            with Vertical(id="table-area"):
                yield DataTable(cursor_type="row")
                with Horizontal(id="trade-pagination"):
                    yield Button("<", id="trade-prev", disabled=True)
                    yield Label("—", id="trade-page-label")
                    yield Button(">", id="trade-next", disabled=True)
            with VerticalScroll(id="filter-panel"):
                yield Button("All", id="filter-all", classes="filter-btn")
        yield Footer()

    _COL_WIDTHS = (16, 48, 8, 14, 8, 10, 10)

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for label, w in zip(
            ("Date / Time (JKT)", "Name", "Category", "Outcome", "Avg Price", "Total", "PnL"),
            self._COL_WIDTHS,
        ):
            table.add_column(label, width=w)

        self._all_groups = await asyncio.to_thread(self._service.get_trade_groups)

        # Sort categories by frequency descending
        counts = Counter(g.category for g in self._all_groups if g.category)
        sorted_cats = sorted(counts, key=lambda c: counts[c], reverse=True)

        filter_panel = self.query_one("#filter-panel", VerticalScroll)
        for cat in sorted_cats:
            filter_panel.mount(
                Button(cat, id=f"filter-{_cat_to_btn_suffix(cat)}", classes="filter-btn")
            )

        self._render_table()

    def _filtered_groups(self) -> list[TradeGroup]:
        if self._active_filters:
            return [g for g in self._all_groups if g.category in self._active_filters]
        return self._all_groups

    def _render_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        groups = self._filtered_groups()
        total_pages = max(1, (len(groups) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        self._trade_page = min(self._trade_page, total_pages - 1)
        start = self._trade_page * _PAGE_SIZE
        page_groups = groups[start : start + _PAGE_SIZE]

        w = self._COL_WIDTHS
        for g in page_groups:
            dt = datetime.fromtimestamp(int(g.last_match_time))
            date_str = dt.strftime("%Y-%m-%d %H:%M")
            name = _trunc(g.market_title or g.market, w[1])
            cat = _trunc(g.category, w[2])
            outcome = _trunc(g.outcome, w[3])
            avg_price_str = _trunc(
                f"${g.avg_buy_price.quantize(_FMT, rounding=ROUND_HALF_UP)}", w[4]
            )
            total_str = _trunc(
                f"${g.total_bought.quantize(_FMT, rounding=ROUND_HALF_UP)}", w[5]
            )
            table.add_row(
                date_str, name, cat, outcome,
                avg_price_str, total_str, _fmt_pnl(g.pnl),
            )

        label = self.query_one("#trade-page-label", Label)
        label.update(f"{self._trade_page + 1} / {total_pages}")
        self.query_one("#trade-prev", Button).disabled = self._trade_page == 0
        self.query_one("#trade-next", Button).disabled = self._trade_page >= total_pages - 1

    def _sync_button_states(self) -> None:
        for btn in self.query(".filter-btn"):
            btn_id = btn.id or ""
            if btn_id == "filter-all":
                continue
            suffix = btn_id.removeprefix("filter-")
            cat = _btn_suffix_to_cat(suffix)
            if cat in self._active_filters:
                btn.add_class("active")
            else:
                btn.remove_class("active")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "trade-prev":
            if self._trade_page > 0:
                self._trade_page -= 1
                self._render_table()
            return

        if btn_id == "trade-next":
            groups = self._filtered_groups()
            total_pages = max(1, (len(groups) + _PAGE_SIZE - 1) // _PAGE_SIZE)
            if self._trade_page < total_pages - 1:
                self._trade_page += 1
                self._render_table()
            return

        if not btn_id.startswith("filter-"):
            return

        if btn_id == "filter-all":
            self._active_filters.clear()
        else:
            suffix = btn_id.removeprefix("filter-")
            cat = _btn_suffix_to_cat(suffix)
            if cat in self._active_filters:
                self._active_filters.discard(cat)
            else:
                self._active_filters.add(cat)

        self._trade_page = 0  # reset to first page on filter change
        self._sync_button_states()
        self._render_table()
