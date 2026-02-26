# Poise

A Polymarket trading terminal built with Python and shown with TUI [Textual]. Gives you a real-time overview of your positions, P&L, and trade history.

Note: This project are (mostly) vibe-coded using Claude.

<img width="1906" height="837" alt="image" src="https://github.com/user-attachments/assets/ed0e7a5b-3670-4d84-9416-daef5655d80e" />
<img width="1917" height="835" alt="image" src="https://github.com/user-attachments/assets/a079cf24-8237-48af-b108-42d6121482c2" />


## Features

- **Home** — account summary, unrealized/realized P&L, open positions, category breakdown
- **Trades** — full trade history with category filtering and pagination
- Runs in any modern terminal, or in a browser via `textual serve`

## Requirements

- Python 3.10+
- A Polymarket account with API credentials

## Setup

1. Clone the repo and install dependencies:

```bash
pip install -r src/poise/requirements.txt
pip install -e .
```

2. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
POLYMARKET_WALLET_ADDRESS=0x...
POLYMARKET_API_KEY=your-api-key
POLYMARKET_API_SECRET=base64-encoded-secret
POLYMARKET_API_PASSPHRASE=your-passphrase
POLYMARKET_PK=your-private-key
```

> Your API credentials can be found in your Polymarket account settings. The private key is only used locally and is never transmitted.

> Polymarket PK are obtained via private key on your wallet.

## Running

**In the terminal:**

```bash
poise
```

**In the browser** (works on any OS without terminal setup):

```bash
textual serve --command "python -m poise"
```

Then open [http://localhost:8000](http://localhost:8000).

## Keybindings

| Key | Action |
|-----|--------|
| `h` | Home screen |
| `t` | Trades screen |
| `q` | Quit |
