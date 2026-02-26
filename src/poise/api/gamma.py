import urllib.parse

import httpx

_GAMMA_HOST = "https://gamma-api.polymarket.com"


class GammaAPI:
    """Raw HTTP calls to the Polymarket Gamma API. No logic, no parsing."""

    def get_markets_by_condition_ids(self, condition_ids: list[str]) -> list[dict]:
        """Returns raw market dicts for the given condition IDs."""
        # The Gamma API requires repeated params, not a comma-joined value:
        # ?condition_ids=a&condition_ids=b  (works)
        # ?condition_ids=a,b               (returns empty)
        params = [("condition_ids", cid) for cid in condition_ids]
        url = f"{_GAMMA_HOST}/markets?" + urllib.parse.urlencode(params)
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
