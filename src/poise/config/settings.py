import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env relative to this file so it's found regardless of CWD
# (e.g. when launched via `textual run --dev`)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(_ENV_FILE)


@dataclass(frozen=True)
class Settings:
    wallet_address: str
    private_key: str
    api_key: str
    api_secret: str
    api_passphrase: str
    chain_id: int = 137


def load_settings() -> Settings:
    missing = [
        var for var in (
            "POLYMARKET_WALLET_ADDRESS",
            "POLYMARKET_PK",
            "POLYMARKET_API_KEY",
            "POLYMARKET_API_SECRET",
            "POLYMARKET_API_PASSPHRASE",
        )
        if not os.getenv(var)
    ]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    return Settings(
        wallet_address=os.environ["POLYMARKET_WALLET_ADDRESS"],
        private_key=os.environ["POLYMARKET_PK"],
        api_key=os.environ["POLYMARKET_API_KEY"],
        api_secret=os.environ["POLYMARKET_API_SECRET"],
        api_passphrase=os.environ["POLYMARKET_API_PASSPHRASE"],
    )
