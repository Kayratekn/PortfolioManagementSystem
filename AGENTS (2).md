# AGENTS.md

## Purpose

This file defines the permanent implementation rules for the AI-Assisted
Portfolio Management System. Codex and other coding agents must read this file
before changing the project.

`PROJECT_STATUS.md` contains current progress and next tasks. This file contains
rules that should remain stable throughout implementation.

## Product boundary

The product is a browser-based web application for individual investors. It
tracks manually entered portfolios and combines portfolio calculations,
financial data, benchmark comparison and AI-supported analysis.

The system is a decision-support and educational tool.

- It is not an automated trading platform.
- It must not connect to bank or brokerage accounts.
- It must not store bank credentials, brokerage passwords or private financial
  access tokens.
- It must not execute buy or sell orders.
- AI output must not be presented as guaranteed financial advice.

## Authoritative project sources

The project design is based on:

1. `SOFTWARE_FINAL_12june_LAST(1).docx`
2. `Graduation Projects Proposal Form_ H. Altıncay (2)(2).docx`
3. `seszeynep(2).docx`
4. The implemented backend scaffold and this file

When sources conflict:

1. Preserve the product boundary and ethical constraints.
2. Prefer the latest explicit team decision recorded in `PROJECT_STATUS.md`.
3. Keep the implementation, report, ER diagram and API documentation
   consistent.
4. Do not silently choose between conflicting requirements. Record the conflict
   under `Open decisions` in `PROJECT_STATUS.md`.

## Final backend stack

- Python
- FastAPI
- Uvicorn
- Pydantic and Pydantic Settings
- SQLAlchemy
- Alembic
- PostgreSQL
- Pytest
- REST API using JSON
- Git and GitHub

Use synchronous SQLAlchemy sessions during the first implementation phase. Do
not mix synchronous and asynchronous database patterns without an explicit
architecture decision.

The project report currently contains some MySQL references. PostgreSQL is the
selected implementation database; the report must eventually be updated to
match the code.

## Architecture rules

Preserve the following dependency direction:

```text
API endpoint
    -> Service
        -> Repository
            -> SQLAlchemy model
                -> PostgreSQL
```

External modules use adapters:

```text
Service
    -> Market-data adapter
    -> AI adapter
```

### API layer

`app/api` owns HTTP routing, request parsing, authentication dependencies and
response status codes.

- Keep endpoints small.
- Validate input through Pydantic schemas.
- Do not place portfolio calculations or SQL queries inside endpoints.
- Use the `/api/v1` prefix.

### Service layer

`app/services` owns business rules and financial calculations.

- Services must not construct FastAPI responses.
- Services must not depend on frontend code.
- Financial calculations should be deterministic and independently testable.

### Repository layer

`app/repositories` owns database queries.

- Repositories must not contain HTTP concerns.
- Avoid duplicating the same ownership filters or queries across endpoints.
- All user-owned data queries must include the authenticated user context.

### Model and schema layers

`app/models` contains SQLAlchemy persistence models.

`app/schemas` contains Pydantic request and response models.

- Never expose ORM objects directly as an undocumented API contract.
- Database models and API schemas may have different fields.
- Schema changes must use Alembic migrations.
- Do not use `Base.metadata.create_all()` as the production migration strategy.

### Integration layer

`app/integrations/market_data` owns TEFAS, exchange-rate, precious-metal and
benchmark connectors.

`app/integrations/ai` owns communication with AI analytics, sentiment and
report-based Q&A components.

- Core services must not depend directly on a third-party provider library.
- Each provider must be replaceable behind an adapter.
- A failure in sentiment or report Q&A must not break core portfolio tracking.

## Domain rules

### Transactions and holdings

Transactions are the source of truth for ownership.

```text
holding quantity = sum(BUY quantity) - sum(SELL quantity)
```

- Do not treat a mutable `holdings` table as the primary financial record.
- A holdings view or cache may be introduced later for performance.
- Historical portfolio valuation must derive holding quantities from
  transactions on or before the requested valuation date. Future transactions
  must never affect a historical valuation.
- Reject zero or negative quantities and prices.
- Reject a sell that exceeds the currently available quantity.
- Do not delete historical transactions or prices after an asset is sold.
  Historical data is required for portfolio history and auditability.
- The initial transaction types are `BUY` and `SELL`. Additional transaction
  types require a documented schema and calculation change.

### Cost Basis v1

Cost Basis v1 uses Moving Weighted Average Cost as an application/accounting
convention for this portfolio analytics project. Do not describe this
methodology as tax/legal accounting advice or claim that it is legally required.

- Transactions remain the sole source of truth.
- Cost basis is derived by replaying transaction history; do not add a mutable
  persisted holdings/cost-basis table for v1.
- Replay order must be deterministic: `transaction_date ASC`, then transaction
  `id ASC`.
- Use `Decimal` only. Never use `float`.
- Do not round or quantize internal cost-basis calculations.

BUY behavior:

```text
buy_cost = buy_quantity * buy_unit_price
new_total_cost = previous_total_cost + buy_cost
new_quantity = previous_quantity + buy_quantity
average_cost_per_unit = new_total_cost / new_quantity
```

SELL behavior:

```text
cost_removed = sell_quantity * current_average_cost_per_unit
remaining_total_cost = previous_total_cost - cost_removed
remaining_quantity = previous_quantity - sell_quantity
```

- A SELL does not change the average cost per unit of the remaining units,
  except that when remaining quantity becomes zero the cost basis state is reset
  to zero.
- Existing oversell validation remains authoritative.

Historical/as-of behavior:

- Cost basis for an as-of date must use only transactions whose
  `transaction_date <= requested date`.
- Future transactions must never change historical cost basis.
- Same-date ordering remains `transaction_date ASC`, `id ASC`.

Currency:

- Cost Basis v1 is calculated in the asset's native `Asset.currency`.
- Do not silently infer a missing `Asset.currency`.
- Conversion of cost basis or P/L into portfolio base currency is not part of
  this methodology slice and requires separate FX semantics later.

Fees/taxes:

- `Transaction` currently has no fee, commission or tax fields.
- Cost Basis v1 therefore uses `quantity * unit_price` only.
- Do not invent fee/commission/tax behavior.

Realized P/L:

- Do not implement realized P/L as part of documenting this methodology.
- Future realized P/L under this methodology will use the current moving average
  cost at the SELL point.
- Exact P/L and FX contract remains a later implementation/design slice.

### Financial precision

- Use `Decimal`/database `NUMERIC`, not binary floating-point values, for money,
  quantities, prices, exchange rates and calculated monetary results.
- Store currency codes using ISO-style uppercase values such as `TRY`, `USD`,
  `EUR` and `GBP`.
- State the direction of every exchange rate. Example: `USD/TRY` means TRY
  required for one USD.
- Round only at defined output boundaries; do not repeatedly round intermediate
  calculations.
- The selected cost-basis method must be followed before unrealized or realized
  profit/loss is implemented.

### Market data

- Store the source and effective date of market data.
- `AssetPrice` must prevent duplicate `(asset_id, price_date, source)` records.
- Historical series must be aligned by date before comparison.
- Portfolio and benchmark series must be normalized to the same starting value
  for chart comparison.
- A portfolio snapshot represents a dated calculated result, not a replacement
  for transaction history.
- For TEFAS valuation, `YAT`, `EMK`, `GYF` and `GSYF` use
  `TefasFundDailyData.price`; `BYF` uses `exchange_bulletin_price`.
  If a BYF exchange-market price is unavailable, do not silently fall back to NAV.
- For valuation FX, use the Decimal TCMB reference midpoint
  `(ForexBuying + ForexSelling) / 2`; do not persist the midpoint.
- Use latest-on-or-before semantics independently for valuation price and FX data.
  Price date and FX date do not need to match across independent providers.
- Direct and inverse FX conversions use the stored foreign/TRY observation.
  Foreign-to-foreign conversions go through TRY and require both TCMB legs to
  have the same effective `rate_date`; otherwise the conversion is unavailable.
- If `Asset.currency` is unknown, do not infer or hardcode a currency.
  FX-dependent valuation must remain unavailable until a reliable currency is known.
- If any positive holding cannot be valued because required valuation price,
  asset currency or FX data is unavailable, portfolio valuation must be marked
  `INCOMPLETE` and total market value must remain unavailable. Never present a
  partial sum of only valued holdings as a complete portfolio total.
- Portfolio item weight is a `Decimal` ratio in `0..1` form, not percentage
  points.
- For a complete non-empty portfolio:
  ```text
  weight = item.market_value / portfolio.total_market_value
  ```
- Weight must use portfolio-currency `market_value`, never
  `native_market_value`.
- Do not use float, round or quantize internally when calculating weights.
- For an `INCOMPLETE` portfolio, every item weight must be unavailable (`None`),
  including otherwise complete items whose `market_value` is known. Never
  calculate weights from only the successfully valued subset of an incomplete
  portfolio.
- Empty `COMPLETE` portfolios remain `total_market_value = Decimal("0")` with
  no items, so no weight division is performed.

### Data collection

- Do not download and refresh all TEFAS funds on every application start.
- Actively refresh assets held in a portfolio, assets in a watchlist and
  configured benchmarks.
- When an asset is first tracked, request up to three years of price history
  when legally and technically available.
- After the initial import, fetch only missing dates.
- If investor count, portfolio size or similar historical TEFAS fields are not
  available, do not fabricate them. Store available data and begin daily
  snapshots from the first successful collection.
- Respect provider terms and rate limits.
- Do not implement unauthorized scraping or rate-limit bypasses.
- Preserve the most recent valid cached data when a source temporarily fails.
- Every cached response must expose its `as_of` date and stale-data status.
- Record sync status and errors without crashing the portfolio API.

## Security and privacy rules

- Store only password hashes; never store plain-text passwords.
- Keep secrets and database credentials in environment variables.
- Never commit `.env`.
- Authenticate protected endpoints.
- Authorize every user-owned resource by both resource ID and authenticated
  user ID.
- A user must never access another user's portfolio, transactions, reports,
  notes, watchlist or AI results.
- Validate uploaded file type and size before report processing.
- Avoid returning internal stack traces, database credentials or provider
  secrets in API responses.
- Logs must not contain passwords, tokens or sensitive document content.

## AI and analytics rules

- The backend controls access to portfolio data before invoking AI modules.
- The AI module must receive only the data required for the requested analysis.
- Save structured metrics separately from explanatory text.
- Store the analysis timestamp and model/formula version.
- Robustness scores must have a documented, reproducible calculation.
- Sentiment is an opinion indicator, not factual verification.
- Report-based answers must be grounded in the user's uploaded report.
- All recommendation-like text must include decision-support wording and must
  not promise profit or instruct automatic trading.

## API conventions

- Base path: `/api/v1`
- Use plural resource names: `/portfolios`, `/transactions`, `/reports`.
- Use Pydantic request and response schemas.
- Use appropriate HTTP status codes.
- Use a consistent error body containing a machine-readable code and a
  user-readable message.
- Paginate potentially large collections.
- Include data freshness metadata in endpoints that depend on market data.
- Do not make breaking API changes without updating frontend contracts and
  `PROJECT_STATUS.md`.

## Required entity set

The planned core entities are:

1. User
2. Portfolio
3. Asset
4. Transaction
5. AssetPrice
6. ExchangeRate
7. TefasFundDailyData
8. PortfolioSnapshot
9. Benchmark
10. BenchmarkPrice
11. WatchlistItem
12. AIAnalysis
13. ExpertSource
14. UserExpertSource
15. SentimentPost
16. ReportDocument
17. ReportChunk
18. Note
19. DataSyncRun

Do not implement all entities in one change. Add them by vertical feature,
including model, schema, repository, service, endpoint, migration and tests.

## Testing rules

- Use Pytest.
- Target at least 70% test coverage as required by the project report.
- Unit-test portfolio valuation, currency conversion, quantity calculation,
  cost basis, benchmark normalization and risk metrics.
- API-test validation, authentication and ownership isolation.
- Integration-test repository behavior and module boundaries.
- Test cached-data fallback and external-provider failures.
- Compare financial calculations with manually verified examples.
- Every bug fix must include a regression test when practical.

A feature is not complete merely because its endpoint returns a response.

## Coding rules

- Follow PEP 8.
- Use type hints for public functions and service interfaces.
- Prefer small, explicit modules over large multi-purpose files.
- Use descriptive financial names; avoid unexplained abbreviations.
- Keep provider-specific field names inside integration adapters.
- Avoid premature microservices, queues and distributed infrastructure.
- Add complexity only when the current modular monolith cannot meet a
  documented requirement.
- Preserve unrelated code and user changes.

## Team boundaries

- Zeynep: data integration and preprocessing.
- Kayra: backend, portfolio calculations and testing.
- Bahattin: AI analytics, correlation, risk, sentiment and report Q&A.
- Arınç: frontend and visualization.

The backend defines stable contracts for the other modules. Do not move another
member's complete implementation into the backend without an explicit team
decision.

## Agent workflow

Before implementing a task:

1. Read this file.
2. Read `PROJECT_STATUS.md`.
3. Inspect the relevant existing model, schema, repository, service, endpoint,
   migration and tests.
4. Identify any unresolved decision that blocks correct implementation.

After implementing a task:

1. Run relevant tests and static/syntax checks.
2. Confirm that no secrets or generated cache files were added.
3. Update `PROJECT_STATUS.md` with completed work, migrations, endpoints,
   tests and the exact next step.
4. Do not rewrite unrelated sections of either Markdown file.

## Definition of done

A backend feature is complete only when:

- Its behavior is within the approved product scope.
- Model and migration are consistent.
- Validation and authorization are implemented.
- Business logic is in a service.
- Database access is isolated in a repository where appropriate.
- API schemas and status codes are documented.
- Success, validation and authorization tests pass.
- Frontend/AI/data contracts are documented when affected.
- `PROJECT_STATUS.md` is updated.
