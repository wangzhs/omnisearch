# OmniSearch

中文说明见 [README.zh-CN.md](README.zh-CN.md)。

OmniSearch is a local-first tool layer for AI agents, now primarily focused on A-share stock data workflows.

It is still not a search engine. Today the primary use case is the stock data layer, while the original web tooling remains available as supporting capability:

- `/search` backed by SearXNG
- `/extract` backed by `requests` + Trafilatura
- `/research` as a minimal search + extract orchestration
- `GET /company/*` as the primary A-share stock data layer

## What It Does

OmniSearch exposes one FastAPI service and keeps responsibilities narrow:

- web search stays behind `/search`
- content extraction stays behind `/extract`
- research orchestration stays behind `/research`
- stock data is normalized into local SQLite and served from `/company/*`

There is no indexing engine, ranking model, auth, billing, admin dashboard, or LLM summarization here.

## Stock API Contract

The stock layer is the primary contract of this repository.

Core internal entities:

- `company_profile`
- `event`
- `financial_summary`
- `price_daily`

Primary endpoint:

- `GET /company/{ticker}/overview`

Supporting stock endpoints:

- `GET /company/{ticker}`
- `GET /company/{ticker}/events`
- `GET /company/{ticker}/financials`
- `GET /company/{ticker}/prices`
- `GET /company/{ticker}/timeline`
- `GET /company/{ticker}/risk-flags`

Overview is the recommended entry point for agents because it aggregates:

- normalized company profile
- latest financial summary
- latest daily price
- recent events
- risk flags
- `data_status` for company, financials, prices, and events

## Project Structure

```text
app/
  api/
  collectors/
  core/
  db/
  extractors/
  models/
  normalizers/
  providers/
  research/
  schemas/
  services/
```

## Requirements

- Python 3.11+
- Docker and Docker Compose for the bundled SearXNG setup
- `TUSHARE_TOKEN` if you want company profile and financial summary collection

## One-Command Start

```bash
make up
```

Equivalent:

```bash
docker compose up --build
```

This starts:

- OmniSearch API on `http://localhost:8000`
- SearXNG on `http://localhost:8080`

The API container persists local stock cache data under `./data`.

## Local Setup

1. Create env file:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Start SearXNG:

```bash
docker compose up -d searxng
```

4. Start the API:

```bash
uvicorn app.main:app --reload
```

## Key Env Vars

```env
API_PORT=8000
SEARXNG_BASE_URL=http://localhost:8080
SQLITE_DB_PATH=./data/omnisearch.db
RESEARCH_PLANNER=rule
TUSHARE_TOKEN=
TUSHARE_BASE_URL=
CNINFO_ANNOUNCEMENTS_URL=https://www.cninfo.com.cn/new/hisAnnouncement/query
STOCK_DATA_TTL_HOURS=24
```

Notes:

- `TUSHARE_TOKEN` is required for `/company/{ticker}` and `/company/{ticker}/financials`.
- If you run a local Tushare-compatible proxy, set `TUSHARE_BASE_URL=http://tushare.xyz`.
- AKShare is used for daily prices.
- CNInfo is used for announcement and event collection.
- Stock data is cached locally in SQLite and refreshed on demand.

## Architecture

```text
Client / Agent
  -> OmniSearch API (FastAPI)
       -> SearXNG
       -> requests + Trafilatura
       -> SQLite
       -> Tushare / CNInfo / AKShare
```

## API Examples

### Healthcheck

```bash
curl http://localhost:8000/health
```

### Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"fastapi searxng","top_k":5}'
```

### Extract

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

### Research

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query":"000001 业绩","top_k":2}'
```

`/research` keeps the existing search + extract flow. If the query contains an A-share ticker such as `000001`, the response also includes `stock_context` when local stock data can be collected.

### Company Overview

Recommended first call for agents:

```bash
curl "http://localhost:8000/company/000001/overview?refresh=true"
```

### Company Profile

```bash
curl "http://localhost:8000/company/000001"
```

### Company Events

```bash
curl "http://localhost:8000/company/000001/events?limit=10"
```

### Company Financials

```bash
curl "http://localhost:8000/company/000001/financials?limit=4"
```

### Company Prices

```bash
curl "http://localhost:8000/company/000001/prices?limit=30"
```

### Company Overview

```bash
curl "http://localhost:8000/company/000001/overview"
```

### Company Timeline

```bash
curl "http://localhost:8000/company/000001/timeline"
```

### Company Risk Flags

```bash
curl "http://localhost:8000/company/000001/risk-flags"
```

### Price Debug

```bash
curl "http://localhost:8000/company/002837/prices?limit=5&debug=true"
```

### Event Debug

```bash
curl "http://localhost:8000/company/002837/events?limit=10&refresh=true&debug=true"
```

### Local Sync / Warm Cache

```bash
python -m app.scripts.sync_stock --tickers 000001,002837 --refresh --price-limit 60 --event-limit 10
```

Or via `make`:

```bash
TICKERS=000001,002837 REFRESH=1 PRICE_LIMIT=60 EVENT_LIMIT=10 make sync
```

The sync command warms:

- company profile
- financial summaries
- daily prices
- recent events
- aggregate overview

The command also prints:

- source-level debug for prices
- source-level debug for events
- per-ticker failure summary

## Notes

- This repo remains a tool layer, not a search engine.
- The stock layer is intentionally vertical and A-share focused.
- `/company/{ticker}/overview` is the main stock entry point.
- Current risk flags are heuristic and deterministic. There is no LLM summarization.
- `timeline` now emphasizes major financial updates and large price moves.
- `risk-flags` now surfaces missing data, drawdowns, volatility, and low-margin or negative-growth signals.
- Docker Compose mode keeps the local-first workflow intact.
