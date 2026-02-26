import httpx

_DATA_HOST = "https://data-api.polymarket.com"


class DataAPI:
    """Raw HTTP calls to the Polymarket Data API. No logic, no parsing."""

    def __init__(self, wallet_address: str):
        self._wallet = wallet_address

    def get_activity(self, limit: int = 500) -> list[dict]:
        """
        Returns all user activity entries (type TRADE or REDEEM).
        Each entry includes title, slug, conditionId, side, price, size, usdcSize, timestamp.
        """
        resp = httpx.get(
            f"{_DATA_HOST}/activity",
            params={"user": self._wallet, "limit": limit},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
