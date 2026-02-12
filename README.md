# Stock Research MCP Server (Python)

Production-grade MCP server for stock intelligence with:
- Alpha Vantage + Finnhub provider fallback
- Deterministic indicators/metrics/scoring
- Claude narrative analysis constrained to computed data
- Dual MCP transport modes: `stdio` (Claude Desktop local) and `http` with selectable SSE/streamable endpoints (Render)

## File Tree

```text
mcp_server/
├── main.py
├── tools/
│   └── stock_tools.py
├── providers/
│   ├── base.py
│   ├── alpha_vantage.py
│   ├── finnhub.py
│   └── router.py
├── scoring/
│   └── engine.py
├── indicators/
│   └── technical.py
├── analysis/
│   ├── metrics.py
│   ├── signal_engine.py
│   └── claude_engine.py
├── schemas/
│   └── models.py
├── config/
│   └── settings.py
└── utils/
    ├── logging.py
    └── http.py

tests/
├── test_indicators.py
├── test_metrics.py
└── test_scoring.py
```

## Requirements

- Python 3.11+
- API keys:
  - `CLAUDE_API_KEY`
  - `ALPHA_VANTAGE_API_KEY`
  - `FINNHUB_API_KEY`

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
```

## Run (Claude Desktop local via stdio)

Set in `.env`:

```text
TRANSPORT_MODE=stdio
```

Run:

```bash
python -m mcp_server.main
```

## Run (Render remote via HTTP)

Set in `.env`:

```text
TRANSPORT_MODE=http
HTTP_TRANSPORT=sse  # or streamable
HOST=0.0.0.0
PORT=8000
```

Run:

```bash
python -m mcp_server.main
```

## Tools

- Existing research/report tools:
  - `stock_research_report` (primary)
  - `analyze_stock`
  - `get_price`
  - `get_ohlcv`
  - `get_technicals`
  - `get_fundamentals`
  - `get_news_sentiment`
- Trading-style tools:
  - `get_stock_price`
  - `get_quote`
  - `get_company_profile`
  - `get_candles`
  - `get_stock_news`
  - `get_rsi`
  - `get_macd`
  - `get_key_financials`

## Tests

```bash
pytest -q
```

## Render Deployment

1. Push repo to GitHub.
2. Create a Render Web Service.
3. Build command:
   - `pip install -r requirements.txt`
4. Start command:
   - `python -m mcp_server.main`
5. Environment variables:
   - `TRANSPORT_MODE=http`
   - `HTTP_TRANSPORT=sse` (or `streamable`)
   - `HOST=0.0.0.0`
   - `PORT=8000`
   - `CLAUDE_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `FINNHUB_API_KEY`
6. MCP endpoints:
   - SSE mode (`HTTP_TRANSPORT=sse`):
     - `https://<render-service-domain>/sse`
     - `https://<render-service-domain>/messages/` (POST)
   - Streamable mode (`HTTP_TRANSPORT=streamable`):
     - `https://<render-service-domain>/mcp`
7. Optional health check endpoint:
   - `https://<render-service-domain>/health`

## Claude Desktop Config (local stdio)

Example MCP server entry:

```json
{
  "mcpServers": {
    "stock-research": {
      "command": "python",
      "args": ["-m", "mcp_server.main"],
      "env": {
        "TRANSPORT_MODE": "stdio",
        "CLAUDE_API_KEY": "YOUR_KEY",
        "ALPHA_VANTAGE_API_KEY": "YOUR_KEY",
        "FINNHUB_API_KEY": "YOUR_KEY"
      }
    }
  }
}
```

## Transport Notes

- `TRANSPORT_MODE=auto` (default) auto-selects:
  - `http` when hosted (`PORT` or `RENDER` env present)
  - `stdio` locally
- `HTTP_TRANSPORT=sse` uses:
  - `GET /sse`
  - `POST /messages/`
- `HTTP_TRANSPORT=streamable` uses:
  - `POST /mcp`

