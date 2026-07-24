# PROJECT_STATUS.md

## Project identity

- **Project:** AI-Assisted Portfolio Management System
- **Type:** Browser-based web application
- **Team size:** 4
- **Supervisor:** Prof. Dr. Hakan Altınçay
- **Current project stage:** Graduation Project I design completed; Graduation
  Project II implementation has not started
- **Status updated:** 2026-07-24

## Product summary

The system allows an individual investor to manually enter and track TEFAS
funds, precious metals and supported currency-based investments in one
portfolio application. It calculates current and historical portfolio value in
TRY, USD, EUR and GBP, compares performance with selected benchmarks and
provides explainable AI-supported risk and decision-support results.

The application does not trade, connect to bank accounts or provide guaranteed
investment advice.

## User journey

1. The user registers and signs in.
2. The user creates one or more portfolios.
3. The user records `BUY` and `SELL` transactions.
4. The system derives current holdings from transactions.
5. Market-data integrations fetch and update required prices.
6. The backend calculates value, allocation, profit/loss and currency views.
7. The frontend displays dashboard and historical charts.
8. The user compares the portfolio with selected benchmarks.
9. The user may request risk, correlation, stress and sentiment analysis.
10. The user may upload a financial report and ask grounded questions.
11. The user may save notes and export selected results.

## Team responsibilities

| Member | Responsibility |
|---|---|
| Zeynep Geyik | Project management, financial-data integration and preprocessing |
| Kayra Tekin | Backend API, database integration, portfolio calculations and testing |
| Bahattin Tamer Akipek | AI/ML, correlation, risk, sentiment and report-based Q&A |
| Ahmet Arınç Akyıldız | Frontend dashboard and data visualization |

## Selected backend stack

- Python
- FastAPI
- Uvicorn
- Pydantic / Pydantic Settings
- SQLAlchemy
- Alembic
- PostgreSQL
- Pytest
- REST API and JSON
- Git / GitHub

### Documentation mismatch

The main report still refers to MySQL in parts of the implementation section.
The current backend scaffold uses PostgreSQL. The final report, ER diagram and
installation guide must be updated to use one database name consistently.

## Repository structure

```text
ai-portfolio-backend/
├── app/
│   ├── api/v1/endpoints/
│   ├── core/
│   ├── db/
│   ├── integrations/
│   │   ├── ai/
│   │   └── market_data/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── alembic/
│   └── versions/
├── tests/
├── .env.example
├── alembic.ini
├── requirements.txt
├── AGENTS.md
├── PROJECT_STRUCTURE.md
└── PROJECT_STATUS.md
```

## Current implementation status

| Area | Status | Notes |
|---|---|---|
| Backend folder structure | Complete | Layered modular structure created |
| FastAPI application factory | Complete | Application created in `src/main.py` |
| API versioning | Complete | `/api/v1` router configured |
| Health endpoint | Complete | `GET /api/v1/health` |
| Environment configuration | Complete | `.env.example` and Pydantic settings |
| SQLAlchemy base/session | In progress | PostgreSQL engine, session factory and FastAPI DB dependency added; runtime connection not yet tested |
| Alembic | In progress | Alembic configuration and first `users` table migration added; migration execution not yet verified |
| Health test | Written | Must be executed after dependencies are installed |
| Business entities | In progress | `User` entity, base model infrastructure and first migration are created; other planned entities are not started |
| Authentication | In progress | `register`, `login` and `me` endpoints, password hashing, repository, service and JWT flow are implemented; runtime verification is still pending |
| Portfolio calculations | Not started | No transaction or valuation service |
| Market-data integration | Not started | Adapter packages are empty |
| AI integration | Not started | Adapter package is empty |
| Frontend integration | Not started | API contracts not yet delivered |
| Deployment | Not started | Local development first |

### Verification performed

- Project files pass Python syntax compilation.
- The ZIP package structure was inspected.
- Runtime tests were not executed in the generation environment because the
  project dependencies were not installed there.

## Planned entities

| Entity | Purpose | Status |
|---|---|---|
| User | Account, risk profile and preferred currency | Implemented |
| Portfolio | User-owned portfolio | Planned |
| Asset | Fund, metal, currency, crypto or index definition | Planned |
| Transaction | Source-of-truth buy/sell record | Planned |
| AssetPrice | General historical asset prices | Planned |
| ExchangeRate | Dated currency conversion rates | Planned |
| TefasFundDailyData | TEFAS price, investor count, size and share metrics | Planned |
| PortfolioSnapshot | Dated portfolio values in supported currencies | Planned |
| Benchmark | Comparison reference definition | Planned |
| BenchmarkPrice | Historical benchmark values | Planned |
| WatchlistItem | User-selected tracked asset | Planned |
| AIAnalysis | Stored portfolio risk and decision-support result | Planned |
| ExpertSource | User-selectable public financial source | Planned |
| UserExpertSource | User-to-source selection | Planned |
| SentimentPost | Public content and sentiment result | Planned |
| ReportDocument | Uploaded report metadata | Planned |
| ReportChunk | Report text chunks for grounded Q&A | Planned |
| Note | User portfolio or asset note | Planned |
| DataSyncRun | Data-refresh execution and error status | Planned |

Holdings are initially derived from transactions and are not a primary entity.

## Planned API

### Authentication

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

### Portfolio core

```text
POST   /api/v1/portfolios
GET    /api/v1/portfolios
GET    /api/v1/portfolios/{portfolio_id}
PATCH  /api/v1/portfolios/{portfolio_id}
DELETE /api/v1/portfolios/{portfolio_id}

POST   /api/v1/portfolios/{portfolio_id}/transactions
GET    /api/v1/portfolios/{portfolio_id}/transactions
PATCH  /api/v1/transactions/{transaction_id}
DELETE /api/v1/transactions/{transaction_id}

GET /api/v1/portfolios/{portfolio_id}/summary
GET /api/v1/portfolios/{portfolio_id}/allocation
GET /api/v1/portfolios/{portfolio_id}/history
```

### Market data and benchmarks

```text
GET  /api/v1/assets
GET  /api/v1/assets/{asset_id}
POST /api/v1/watchlist
GET  /api/v1/watchlist
DELETE /api/v1/watchlist/{watchlist_item_id}
GET  /api/v1/portfolios/{portfolio_id}/benchmark-comparison
GET  /api/v1/data-sync/status
```

### Analytics and documents

```text
POST /api/v1/portfolios/{portfolio_id}/analytics
GET  /api/v1/portfolios/{portfolio_id}/analytics/latest
POST /api/v1/reports
POST /api/v1/reports/{report_id}/questions
POST /api/v1/notes
GET  /api/v1/notes
POST /api/v1/exports
```

Authentication endpoints are implemented in code; the remaining routes in this section are still planned.

## Functional scope

### MVP: must work before advanced AI

1. User registration, login and ownership isolation
2. Portfolio CRUD
3. Asset lookup
4. `BUY` and `SELL` transaction CRUD
5. Holding quantity derived from transactions
6. Current portfolio value
7. TRY, USD, EUR and GBP valuation
8. Average cost and basic unrealized profit/loss
9. Market-price storage and stale-cache fallback
10. Portfolio allocation and historical snapshot responses
11. Pytest coverage for core calculations and authorization

### Second implementation stage

1. Watchlist
2. Incremental data synchronization
3. Benchmark comparison
4. Notes
5. Export
6. Dashboard integration

### Advanced stage

1. Correlation analysis
2. Volatility and Sharpe Ratio
3. Maximum drawdown
4. Historical stress testing
5. Portfolio robustness score
6. Expert-source sentiment analysis
7. AI-supported explanations
8. Report upload, summarization and grounded Q&A

Core portfolio tracking must remain usable if advanced AI features are
unavailable.

## Financial calculation plan

### Holding quantity

```text
quantity = total BUY quantity - total SELL quantity
```

### Current value

```text
asset value = current quantity * latest valid market price
portfolio value = sum of asset values converted to the selected currency
```

### Benchmark comparison

Portfolio and benchmark time series will be aligned by date and normalized to
the same initial value.

### Risk analytics

The planned metrics are:

- Daily returns
- Volatility
- Sharpe Ratio
- Maximum drawdown
- Asset correlation
- Historical stress loss
- Explainable robustness score

## Data-update strategy

The meeting notes changed the practical data strategy:

- Do not refresh every TEFAS fund on every user startup.
- Refresh assets owned by the user, watchlist assets and selected benchmarks.
- On first tracking, retrieve up to three years of price history when
  available.
- After first import, request only missing dates.
- Prefer at least one to three months of detailed fund metrics where available.
- If long-term investor count or portfolio-size history is unavailable, store
  only valid returned data and build daily history from that point forward.
- Use cached data when a provider temporarily fails.
- Show the latest successful data date to the user.
- A cloud scheduled update may be added later, but it is not required for the
  initial local MVP.
- Unauthorized scraping and provider restriction bypasses are outside scope.

## Non-functional targets from the report

| Property | Target |
|---|---|
| Dashboard response | Average at most 3 seconds |
| Portfolio calculation | At most 5 seconds for 100 transactions |
| Transaction processing | At least 10 transactions per second |
| Market-data freshness | At least daily |
| Collected-data validity | At least 95% |
| Availability | At least 95% |
| Cached-data fallback success | At least 95% |
| Invalid-input handling | At least 99% |
| Add-transaction usability | At most 5 steps/clicks |
| Automated test coverage | At least 70% |
| Stored real bank credentials | 0 |

## Planned schedule from the report

| Work package | Dates | Main output |
|---|---|---|
| Data integration and preprocessing | 1–30 September 2026 | Cleaned market datasets and connectors |
| Portfolio core and multi-currency evaluation | 1–31 October 2026 | Transactions, valuation and history |
| Dashboard and benchmark comparison | 1–20 November 2026 | Charts and comparison results |
| AI analytics, sentiment and report Q&A | 21 November–15 December 2026 | Advanced analysis modules |
| Final testing and documentation | 16 December 2026–5 January 2027 | Tested presentation-ready system |

## Open decisions

The following decisions must be resolved before their affected features are
implemented:

1. **Cost basis:** weighted-average cost or FIFO?
2. **Frontend framework:** not fixed in the backend documents.
3. **Deployment target:** local demo only or hosted final demo?
4. **Exact legal data providers:** confirm TEFAS, exchange-rate, precious-metal
   and benchmark access before connector implementation.
5. **Report storage:** local project storage for the demo or external object
   storage?
6. **AI interface:** in-process Python module or separate HTTP service?
7. **Additional transaction types:** whether dividends, deposits, withdrawals,
   transfers and fees are required beyond the initial `BUY`/`SELL` scope.

Do not guess these choices inside implementation code.

## Immediate next implementation steps

### Step 1 — Local environment

- Install project dependencies from `requirements.txt`.
- Create `.env` from `.env.example`.
- Create the PostgreSQL `ai_portfolio` database.
- Run the health endpoint and `pytest`.

### Step 2 — Verify completed User flow

- Run the first Alembic migration.
- Verify `POST /api/v1/auth/register`, `POST /api/v1/auth/login` and `GET /api/v1/auth/me`.
- Add Pytest coverage for registration, login and protected endpoint access.

### Step 3 — Portfolio core

- Implement Portfolio, Asset and Transaction vertically.
- Enforce user ownership.
- Implement quantity and current-value services.
- Validate overselling and invalid monetary inputs.

### Step 4 — Data and integration contracts

- Agree on normalized data structures with the data developer.
- Implement provider adapters without coupling core services to one library.
- Add `AssetPrice`, `ExchangeRate` and `DataSyncRun`.
## Planned first acceptance test

The first end-to-end milestone is:

1. Register a user.
2. Log in.
3. Create a portfolio.
4. Add an asset.
5. Add a `BUY` transaction.
6. Return the calculated holding quantity and portfolio value as JSON.
7. Confirm that a second user cannot access the portfolio.

## Documentation update rule

After every completed feature, update only the relevant sections:

- Current implementation status
- Implemented entities
- Implemented API
- Tests and verification
- Open decisions
- Immediate next step

Do not remove historical project facts or silently mark untested work as
complete.










