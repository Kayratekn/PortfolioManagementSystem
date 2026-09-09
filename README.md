# AI-Assisted Portfolio Management System

Backend for the graduation project **AI-Assisted Portfolio Management System**.

The backend is built with **FastAPI, SQLAlchemy, Alembic and PostgreSQL**.

For detailed implementation status, validation evidence and scope decisions, see
[`PROJECT_STATUS.md`](PROJECT_STATUS.md).

## Architecture

~~~text
Request -> Controller -> Service -> Repository -> SQLAlchemy -> PostgreSQL
~~~

## Main folders

~~~text
src/
  config/          configuration and dependency wiring
  controller/      FastAPI endpoints
  integrations/    external provider and AI integrations
  model/           SQLAlchemy models
  repositories/    persistence/query layer
  request/         request schemas
  response/        response schemas
  services/        business logic

tests/             automated backend tests
scripts/           bootstrap, backfill and sync commands
alembic/           database migrations
~~~

## Requirements

- Python 3.13
- PostgreSQL
- Git

Final validation used Python 3.13.12.

## Local Setup

~~~powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
~~~

Configure PostgreSQL and required provider/AI settings in `.env`.

Do not commit `.env` or secrets.

## Database

~~~powershell
.\venv\Scripts\python.exe -m alembic upgrade head
~~~

Current validated Alembic head: `20260909_0026`.

## Run

~~~powershell
.\venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
~~~

FastAPI docs:

`http://127.0.0.1:8000/docs`

## Tests

~~~powershell
.\venv\Scripts\python.exe -m pytest -q
~~~

Final backend verification:

- 2036 passed
- 96.89% src statement coverage
- Required coverage: >=70%
- 12 known non-blocking Starlette HTTP-422 deprecation warnings

## Main Backend Capabilities

- authentication and ownership isolation
- Portfolio CRUD
- Transactions, derived Holdings and CashFlow
- multi-currency historical valuation
- weights, MWAC cost basis, realized and unrealized P/L
- historical performance / TWR
- PortfolioSnapshot generation and persisted history
- Asset catalog and AssetPrice persistence
- TCMB FX integration
- TEFAS read, history, metrics and metadata APIs
- benchmark catalog, comparison and synchronization
- Borsa Istanbul precious-metals integration
- Watchlist, Notes and DataSyncRun
- AI Portfolio Analysis
- AI Robustness
- AI Sentiment
- AI analysis history
- report upload and grounded Report Q&A

## External / Deferred Items

These are not missing approved backend implementations:

- real X/Twitter ingestion: waiting for supervisor/team provider decision
- NEWS/RSS ingestion: no approved provider contract yet
- external scheduler registration: shared deployment/operational responsibility
- frontend live integration acceptance: cross-team work
- AI Chat: no approved current requirement
- Bitcoin benchmark, server exports and transaction correction/reversal: no approved current scope evidence

## Status

**Approved backend feature scope is complete.**

Use `PROJECT_STATUS.md` as the detailed technical handoff and implementation-status source of truth.
