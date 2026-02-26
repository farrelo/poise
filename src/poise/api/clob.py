from textual import log

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType

from ..config.settings import Settings


_CLOB_HOST = "https://clob.polymarket.com"

class ClobAPI:
    """Raw HTTP calls to the Polymarket CLOB API. No logic, no parsing."""

    def __init__(self, settings: Settings):
        self.wallet_address = settings.wallet_address
        self._client = ClobClient(
            host=_CLOB_HOST,
            chain_id=settings.chain_id,
            key=settings.private_key,
            creds=ApiCreds(
                api_key=settings.api_key,
                api_secret=settings.api_secret,
                api_passphrase=settings.api_passphrase,
            ),
            signature_type=0,
            funder=settings.wallet_address,
        )

    def get_balance_allowance(self) -> dict:
        """
        Returns raw balance/allowance dict for the Gnosis Safe proxy wallet.
        signature_type=2 (POLY_GNOSIS_SAFE) is where MetaMask users' USDC lives.
        """
        params = BalanceAllowanceParams(
            asset_type=AssetType.COLLATERAL,
            signature_type=2,
        )
        return self._client.get_balance_allowance(params=params)

    def get_trades(self) -> list[dict]:
        """Returns the raw list of trade dicts from the CLOB."""
        return self._client.get_trades()
