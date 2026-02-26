import logging

from textual.app import App
from textual.logging import TextualHandler
from .api.clob import ClobAPI
from .api.data import DataAPI
from .api.gamma import GammaAPI
from .config.settings import load_settings
from .services.account import AccountService
from .ui.home import HomeScreen
from .ui.trades import TradesScreen


class PoiseApp(App):
    TITLE = "Poise - Polymarket Trading Terminal"
    BINDINGS = [
        ("h", "home", "Home"),
        ("t", "trades", "Trades"),
        ("q", "quit", "Quit")
    ]

    def __init__(self) -> None:
        super().__init__()
        settings = load_settings()
        self._service = AccountService(ClobAPI(settings), GammaAPI(), DataAPI(settings.wallet_address))

    def on_mount(self) -> None:
        self.push_screen(HomeScreen(self._service))

    def action_home(self) -> None:
        if not isinstance(self.screen, HomeScreen):
            self.switch_screen(HomeScreen(self._service))

    def action_trades(self) -> None:
        if not isinstance(self.screen, TradesScreen):
            self.switch_screen(TradesScreen(self._service))


def main() -> None:
    logging.basicConfig(level=logging.INFO, handlers=[TextualHandler()])
    PoiseApp().run()


if __name__ == "__main__":
    main()
