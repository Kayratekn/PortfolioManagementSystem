# PROJECT_STATUS.md

## Project identity

- **Project:** AI-Assisted Portfolio Management System
- **Type:** Browser-based web application
- **Team size:** 4
- **Supervisor:** Prof. Dr. Hakan Altınçay
- **Current backend stage:** Authentication, Portfolio CRUD, Transaction and Holdings foundations are stable. TEFAS valuation-price and TCMB FX foundations are implemented and validated. Portfolio Valuation Aggregation v1 is implemented and validated, exposed through a stable authenticated API contract: `GET /api/v1/portfolios/{portfolio_id}/valuation?valuation_date=YYYY-MM-DD`, and Portfolio Weights v1 is now implemented and validated through that existing endpoint. `valuation_date` is required. Each valuation item exposes `weight: Decimal | None`; weights are `0..1` ratios based on portfolio-currency `market_value`, complete portfolios calculate exact Decimal weights, and incomplete portfolios expose null weight for every item without partial-subset weights. The API preserves `COMPLETE`/`INCOMPLETE` status, unavailable reason, price provenance and FX provenance. Decimal monetary values and weights remain Decimal internally and serialize safely through the Pydantic/FastAPI response contract. No new endpoint or migration was introduced for weights. Cost Basis v1 is now implemented and validated through the public authenticated API `GET /api/v1/portfolios/{portfolio_id}/cost-basis?as_of_date=YYYY-MM-DD`, using the documented Moving Weighted Average Cost methodology. Unrealized P/L v1 is now implemented and validated through the public authenticated API `GET /api/v1/portfolios/{portfolio_id}/unrealized-pl?as_of_date=YYYY-MM-DD`, using the previously documented native-currency-only methodology and completed service implementation. `as_of_date` is required, the endpoint is authenticated and ownership-protected, and the response remains native-currency only. Unrealized P/L v1 has no portfolio-base-currency P/L, FX-adjusted cost basis, portfolio-level Unrealized P/L total, Unrealized P/L percentage, Realized P/L, migration, table or schema change. Cost Basis remains transaction-based, derives native-currency cost basis through deterministic Decimal replay, requires `as_of_date`, preserves ownership isolation, serializes Decimal values as JSON strings, and does not add a mutable cost-basis/holdings table, migration, portfolio-level summed cost-basis total, realized P/L implementation or FX conversion of cost basis/P&L. Public Realized P/L v1 API is now implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/realized-pl?as_of_date=YYYY-MM-DD`. `as_of_date` is required, authentication is required, and portfolio ownership isolation returns 404 with `Portfolio not found.`. The response exposes `portfolio_id`, `as_of_date`, `status` and `items`; each item exposes `asset_id`, `asset_code`, `asset_name`, `asset_currency`, `status`, `unavailable_reason`, `sold_quantity`, `realized_proceeds`, `realized_cost_basis` and `native_realized_pl`. Decimal financial values remain Decimal internally and serialize as JSON strings. Realized P/L remains transaction-sourced, cumulative through one `as_of_date`, native-currency only, and uses SELL activity on or before `as_of_date` as its asset universe so fully sold assets remain included. Missing or blank `Asset.currency` produces an `UNAVAILABLE` item that preserves `sold_quantity` while exposing null monetary outputs. Cost Basis and Realized P/L continue to share one canonical Moving Weighted Average Cost replay helper. Transaction History public API is now implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/transactions` with authentication, ownership isolation, `skip`/`limit` pagination, deterministic `transaction_date ASC, id ASC` ordering and `TransactionListResponse`. Asset Catalog public API is now implemented and validated at `GET /api/v1/assets` with authentication, active-asset-only scope, `skip`/`limit` pagination, optional case-insensitive search across `asset_code` and `asset_name`, deterministic `asset_code ASC, id ASC` ordering and nullable `isin`/`currency` preservation. No market price or freshness metadata is exposed by the Asset Catalog API. Portfolio Historical Performance / TWR foundation is now implemented and validated through the public authenticated API `GET /api/v1/portfolios/{portfolio_id}/performance?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`. `start_date` and `end_date` are required inclusive dates; `end_date` must be greater than or equal to `start_date`; ranges over 366 inclusive calendar days return HTTP 422. Performance uses calendar-day points, daily-close historical valuation including assets plus derived cash, start-of-day DEPOSIT/WITHDRAWAL external flows, and BUY/SELL remain internal trades that never count as external flows. Decimal arithmetic is used throughout, never float. Provider-independent Benchmark + BenchmarkPrice storage foundation is now implemented and validated via migration `20260903_0016`, following `20260902_0015`. Benchmark metadata + generic historical price import foundation is now implemented and validated via migration `20260903_0017`, following `20260903_0016`; `Benchmark.index_owner` is required, nonblank and uppercase, `Benchmark.return_type` is required and constrained to `PRICE_RETURN` or `TOTAL_RETURN`, `provider` remains the configured data-provider identity and `BenchmarkPrice.source` remains row-level provenance. The generic benchmark price parser accepts canonical `date,close` rows, parses close directly from string to Decimal, rejects floats, non-finite/blank/malformed/zero/negative values and values requiring rounding beyond `NUMERIC(20,8)`, allows exact trailing-zero representations, deduplicates identical duplicate dates deterministically, rejects conflicting duplicate dates, and never fabricates dates or forward-fills. The generic import service is benchmark-agnostic, requires an existing active Benchmark, accepts historical dates only, rejects current/future dates until provider finality is defined, inserts missing rows, is idempotent for same date/close/source, rejects close/source conflicts by default with `allow_revisions=False`, permits controlled revisions only with `allow_revisions=True`, preserves benchmark/date uniqueness and isolation, commits once and rolls back atomically on failure/conflict. Benchmark storage/import is ready. Generic Benchmark Comparison API is now implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/benchmark-comparison?benchmark_code=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`; it reuses the existing PortfolioPerformanceService/TWR unchanged, reads persisted BenchmarkPrice observations only, uses a hidden latest-real-observation baseline on or before `start_date - 1 day`, does not fabricate or forward-fill non-trading days, supports historical FX conversion into the portfolio base currency, and returns separate portfolio and benchmark normalized series plus cumulative benchmark return and excess return. BIST100 operational bootstrap/import tooling is now implemented and validated: supported metadata locks `BIST100` / `BIST 100` / `MARKET_INDEX` / `TRY` / `BORSA_ISTANBUL` / `PRICE_RETURN` with provider identity `YAHOO_FINANCE` and provider symbol `XU100.IS`; bootstrap is idempotent and conflict-safe, and a generic CSV CLI imports canonical `date,close` historical datasets through the existing validated BenchmarkPrice parser/import service. BIST100 is now operational with real persisted historical data in the current PostgreSQL environment: the supported `BIST100` Benchmark row is persisted with provider `YAHOO_FINANCE` / symbol `XU100.IS`, and 1,251 validated daily `BenchmarkPrice` observations covering 2021-09-06 through 2026-09-04 are persisted with source `DATA_TEAM_YAHOO_FINANCE_CLOSE`. The real persisted benchmark series were verified through the public Benchmark Comparison API end-to-end, including historical USD-to-TRY FX behavior for the USD benchmarks. Benchmark Catalog API is now implemented and validated at `GET /api/v1/benchmarks`; authentication is required and the endpoint exposes the active persisted benchmark catalog with deterministic ordering and public metadata only. Benchmark Daily Scheduled Sync + completed-close finality is now implemented and validated for BIST100, SP500 and NASDAQ100 through an isolated Yahoo Finance/yfinance integration. The sync fetches only completed historical daily Close observations, preserves the existing historical-only import guard, rejects future reference dates and out-of-range provider rows, performs Decimal 8dp canonicalization, never fabricates non-trading dates or automatically revises existing history, and persists new daily rows with source `YAHOO_FINANCE_DAILY_CLOSE`. TEFAS benchmark implementation, individual-stock comparison, TWR behavior changes and comparison-result persistence remain outside this slice. No portfolio-level Realized P/L total, FX/base-currency conversion, market-price dependency, percentage/return, from/to period behavior, fees/taxes or schema change outside the provider-independent benchmark storage foundation was added.
- **Status updated:** 2026-09-07

## Product summary

The system allows an individual investor to track supported investment assets in manually entered portfolios and combines portfolio calculations, market/fund data, benchmark comparison and later AI-supported analysis.

The current backend already contains the authentication and portfolio foundation plus a substantial TEFAS data-integration layer. TEFAS daily fund data, fund-detail metadata, portfolio allocation data and multiple derived short-term metrics have been investigated, implemented and tested conservatively.

The project remains a decision-support and educational application. It does not execute trades or connect to bank/brokerage accounts.

## Current repository structure

```text
src/
├── config/
├── controller/
├── exception/
├── integrations/
├── mapper/
├── model/
├── repositories/
├── request/
├── response/
└── services/
alembic/
docs/
tests/
```

## Current implementation status

| Area | Status | Notes |
|---|---|---|
| Backend folder structure | Complete | Modular backend layout exists under `src/` |
| FastAPI application | Complete | Application is created in `src/main.py` |
| API versioning | Partial | Current routes use `/api/v1`; no separate version-module layer yet |
| Health endpoint | Complete | `GET /api/v1/health` is registered |
| Environment configuration | Complete | `.env.example` and Pydantic settings are present |
| SQLAlchemy base/session | Complete | Engine, session factory and FastAPI DB dependency are implemented |
| Alembic migrations | Active / working | PostgreSQL migration flow is established and used for implemented domains |
| User/authentication domain | Complete | Register, login, current-user flow, password hashing and JWT validation are implemented |
| Portfolio domain | Complete | CRUD, ownership isolation, pagination and soft delete are implemented and tested |
| Asset/data foundation | Implemented / validated (public catalog API) | Asset-linked TEFAS snapshots and related repositories/services/tests exist; nullable Asset-level ISIN metadata persistence/enrichment is implemented. Public Asset Catalog API is implemented at `GET /api/v1/assets`; it returns active assets only, supports pagination and optional case-insensitive code/name search, preserves nullable `isin` and `currency`, and does not expose market price or freshness metadata. |
| Watchlist domain | Implemented / validated (public API contract) | Migration `20260907_0018`, following `20260903_0017`, creates user-owned `watchlist_items` with `user_id`, `asset_id`, timestamps, database uniqueness on `(user_id, asset_id)` and a user-scoped index. Authenticated APIs are implemented at `POST /api/v1/watchlist`, `GET /api/v1/watchlist` and `DELETE /api/v1/watchlist/{watchlist_item_id}`. Creation accepts only existing active assets; missing/inactive assets return 404 `Asset not found.`. A user cannot add the same asset twice; duplicates return 409 `Asset is already in watchlist.` and the DB unique constraint protects concurrent duplicate writes. Different users may track the same asset. Listing is isolated to the current user, paginated with deterministic `asset_code ASC, watchlist_item.id ASC` ordering, and existing entries remain visible if an Asset later becomes inactive. Delete is owner-only, hard-delete, and missing or other-user items return 404 `Watchlist item not found.`. Public responses expose asset metadata and `created_at` without exposing `user_id` or `updated_at`. No market-price refresh, search, PATCH, soft-delete or unrelated Asset behavior was added. |
| Transaction domain | Implemented / validated (public create + history API) | PostgreSQL `transactions` table foundation was introduced via migration `20260825_0012`; migration `20260902_0014` adds nullable `transaction_currency` (`TRY`/`USD`/`EUR`/`GBP`) for legacy-safe currency snapshots. New API-created BUY/SELL transactions require `transaction_currency`, normalize it at the request boundary, persist it, and expose it through create/history responses; legacy rows with null currency remain readable. Transactions for the same portfolio + asset must use the same non-null transaction currency. BUY and SELL creation both acquire the owned portfolio row with PostgreSQL `FOR UPDATE` before currency-consistency validation, historical SELL quantity validation and insert/commit, preventing concurrent first-write mixed-currency history through the normal service path. Existing Decimal / NUMERIC precision, portfolio ownership isolation, asset existence validation, deterministic `transaction_date ASC, id ASC` history ordering and `TransactionListResponse` behavior remain intact. No `Asset.currency` inference/backfill was introduced. Frontend integration is not complete. |
| PortfolioCashFlow foundation | Implemented / validated (public create + history API) | Migration `20260902_0015`, following `20260902_0014`, creates PostgreSQL table `portfolio_cash_flows` with `id`, `portfolio_id`, `flow_type`, `amount`, `currency`, `flow_date`, `created_at` and `updated_at`. `flow_type` supports only `DEPOSIT` and `WITHDRAWAL`; `amount` is Decimal / `NUMERIC(20,8)` and must be greater than zero; `currency` supports only `TRY`, `USD`, `EUR` and `GBP`. Public authenticated APIs are implemented at `POST /api/v1/portfolios/{portfolio_id}/cash-flows` and `GET /api/v1/portfolios/{portfolio_id}/cash-flows`; ownership isolation uses the canonical `404` detail `Portfolio not found.`. Responses serialize `amount` as a JSON string. Cash-flow history is deterministic by `flow_date ASC`, then `id ASC`, and exposes paginated `items`, `total`, `skip` and `limit`. No cash replay, mutable `CashBalance` table, insufficient-cash validation, TWR, historical valuation changes, benchmark implementation, transaction behavior changes, or `Asset`/TEFAS currency inference were added. |
| Derived per-currency cash replay foundation | Implemented / validated (internal service-only) | Cash replay is implemented as an internal service-only foundation with no public API and no migration. Historical cash is derived with Decimal-only arithmetic from `DEPOSIT +amount`, `WITHDRAWAL -amount`, `BUY -quantity*unit_price` and `SELL +quantity*unit_price`. Cash is tracked independently per currency and includes only PortfolioCashFlow and Transaction events dated `<= as_of_date`, so future transactions/cash flows do not affect historical cash. BUY/SELL use `Transaction.transaction_currency`; DEPOSIT/WITHDRAWAL use `PortfolioCashFlow.currency`; `Asset.currency` and TEFAS currency are never inferred, and no FX conversion is performed. Legacy transactions with `transaction_currency = NULL` are not guessed or applied to a currency; the result becomes `INCOMPLETE` with `unavailable_reason = TRANSACTION_CURRENCY_UNAVAILABLE` while known events are still replayed. Negative balances are preserved, no insufficient-cash validation or clamping exists yet, zero balances are omitted, non-zero balances are returned in deterministic currency ASC order, and an empty portfolio returns `COMPLETE` with an empty balance list. Same-day replay represents daily-close cash after all events dated `as_of_date`. No mutable `CashBalance` table, valuation changes, TWR/performance, benchmark implementation, transaction creation changes, or public cash-replay endpoint were added. |
| Holdings domain | Implemented / validated (foundation) | Holdings are derived from Transaction history without duplicated persisted holdings truth. `GET /api/v1/portfolios/{portfolio_id}/holdings` returns asset metadata and Decimal quantity for positive current holdings only; fully sold assets are omitted and ownership isolation is enforced. Service-level valuation aggregation is implemented; portfolio weights are implemented; Cost Basis v1 service and Unrealized P/L v1 service use positive historical/as-of holdings from transactions. Realized P/L v1 public API is implemented and validated. |
| Cost Basis v1 | Implemented / validated (public API contract) | `GET /api/v1/portfolios/{portfolio_id}/cost-basis?as_of_date=YYYY-MM-DD` is implemented as a public authenticated API. `as_of_date` is required; missing or invalid dates return 422, authentication is required and unauthenticated requests return 401, and portfolio ownership isolation returns 404 with `Portfolio not found.`. The response exposes `portfolio_id`, `as_of_date`, `status` and `items`; each item exposes `asset_id`, `asset_code`, `asset_name`, `asset_currency`, `status`, `unavailable_reason`, `quantity`, `total_cost_basis` and `average_cost_per_unit`. Decimal values remain Decimal internally and serialize as JSON strings. No portfolio-level `total_cost_basis` is exposed because native asset currencies can differ. Moving Weighted Average Cost service algorithm was not changed: transactions remain the source of truth, cost basis is replayed by `transaction_date ASC`, then `id ASC`, historical/as-of calculation uses `transaction_date <= as_of_date`, future transactions do not affect historical Cost Basis, fully sold assets remain omitted, missing `Asset.currency` remains `UNAVAILABLE` and makes the result `INCOMPLETE`, and manual/non-TEFAS assets with known currency are supported. No mutable cost-basis/holdings table, migration, realized P/L or FX conversion of cost basis/P&L was added in the Cost Basis slice. |
| Unrealized P/L v1 | Implemented / validated (public API contract) | Unrealized P/L v1 methodology was documented previously, the service implementation is complete, and the public API is implemented at `GET /api/v1/portfolios/{portfolio_id}/unrealized-pl?as_of_date=YYYY-MM-DD`. `as_of_date` is required, and the endpoint is authenticated and ownership-protected. The response is native-currency only and uses the existing `UnrealizedPlService`, composed from `CostBasisService`, `TransactionRepository` and `TefasValuationPriceService`; it does not use `PortfolioValuationService` or `FxConversionService`. Public response items include asset identity/currency, `status`, `unavailable_reason`, `quantity`, `total_cost_basis`, `average_cost_per_unit`, selected price/provenance, `price_freshness`, `native_market_value` and `native_unrealized_pl`. Availability and financial semantics remain those documented in `AGENTS (2).md`: no portfolio-base-currency Unrealized P/L, FX-adjusted cost basis, portfolio-level Unrealized P/L total, Unrealized P/L percentage, Realized P/L, migrations or schema changes. |
| Realized P/L v1 | Implemented / validated (public API contract) | Public Realized P/L v1 API is implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/realized-pl?as_of_date=YYYY-MM-DD`. `as_of_date` is required, authentication is required, and portfolio ownership isolation returns 404 with `Portfolio not found.`. The response exposes `portfolio_id`, `as_of_date`, `status` and `items`; each item exposes `asset_id`, `asset_code`, `asset_name`, `asset_currency`, `status`, `unavailable_reason`, `sold_quantity`, `realized_proceeds`, `realized_cost_basis` and `native_realized_pl`. Decimal financial values remain Decimal internally and serialize as JSON strings. Fully sold assets remain included because the Realized P/L universe is SELL activity on or before `as_of_date`. Missing or blank `Asset.currency` remains `UNAVAILABLE`, preserves `sold_quantity`, and exposes null monetary outputs. Realized P/L remains cumulative through `as_of_date` and native-currency only. No portfolio-level Realized P/L total, FX/base-currency conversion, market-price dependency, percentage/return, from/to period behavior, fees/taxes, migration or schema change was added. `RealizedPlService` and the shared MWAC replay were unchanged during this API slice. |
| Exchange-rate / TCMB foundation | Implemented / validated | PostgreSQL `exchange_rates` via migration `20260826_0013`; TCMB current/historical XML client preserves effective rate date and Decimal `ForexBuying`/`ForexSelling`; idempotent TCMB sync persists USD/TRY, EUR/TRY and GBP/TRY observations. |
| Valuation market-data foundation | Implemented / validated (v1) | YAT/EMK/GYF/GSYF valuation uses TEFAS NAV `price`; BYF uses `exchange_bulletin_price` as exchange-market price with no silent NAV fallback. Price and FX lookups use latest-on-or-before semantics. FX conversion uses Decimal TCMB midpoint reference rates for identity/direct/inverse/cross conversions; foreign-to-foreign cross legs require the same effective date. |
| Market Data Freshness | Implemented / validated (focused API contract) | Shared freshness contract is implemented for market-data observations with `requested_date`, `effective_date`, `age_days` and `status`. Status values are `CURRENT`, `STALE`, `UNAVAILABLE` and `NOT_APPLICABLE`. `CURRENT` means `effective_date == requested_date`; `STALE` means an older latest-on-or-before market observation was used; `UNAVAILABLE` means required market data is missing; `NOT_APPLICABLE` is used for identity FX. No arbitrary stale-day threshold exists. Portfolio Valuation exposes `price_freshness` and `fx_freshness`; Unrealized P/L exposes `price_freshness`. Existing price/FX selection, Decimal financial calculations, `COMPLETE`/`INCOMPLETE` behavior, ownership and `unavailable_reason` semantics were not changed. TEFAS metrics/allocation APIs were not changed, and no migration/model/table/provider changes were introduced. No PostgreSQL-specific smoke was required because DB/query behavior did not change. |
| Portfolio valuation aggregation | Implemented / validated (v1 API + weights + derived cash) | `GET /api/v1/portfolios/{portfolio_id}/valuation` was extended additively to include derived cash while preserving the existing public endpoint and required `valuation_date`. Existing `total_market_value` remains asset-only, existing asset valuation formulas remain unchanged, and existing asset item `weight` semantics remain unchanged using the asset-only denominator. New response fields are `cash_items`, `total_cash_value` and `total_portfolio_value`. Cash comes from `PortfolioCashReplayService` using the same portfolio/user/valuation date. Same-currency cash is used directly without FX lookup; foreign cash uses the existing historical FX foundation with latest-on-or-before `valuation_date`. Decimal arithmetic is used throughout, never float. Negative cash balances are preserved and reduce total portfolio value. `Asset.currency` and TEFAS currency are never used or inferred for cash. If asset valuation, cash replay or required cash FX is incomplete/unavailable, overall valuation is `INCOMPLETE` and `total_portfolio_value` is `None`; if cash replay is incomplete, known cash items may still be exposed but `total_cash_value` is `None`; if one cash FX is unavailable, that cash item is `UNAVAILABLE` with `FX_UNAVAILABLE` and both `total_cash_value` and `total_portfolio_value` are `None`. If both asset and cash sides are complete, `total_cash_value = sum(converted cash)` and `total_portfolio_value = total_market_value + total_cash_value`. Cash-only portfolios are supported and empty portfolios remain complete zero. No TWR/performance, benchmark, cash solvency, mutable `CashBalance`, migration, new endpoint, transaction creation change or cash/full-portfolio weight semantics were added. |
| Portfolio Historical Performance / TWR foundation | Implemented / validated (public API contract) | Public authenticated endpoint `GET /api/v1/portfolios/{portfolio_id}/performance?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` is implemented. `start_date` and `end_date` are required and inclusive; `end_date >= start_date`; maximum inclusive range is 366 calendar days, and invalid ranges return 422. Performance returns calendar-day points. DEPOSIT/WITHDRAWAL are modeled as start-of-day external flows, with DEPOSIT positive and WITHDRAWAL negative; BUY/SELL remain internal trades and never enter external flow `F`. Historical valuation is daily close and already includes assets plus derived cash. Formula: `V_start = previous calendar-day close`, `F = current-day net external flow in portfolio base currency`, `V_end = current-day close`; when `V_start + F > 0`, `daily_return = (V_end - V_start - F) / (V_start + F)`. Same-currency flows require no FX; foreign external flows use historical FX latest-on-or-before flow date. Missing required flow FX makes the point `INCOMPLETE`, exposes `external_flow = None`, and never uses a partial external-flow value. Capital-base semantics are: positive denominator calculates return; zero denominator with zero ending value is `NOT_APPLICABLE`; zero denominator with non-zero ending value is `INCOMPLETE` with `ZERO_DENOMINATOR_WITH_VALUE`; negative denominator is `INCOMPLETE` with `NON_POSITIVE_CAPITAL_BASE`. Valid zero-capital gaps do not break cumulative continuity; a genuine `INCOMPLETE` point permanently breaks requested-period cumulative continuity, though later local daily returns may still be calculated with `cumulative_return = None`. Top-level status is `INCOMPLETE` if any point is incomplete, otherwise `COMPLETE` if at least one point is complete, otherwise `NOT_APPLICABLE`. Response exposes `portfolio_id`, `base_currency`, `start_date`, `end_date`, `status`, `cumulative_return` and `points`; each point exposes `date`, `portfolio_value`, `external_flow`, `daily_return`, `cumulative_return`, `status` and `unavailable_reason`. Decimal response values serialize as strings. No benchmark comparison, performance persistence, PortfolioSnapshot persistence, migration, cash solvency, transaction behavior changes or Asset/TEFAS currency inference was added. |
| PortfolioSnapshot storage foundation | Implemented / validated (internal storage only) | Migration `20260907_0022`, following `20260907_0021`, creates `portfolio_snapshots` as persisted dated calculated portfolio results with required `portfolio_id`, `snapshot_date` and Decimal `total_value_try`, `total_value_usd`, `total_value_eur`, `total_value_gbp` (`Numeric(20,8)`). `(portfolio_id, snapshot_date)` is unique; historical repository lookups are deterministic and latest-on-or-before never uses future rows. Zero and negative totals are intentionally permitted. Snapshots do not replace Transaction/PortfolioCashFlow as source of truth and are not yet used by valuation, TWR/performance or benchmark comparison. No generation service, scheduler or public API exists yet. |

| Provider-independent Benchmark + BenchmarkPrice storage and generic import foundation | Implemented / validated (internal storage/import only) | Migration `20260903_0016`, following `20260902_0015`, creates provider-independent `benchmarks` and `benchmark_prices` tables. Migration `20260903_0017`, following `20260903_0016`, adds required `Benchmark.index_owner` and required `Benchmark.return_type`; `index_owner` is nonblank and uppercase, and `return_type` is constrained to `PRICE_RETURN` or `TOTAL_RETURN`. Migration `0017` checks that `benchmarks` is empty before schema mutation and aborts instead of guessing/backfilling metadata for existing rows. Existing `provider` remains the configured data-provider identity and `BenchmarkPrice.source` remains row-level provenance. The generic parser accepts canonical `date,close` rows, parses close directly from string to Decimal, rejects float financial input, rejects non-finite, blank, malformed, zero and negative values, rejects values requiring rounding beyond `NUMERIC(20,8)`, accepts exact trailing-zero representations, deduplicates identical duplicate dates deterministically, rejects conflicting duplicate dates, and does not fabricate dates or forward-fill. The generic BenchmarkPrice import service is benchmark-agnostic, requires an existing active Benchmark, accepts historical dates only, rejects current/future dates until provider finality exists, inserts missing rows, is idempotent for same date/close/source, rejects close/source conflicts by default with `allow_revisions=False`, permits explicit controlled revisions with `allow_revisions=True`, preserves benchmark/date uniqueness and isolation, commits once and rolls back atomically on failure/conflict. No BIST100 catalog row/seed, XU100/XU100.IS mapping, Yahoo/yfinance dependency, live provider client, scheduler, public benchmark API, comparison API, FX or TWR changes, TEFAS benchmark implementation or benchmark-series fabrication was added. |
| Generic Benchmark Comparison API | Implemented / validated (public API contract) | Authenticated endpoint `GET /api/v1/portfolios/{portfolio_id}/benchmark-comparison?benchmark_code=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` reuses existing Portfolio Historical Performance/TWR unchanged and compares it with persisted BenchmarkPrice observations. Benchmark baseline is the latest real observation on or before `start_date - 1 day`; start-date observations are never used as the hidden baseline. Benchmark series contains actual observations only, with no fabricated weekend/holiday rows or forward-fill. Foreign benchmark levels are converted into the portfolio base currency using historical latest-on-or-before FX on each actual observation date, intentionally including currency impact. Response exposes separate portfolio/benchmark series, Decimal cumulative returns, baseline metadata, normalization with hidden baseline 100, status/reason semantics and Decimal excess return as the return difference. Unknown/inactive benchmarks return canonical 404 and ownership isolation preserves `Portfolio not found.`. No provider calls, benchmark seed/import, catalog API, TWR change or result persistence were added. |
| Benchmark Catalog API | Implemented / validated (public authenticated API contract) | Authenticated endpoint `GET /api/v1/benchmarks` returns only active persisted benchmarks using the existing `BenchmarkRepository.list_active()` contract with deterministic `code ASC, id ASC` ordering. The v1 response contains `items` and `total`; each public item exposes only `id`, `code`, `name`, `benchmark_type`, `native_currency`, `index_owner` and `return_type`. Provider identity, provider symbol, activation state and timestamps are intentionally not exposed. No pagination or search is added in v1. Real PostgreSQL + FastAPI HTTP smoke returned the three current active benchmarks in `BIST100 -> NASDAQ100 -> SP500` order, enforced authentication, and rollback preserved production benchmark data. No migration or benchmark comparison/import/sync behavior changed. |
| Benchmark Daily Scheduled Sync + completed-close finality | Implemented / validated (internal operational sync) | Runtime `yfinance` is isolated to `YahooFinanceBenchmarkClient`. Supported `BIST100` / `XU100.IS`, `SP500` / `^GSPC` and `NASDAQ100` / `^NDX` daily Close observations are fetched with `interval=1d`, `auto_adjust=False`, inclusive start and exclusive end semantics. Sync starts at the latest persisted BenchmarkPrice date + 1 day and uses `reference_date` as the exclusive end. Provider observations must remain inside that range; no weekend/holiday observations are fabricated or forward-filled. The default operational date is Europe/Istanbul-aware and future manual reference dates are rejected. Provider Close values are converted through `Decimal(str(value))`, canonicalized with `ROUND_HALF_UP` to 8 decimal places and passed through the existing BenchmarkPrice import service with `allow_revisions=False` and `today=reference_date`. Historical bootstrap is required before daily sync; empty provider results are valid no-ops; newly synced rows use source `YAHOO_FINANCE_DAILY_CLOSE`. The Python scheduler script is one-shot; external OS scheduling is not yet configured. No migration or benchmark comparison/catalog/TWR behavior change was introduced. |
| BIST100 benchmark operational data + import tooling | Implemented / validated (real PostgreSQL historical dataset loaded) | BIST100 is configured with exact metadata `code=BIST100`, `name=BIST 100`, `benchmark_type=MARKET_INDEX`, `native_currency=TRY`, `index_owner=BORSA_ISTANBUL`, `return_type=PRICE_RETURN`, `provider=YAHOO_FINANCE`, `provider_symbol=XU100.IS`, `is_active=true`. The reusable bootstrap service and generic CSV import CLI remain the authoritative operational path. A data-team Yahoo Finance/yfinance `XU100.IS` 5-year daily `Close` dataset was canonicalized to the backend `NUMERIC(20,8)` contract without changing dates, validated by the existing backend CSV reader/parser, then imported into real PostgreSQL. The database now contains 1,251 BIST100 `BenchmarkPrice` observations from 2021-09-06 through 2026-09-04 with source `DATA_TEAM_YAHOO_FINANCE_CLOSE`. Real-data end-to-end comparison through the authenticated Benchmark Comparison API passed using persisted BIST100 observations. No migration, runtime Yahoo/yfinance dependency, live provider client, scheduler or same-day finality change was added. |
| S&P500 + NASDAQ100 benchmark operational data | Implemented / validated (real PostgreSQL historical datasets loaded) | `SP500` is configured as `S&P 500`, `MARKET_INDEX`, `USD`, `index_owner=SP_DOW_JONES_INDICES`, `PRICE_RETURN`, `provider=YAHOO_FINANCE`, `provider_symbol=^GSPC`; `NASDAQ100` is configured as `NASDAQ-100`, `MARKET_INDEX`, `USD`, `index_owner=NASDAQ`, `PRICE_RETURN`, `provider=YAHOO_FINANCE`, `provider_symbol=^NDX`. Both benchmark rows were bootstrapped into real PostgreSQL. Each validated 5-year daily Close dataset contains 1,255 persisted BenchmarkPrice observations from 2021-09-07 through 2026-09-04 with source `DATA_TEAM_YAHOO_FINANCE_CLOSE`. Real authenticated Benchmark Comparison API smoke passed for both USD-base portfolios and TRY-base portfolios. The TRY-base comparison used persisted historical TCMB USD/TRY midpoint conversion with latest-on-or-before FX behavior, confirming that foreign-benchmark performance includes currency impact. No benchmark-specific comparison logic, migration, runtime Yahoo/yfinance dependency, live benchmark provider client or scheduled benchmark sync was added. |
| TEFAS client/integration | Implemented and actively extended | General info, historical price, portfolio breakdown, management-fee source extraction/history persistence and bulk refresh/history sync for YAT/EMK and fund-detail page/profile metadata are used through the backend integration/service layer |
| TEFAS daily raw data | Implemented | Core raw fields include fund code/name/date, price, shares outstanding, investor count, portfolio size and BYF exchange bulletin price where available |
| TEFAS scheduled daily sync | Complete / merged | Default scheduled sync runs YAT, EMK, BYF, GYF and GSYF sequentially using fund-kind-level bulk general-info requests; merged in PR #34 |
| TEFAS detail snapshot | Implemented | Includes fund category, 1-year category rank, category fund count, raw market-share value, official TEFAS risk value and source-oriented profile metadata |
| TEFAS portfolio allocation | Implemented / validated | 54 raw allocation fields observed; 43 mapped by same-date raw/UI verification; 11 preserved as unresolved/unobserved raw fields |
| TEFAS derived metrics | Implemented | Daily, five-observation and one-month performance/evolution metrics are available for the implemented raw series |
| TEFAS capability/gap analysis | Complete | Direct vs derived vs unavailable vs external-source-needed decisions documented for the data team |
| Official TEFAS risk value | Complete / merged | `profilData["riskDegeri"]` is normalized to `risk_value: int | None`, validated to 1..7 and persisted in detail snapshots |
| External source decision | Complete for current MVP | TEFAS is primary; KAP is preferred official supplementary source when needed; FVT is not a required backend dependency |
| AI integration | Not started in backend | Analytics, sentiment and report-Q&A integration remain later-stage work |
| Frontend integration | Not started in backend | Stable backend contracts will be provided as domains are finalized |

## Authentication and portfolio API

Implemented routes include:

```text
GET    /api/v1/health
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/auth/me
GET    /api/v1/assets

POST   /api/v1/portfolios
GET    /api/v1/portfolios
GET    /api/v1/portfolios/{portfolio_id}
PATCH  /api/v1/portfolios/{portfolio_id}
DELETE /api/v1/portfolios/{portfolio_id}
GET    /api/v1/portfolios/{portfolio_id}/transactions
POST   /api/v1/portfolios/{portfolio_id}/cash-flows
GET    /api/v1/portfolios/{portfolio_id}/cash-flows
GET    /api/v1/portfolios/{portfolio_id}/cost-basis?as_of_date=YYYY-MM-DD
GET    /api/v1/portfolios/{portfolio_id}/unrealized-pl?as_of_date=YYYY-MM-DD
GET    /api/v1/portfolios/{portfolio_id}/realized-pl?as_of_date=YYYY-MM-DD
```

Do not infer additional public API endpoints from internal TEFAS services unless they are explicitly implemented and registered.

## TEFAS daily-data capability

Verified daily business fields currently used by the backend:

- `fund_code`
- `fund_name`
- `data_date`
- `price`
- `shares_outstanding`
- `investor_count`
- `portfolio_size`
- `exchange_bulletin_price`

Important provider-specific behavior:

- BYF raw `kisiSayisi=0` was verified to represent unavailable investor-count data in tested observations and is normalized to `None`.
- `exchange_bulletin_price` was observed populated for BYF in the tested August 2026 dates.
- The same raw field was present but `NULL` in tested YAT, EMK, GYF and GSYF observations.
- Provider-specific semantics must remain inside the TEFAS integration/service layer.

## TEFAS detail snapshot capability

The backend detail-page metadata extraction and fund-detail snapshot persistence currently preserve source-oriented values for:

- `fund_category`
- `category_rank`
- `category_fund_count`
- `market_share_raw`
- `risk_value`
- `isin`
- `tefas_status`
- `transaction_start_time`
- `transaction_end_time`
- `entry_commission_raw`
- `exit_commission_raw`
- `interest_content`
- `fund_sale_valor`
- `fund_redemption_valor`

`category_rank` / `category_fund_count` were validated against the TEFAS detail-analysis semantics as the current 1-year category ranking and category fund count.

The official TEFAS 1–7 fund risk value is source-confirmed, extracted from exact-matching `profilData["riskDegeri"]`, validated to 1..7 and persisted in fund-detail snapshots. Do not substitute a derived volatility score when the official source value is unavailable. Raw commission values are persisted without percentage conversion, and valor values are persisted as source integer fields without inferred settlement semantics.

## TEFAS portfolio-allocation status

`dagilimSiraliGetirT` exposes 54 observed allocation raw fields after metadata is excluded.

Current validation status:

- **43 / 54** raw allocation fields have verified same-date TEFAS raw/UI business-label mappings.
- **11 / 54** remain unresolved/unobserved:
  - `bb`
  - `db`
  - `dot`
  - `eut`
  - `fkb`
  - `kh`
  - `kks`
  - `t`
  - `vm`
  - `yba`
  - `ymk`

Additional validation was performed across all five supported fund kinds (`YAT`, `EMK`, `BYF`, `GYF`, `GSYF`) and sample dates in both 2025 and 2026.

A total of **12,476 raw portfolio-breakdown rows** were checked for these 11 fields and no non-zero observation was found.

Therefore:

- Do not guess business labels for these 11 fields.
- Preserve them as unknown/unobserved raw fields for future discovery.
- They are not currently a blocker for using the verified active allocation mappings.

## Implemented / established TEFAS metrics

Current metric capability includes:

### Return metrics

- Daily return
- Five-observation return
- One-month return

### Daily evolution metrics

- Investor-count daily change
- Investor-count daily growth ratio
- AUM daily change
- AUM daily growth ratio
- Average AUM per investor
- Shares-outstanding change
- BYF exchange-bulletin metrics where applicable

### Five-observation evolution metrics

- `five_observation_aum_change`
- `five_observation_aum_growth_ratio`
- `five_observation_investor_count_change`
- `five_observation_investor_count_growth_ratio`

### One-month evolution metrics

- `one_month_aum_change`
- `one_month_aum_growth_ratio`
- `one_month_investor_count_change`
- `one_month_investor_count_growth_ratio`

### Estimated net fund flow capability

Estimated net fund flow is classified as `DERIVABLE_FROM_TEFAS`.

Conservative derivation:

```text
estimated_net_fund_flow
    = current_AUM
    - previous_AUM * (current_price / previous_price)
```

This removes the estimated valuation-return effect from the AUM change.

Important limitation:

- This is an **estimated derived flow metric**.
- It is not a direct TEFAS subscription/redemption transaction field.
- Raw investor cash-flow transactions remain unavailable in the verified TEFAS dataset.

## External data-source decision

Current MVP source priority:

1. **TEFAS** — primary source for daily fund data and validated fund-detail/allocation data.
2. **KAP** — preferred official supplementary source when a required disclosure, settlement/value-date field or more granular official fund document cannot be reliably obtained through TEFAS.
3. **FVT** — may be used only as a reference, cross-check or product-analysis inspiration source; it is not a required backend data dependency for the current MVP.

The capability/gap analysis concluded that the current core short-term fund-analysis requirements do not justify adding FVT as a mandatory source.

## Verification performed

Important verified checkpoints include:

- Authentication and Portfolio CRUD were previously verified against PostgreSQL.
- ExchangeRate migration `20260826_0013` passed real PostgreSQL upgrade/downgrade/upgrade round-trip and constraint/repository smoke checks.
- Real TCMB client and TCMB-to-PostgreSQL sync smoke checks passed with effective-date and Decimal-rate preservation.
- Valuation market-data smoke verified TEFAS NAV selection, BYF exchange-market selection, and direct/inverse/cross FX conversion on PostgreSQL.
- Valuation market-data focused suite passed 65 tests; full backend suite passed 853 tests.
- TEFAS fund-kind and daily-column discovery covered `YAT`, `EMK`, `BYF`, `GYF` and `GSYF`.
- Portfolio-allocation raw/UI verification produced 43 verified mappings.
- The 11 unresolved allocation fields were scanned across 12,476 raw rows without a non-zero observation.
- TEFAS detail-page extraction for `fund_category`, `category_rank`, `category_fund_count`, `market_share_raw`, `isin` and `risk_value` is covered by automated tests.
- Official risk value is extracted only from exact matching `profilData["fonKodu"]` and `profilData["riskDegeri"]`; unidentified or other-fund profile data is ignored.
- TEFAS detail-page parsing ignores Next.js reference-string marker occurrences such as `$...:profilData` while preserving strict handling for other decoded non-object marker values.
- Live AAL detail-page smoke verification after this parser robustness change returned `fund_category=Para Piyasası Fonu` and `risk_value=1`.
- TEFAS ISIN is source-confirmed from exact-matching `profilData["isinKodu"]`; missing values normalize to `None`, while present string values are trimmed and uppercased.
- Live ISIN extraction was verified through the service layer for sample YAT, EMK, BYF, GYF and GSYF funds.
- `Asset.isin` is nullable `String(32)` metadata added by migration `20260819_0009`; no unique, index or format constraint is imposed at this stage.
- Fund-detail observation enriches a missing Asset ISIN from already-fetched TEFAS metadata without making an additional provider request; matching values are accepted and conflicting non-null values raise instead of being silently overwritten.
- Asset ISIN enrichment and new snapshot persistence share the same transaction; rollback behavior is covered by tests, including snapshot persistence failure.
- Focused Asset/observation-service test suite: **27 passed**.
- Fresh SQLite migration upgrade through `20260819_0009` passed, and migration round-trip `0009 -> 0008 -> 0009` passed.
- Migration `20260817_0008` adds nullable `risk_value` with a database check constraint limiting non-null values to 1..7.
- Fresh SQLite `alembic upgrade head` passed through revision `20260817_0008`.
- SQLite migration round-trip `0008 -> 0007 -> 0008` passed.
- Focused risk-value test suite: **109 passed**.
- `git diff --check` passed for the risk-value implementation, with Windows LF/CRLF normalization warnings only.
- Multi-kind scheduled daily sync was verified locally for `YAT`, `EMK`, `BYF`, `GYF` and `GSYF`.
- The scheduled flow uses fund-kind-level bulk general-info requests rather than one request per fund.
- Real TEFAS/PostgreSQL smoke test for 2026-08-17 persisted: YAT 2033, EMK 400, BYF 30, GYF 255 and GSYF 539 funds; 3257 TEFAS fund assets were present after the sync.
- Focused scheduled-sync test suite: **20 passed**.
- Focused PR1 TEFAS management-fee client/service extraction tests: **132 passed**.
- Focused TEFAS management-fee history persistence tests: **43 passed**.
- Focused TEFAS management-fee bulk refresh/history sync tests: **57 passed**.
- Focused TEFAS detail-page profile metadata extraction tests: **141 passed**.
- Focused TEFAS detail snapshot model, observation-service and bulk-refresh test suite: **66 passed**.
- Current full backend test-suite result: **675 passed**.
- `git diff --check` passed for the current TEFAS detail-page profile metadata persistence change.
- Short-term evolution metrics were implemented and merged in PR #29.
- Transaction migration `20260825_0012` was applied on real PostgreSQL.
- Transaction migration round-trip `0012 -> 0011 -> 0012` passed.
- Focused Transaction-related suite: **76 passed**.
- Current full backend test-suite result after Transaction foundation: **731 passed**.
- Real PostgreSQL BUY 10 / SELL 4 smoke produced net quantity `6.00000000`.
- Real PostgreSQL `FOR UPDATE` smoke verified a second session was blocked while the first held the portfolio lock.
- Focused Holdings integration slice: **35 passed**.
- Real PostgreSQL BUY 10 / SELL 4 holdings smoke produced quantity `6.00000000`.
- Current full backend suite after Holdings foundation: **753 passed**.
- Portfolio valuation + transaction repository focused regression suite: **53 passed**.
- Wider valuation/holdings/market-data integration suite: **127 passed**.
- Real PostgreSQL portfolio valuation smoke: **PASS**. It verified that future SELL does not affect historical as-of quantity, YAT uses NAV, BYF uses `exchange_bulletin_price` with no NAV fallback, USD/TRY TCMB midpoint FX conversion works, exact Decimal portfolio total is preserved, and the transaction was rolled back after the smoke.
- Current full backend suite after Portfolio Valuation Aggregation v1: **885 passed**.
- Portfolio Valuation API focused response/API/service suite: **47 passed**.
- Wider Portfolio/Transaction/Holdings/valuation API integration suite: **203 passed**.
- Real PostgreSQL + FastAPI valuation endpoint smoke: **PASS**. It verified HTTP 200 through the actual FastAPI route/dependency graph, `valuation_date` response preservation, future SELL exclusion from historical as-of quantity, YAT NAV price, BYF `exchange_bulletin_price` / `EXCHANGE_MARKET`, USD/TRY TCMB midpoint FX, exact portfolio total, Decimal monetary values serialized as JSON strings, and smoke data rollback afterward.
- Current full backend suite after Portfolio Valuation API Contract v1: **905 passed**.
- Focused Portfolio Valuation service/response/API suite after Portfolio Weights v1: **61 passed**.
- Wider Portfolio/Transaction/Holdings/valuation/price/FX integration after Portfolio Weights v1: **217 passed**.
- Real PostgreSQL + real FastAPI endpoint smoke after Portfolio Weights v1: **PASS**. It verified COMPLETE portfolio total `100`, TRY weight `0.25`, USD asset native value `7.5`, TCMB midpoint FX `10`, converted market value `75`, USD weight `0.75`, weight JSON type string, INCOMPLETE portfolio total `None`, all INCOMPLETE portfolio weights `None`, and smoke transaction rollback afterward.
- Current full backend suite after Portfolio Weights v1: **919 passed**.
- `git diff --check` passed after Portfolio Weights v1 with harmless Windows LF/CRLF normalization warnings only.
- Focused Cost Basis + transaction repository tests after service-level Cost Basis v1: **51 passed**.
- Wider transaction/holdings/valuation/market-data regression suite after service-level Cost Basis v1: **222 passed**.
- Real PostgreSQL Cost Basis smoke after service-level Cost Basis v1: **PASS**. It verified historical weighted average, partial SELL behavior, full SELL reset, later BUY reset and rollback confirmation.
- Current full backend suite after service-level Cost Basis v1: **944 passed**.
- Focused Cost Basis service + response + API tests after public API contract: **38 passed**.
- Wider Transaction/Holdings/Cost Basis/Valuation regression suite after public API contract: **186 passed**.
- Real PostgreSQL + real FastAPI Cost Basis API smoke: **PASS**. It verified HTTP 200, COMPLETE result, historical as-of date handling, future BUY exclusion, partial SELL quantity `10`, total cost `250`, average cost `25`, SELL unit_price ignored for cost basis, Decimal JSON strings, no portfolio-level `total_cost_basis` and rollback confirmation.
- Current full backend suite after Cost Basis public API contract: **963 passed**.
- Focused Unrealized P/L service tests after service-level Unrealized P/L v1: **28 passed**.
- Wider Transaction/Cost Basis/valuation-price/Portfolio Valuation/Unrealized P/L regression suite after service-level Unrealized P/L v1: **133 passed**.
- Real PostgreSQL Unrealized P/L service smoke after service-level Unrealized P/L v1: **PASS**. It verified portfolio base currency TRY, asset currency USD, no FX dependency, historical as-of date `2026-08-22`, two BUYs producing MWAC `25`, partial SELL leaving quantity `10` and total cost basis `250`, SELL unit_price `999` ignored for cost basis, future BUY excluded, future market price excluded, latest price on-or-before selected as `35` on `2026-08-21`, native market value `350`, native Unrealized P/L `+100 USD`, no portfolio-level P/L total and rollback confirmation.
- Current full backend suite after service-level Unrealized P/L v1: **991 passed**.
- `git diff --check` passed after service-level Unrealized P/L v1.
- Focused Unrealized P/L service/response/API tests after public API contract: **57 passed**.
- Wider regression suite after Unrealized P/L public API contract: **202 passed**.
- Real PostgreSQL + actual FastAPI Unrealized P/L HTTP smoke after public API contract: **PASS**. It confirmed PostgreSQL, HTTP 200, TRY portfolio / USD YAT asset, no FX dependency, two BUYs `10@20` and `10@30`, SELL `10@999`, future BUY excluded, future price excluded, remaining quantity `10`, total cost basis `250`, average cost `25`, selected NAV `35` dated `2026-08-21`, native market value `350 USD`, native Unrealized P/L `+100 USD`, portfolio-level total absent and rollback PASS.
- Current full backend suite after Unrealized P/L public API contract: **1020 passed**.
- Diff/scope review passed after Unrealized P/L public API contract; `UnrealizedPlService` remained unchanged during the API slice.
- Focused service/repository/shared-replay tests after service-level Realized P/L v1: **85 passed**.
- Wider regression suite after service-level Realized P/L v1: **162 passed**.
- GPT-5.5 High financial correctness review for service-level Realized P/L v1: **PASS**, with **CRITICAL FINDINGS: NONE**.
- Real PostgreSQL Realized P/L service smoke after service-level Realized P/L v1: **PASS**. It verified full exit, re-entry/new MWAC cycle, cumulative realized values, future transaction exclusion, fully sold asset retention and rollback confirmation.
- Current full backend suite after service-level Realized P/L v1: **1054 passed**.
- `git diff --check` passed after service-level Realized P/L v1.
- Focused Realized P/L service/response/API tests after public Realized P/L API contract: **45 passed**.
- Wider Cost Basis/Unrealized P/L/Realized P/L API regression after public Realized P/L API contract: **58 passed**.
- Real PostgreSQL + actual FastAPI Realized P/L HTTP smoke after public API contract: **PASS**. It verified HTTP 200, full exit, re-entry/new MWAC cycle, cumulative realized values, future transaction exclusion, fully sold asset retention, Decimal JSON string serialization, no portfolio-level total or FX fields, and rollback PASS.
- Current full backend suite after public Realized P/L API contract: **1078 passed**.
- `git diff --check` passed after public Realized P/L API contract.
- Focused Transaction History public API repository/service/response/API tests: **78 passed**.
- Wider Transaction/Holdings/Cost Basis/Portfolio Valuation/Unrealized P/L/Realized P/L regression after Transaction History public API: **269 passed**.
- Real PostgreSQL + actual FastAPI Transaction History HTTP smoke: **PASS**. It verified HTTP 200 listing, `skip`/`limit`/`total` pagination, deterministic `transaction_date ASC, id ASC` ordering, Decimal quantity/unit-price JSON string serialization, ownership isolation with 404 `Portfolio not found.`, and rollback confirmation.
- Current full backend suite after Transaction History public API: **1092 passed**.
- `git diff --check` passed after Transaction History public API.
- Focused Asset Catalog public API repository/service/response/API tests: **14 passed**.
- Wider Asset Catalog/Asset Repository/TEFAS/Transaction regression after Asset Catalog public API: **135 passed**.
- Real PostgreSQL + actual FastAPI Asset Catalog HTTP smoke: **PASS**. It verified HTTP 200 listing, PostgreSQL case-insensitive `asset_code`/`asset_name` search, active-only filtering, `skip`/`limit`/`total` pagination, deterministic `asset_code ASC, id ASC` ordering, nullable `isin`/`currency` preservation, generic TEFAS + MANUAL catalog scope, exclusion of `is_active` from the public response, and rollback confirmation.
- Current full backend suite after Asset Catalog public API: **1106 passed**.
- `python -m compileall src` passed after Asset Catalog public API.
- `git diff --check` passed after Asset Catalog public API.
- Public FastAPI API tests for valuation + unrealized P/L after Market Data Freshness: **49 passed**.
- Focused freshness/valuation/unrealized suite after Market Data Freshness: **129 passed**.
- Wider market-data regression after Market Data Freshness: **184 passed**.
- Current full backend suite after Market Data Freshness: **1117 passed**.
- `git diff --check` passed after Market Data Freshness.
- Transaction Currency migration `20260902_0014` was applied successfully on real PostgreSQL from `20260826_0013`.
- Wider Transaction/Holdings/Cost Basis/Realized P/L/Unrealized P/L/Portfolio Valuation regression after Transaction Currency: **349 passed**.
- GPT-5.5 High concurrency/data-integrity final diff review after Transaction Currency: **PASS**, with no blocking issues, non-blocking issues or scope violations.
- Real PostgreSQL + actual FastAPI Transaction Currency smoke: **PASS**. It verified request normalization from `" try "` to `TRY`, same portfolio + asset currency consistency, rejection of a conflicting `USD` transaction with HTTP 422, legacy null `transaction_currency` readability, PostgreSQL CHECK rejection of unsupported `JPY`, and smoke-data cleanup.
- Current full backend suite after Transaction Currency: **1133 passed**.
- `git diff --check` passed for the Transaction Currency implementation before feature close.
- PortfolioCashFlow foundation migration `20260902_0015`, following `20260902_0014`, was applied successfully on real PostgreSQL.
- Focused PortfolioCashFlow tests: **40 passed**.
- Wider Portfolio/Transaction-related regression after PortfolioCashFlow foundation: **300 passed**.
- Real PostgreSQL migration/schema smoke after PortfolioCashFlow foundation: **PASS**.
- Real PostgreSQL + actual FastAPI PortfolioCashFlow smoke: **PASS**. It verified DEPOSIT/WITHDRAWAL creation, request normalization, Decimal amount JSON string serialization, deterministic `flow_date ASC, id ASC` ordering, pagination, ownership isolation with 404 `Portfolio not found.`, unsupported `JPY` rejection and smoke cleanup.
- Current full backend suite after PortfolioCashFlow foundation: **1173 passed**.
- Final PortfolioCashFlow diff/scope review: **PASS**, with no blocking issues, non-blocking issues or scope violations.
- Focused cash replay repository/service tests: **12 passed**.
- GPT-5.5 High financial correctness review for Derived per-currency cash replay foundation: **PASS**, with no blocking issues, non-blocking issues or scope violations.
- Wider related regression after Derived per-currency cash replay foundation: **312 passed**.
- Current full backend suite after Derived per-currency cash replay foundation: **1185 passed**.
- `git diff --check` passed after Derived per-currency cash replay foundation.
- Initial focused valuation + cash-replay tests after Historical portfolio valuation including derived cash: **92 passed**.
- GPT-5.5 High financial correctness review for Historical portfolio valuation including derived cash: **PASS**, with no blocking issues or scope violations.
- High review identified 2 non-blocking test gaps; both were added without production code changes.
- Valuation service tests after edge-case additions: **49 passed**.
- Focused valuation + cash-replay set after edge-case additions: **94 passed**.
- Wider related regression after Historical portfolio valuation including derived cash: **271 passed**.
- Current full backend suite after Historical portfolio valuation including derived cash: **1203 passed**.
- `git diff --check` passed after Historical portfolio valuation including derived cash.
- Initial focused implementation/affected tests after Portfolio Historical Performance / TWR foundation: **121 passed**.
- GPT-5.5 High TWR financial correctness review: **PASS**, with no blocking issues or scope violations.
- High review identified 2 non-blocking targeted TWR test gaps.
- Both targeted TWR tests were added without production-code changes.
- Performance service tests after targeted additions: **28 passed**.
- Focused TWR/API/repository set after targeted additions: **40 passed**.
- Wider related regression after Portfolio Historical Performance / TWR foundation: **308 passed**.
- Current full backend suite after Portfolio Historical Performance / TWR foundation: **1240 passed**.
- `git diff --check` passed after Portfolio Historical Performance / TWR foundation.
- Initial benchmark model/repository tests after provider-independent Benchmark + BenchmarkPrice storage foundation: **22 passed**.
- Initial wider storage-adjacent run after provider-independent Benchmark + BenchmarkPrice storage foundation: **63 passed**.
- First final Benchmark storage foundation review: **FAIL** due `native_currency` allowing non-alphabetic 3-character values.
- Benchmark storage blocker was fixed in the model and migration.
- Benchmark model tests after currency fix: **23 passed**.
- Benchmark repository tests after lookup-isolation fix: **11 passed**.
- Wider storage-adjacent run after Benchmark storage fixes: **75 passed**.
- Re-review after Benchmark storage fixes: **PASS**, with no blocking issues, non-blocking issues or scope violations.
- Real PostgreSQL migration/schema smoke after Benchmark storage foundation: **PASS**.
- Current full backend suite after provider-independent Benchmark + BenchmarkPrice storage foundation: **1274 passed**.
- `git diff --check` passed after provider-independent Benchmark + BenchmarkPrice storage foundation.
- Initial focused benchmark/import tests after Benchmark metadata + generic historical price import foundation: **78 passed**.
- Initial wider storage-adjacent run after Benchmark metadata + generic historical price import foundation: **208 passed**.
- GPT-5.5 High review for Benchmark metadata + generic historical price import foundation: **FAIL** due migration safety, silent overwrite/provenance overwrite and Decimal scale issues.
- Benchmark metadata + generic import blockers were fixed.
- Focused benchmark/import tests after fixes: **94 passed**.
- Wider storage-adjacent run after fixes: **224 passed**.
- GPT-5.5 High re-review after fixes: **PASS**, with no blocking issues, non-blocking issues or scope violations.
- Real PostgreSQL migration/schema smoke after Benchmark metadata + generic import foundation: **PASS**.
- Real PostgreSQL import smoke after Benchmark metadata + generic import foundation: **PASS**. It verified insert, idempotency, conflict protection, explicit revision, Decimal scale rejection, current/future rejection, atomic rollback and cleanup.
- Current full backend suite after Benchmark metadata + generic historical price import foundation: **1334 passed in 22.14s**.
- `git diff --check` passed after Benchmark metadata + generic historical price import foundation.
- Focused Generic Benchmark Comparison API tests: **33 passed**.
- Wider benchmark/performance/FX related regression: **167 passed**.
- GPT-5.5 High financial/correctness review for Generic Benchmark Comparison API: **PASS**, with no blocking issues or scope violations.
- Real PostgreSQL + FastAPI Benchmark Comparison smoke: **PASS**; authenticated HTTP comparison, hidden baseline, Decimal returns/normalization, ownership isolation and outer-transaction rollback cleanup were verified.
- Current full backend suite after Generic Benchmark Comparison API: **1356 passed in 22.51s**.
- `git diff --check` passed after Generic Benchmark Comparison API; only existing Windows LF-to-CRLF normalization warnings were reported.
- Focused BIST100 bootstrap / generic CSV import tooling tests: **28 passed**.
- Existing benchmark regression after BIST100 bootstrap/import tooling: **116 passed**.
- GPT-5.5 High correctness/data-integrity review for BIST100 bootstrap/import tooling: **PASS**, with no blocking issues or scope violations.
- Real PostgreSQL BIST100 bootstrap smoke: **PASS**; exact metadata creation, idempotent rerun, duplicate prevention and outer-transaction rollback cleanup were verified.
- Real PostgreSQL BIST100 CSV import smoke: **PASS**; canonical CSV parsing, two historical BenchmarkPrice inserts, exact Decimal preservation, exact source provenance and rollback cleanup were verified.
- Current full backend suite after BIST100 bootstrap/import tooling: **1384 passed in 22.81s**.
- Data-team S&P500 dataset received from Yahoo Finance/yfinance using `^GSPC`, `Close`, `5y`, `1d`, `auto_adjust=False`: **1255 rows**, date range **2021-09-07 through 2026-09-04**.
- S&P500 canonicalization validation: **PASS**; 1255 dates preserved, duplicate/weekend/non-positive rows absent, 1122 close values normalized explicitly to 8 decimal places, maximum absolute rounding adjustment `0.000000005`.
- Full canonical S&P500 dataset dry validation through the existing backend CSV reader/parser: **PASS**, 1255/1255 observations accepted.
- Data-team NASDAQ100 dataset received from Yahoo Finance/yfinance using `^NDX`, `Close`, `5y`, `1d`, `auto_adjust=False`: **1255 rows**, date range **2021-09-07 through 2026-09-04**.
- NASDAQ100 canonicalization validation: **PASS**; 1255 dates preserved, duplicate/weekend/non-positive rows absent, 755 close values normalized explicitly to 8 decimal places, maximum absolute rounding adjustment `0.000000005`.
- Full canonical NASDAQ100 dataset dry validation through the existing backend CSV reader/parser: **PASS**, 1255/1255 observations accepted.
- Real PostgreSQL SP500/NASDAQ100 bootstrap rollback smoke: **PASS**; both produced `CREATED -> ALREADY_EXISTS` with exact locked Yahoo Finance provider symbols, and rollback left no production rows.
- Focused SP500/NASDAQ100 benchmark config/bootstrap tests: **35 passed**.
- Current full backend suite after SP500/NASDAQ100 benchmark registry extension: **1391 passed in 22.69s**.
- Focused Benchmark Catalog service/response/API plus Benchmark Comparison API regression tests: **11 passed in 0.67s**.
- Real PostgreSQL + FastAPI Benchmark Catalog HTTP smoke: **PASS**; unauthenticated access returned HTTP 401, authenticated access returned HTTP 200 with `total=3`, deterministic `BIST100 -> NASDAQ100 -> SP500` ordering and exact public response fields only; temporary user data rolled back and production benchmark rows were preserved.
- Current full backend suite after Benchmark Catalog API: **1396 passed in 22.73s**.
- Real PostgreSQL SP500 bootstrap/import: **PASS**; benchmark metadata was created with `YAHOO_FINANCE` / `^GSPC`, and **1255** historical BenchmarkPrice rows were persisted from **2021-09-07 through 2026-09-04** with source `DATA_TEAM_YAHOO_FINANCE_CLOSE`.
- Real PostgreSQL NASDAQ100 bootstrap/import: **PASS**; benchmark metadata was created with `YAHOO_FINANCE` / `^NDX`, and **1255** historical BenchmarkPrice rows were persisted from **2021-09-07 through 2026-09-04** with source `DATA_TEAM_YAHOO_FINANCE_CLOSE`.
- Real persisted SP500/NASDAQ100 authenticated Benchmark Comparison API smoke with a temporary USD-base cash-only portfolio: **PASS**; both comparisons returned `COMPLETE`, matched independently calculated persisted-price returns, and rollback preserved both 1255-row production datasets.
- Historical TCMB rates for **2026-09-02, 2026-09-03 and 2026-09-04** were fetched through the existing historical TCMB client and persisted successfully for USD/EUR/GBP -> TRY; all 9 rows were created with no updates.
- Real persisted SP500/NASDAQ100 authenticated Benchmark Comparison API smoke with a temporary TRY-base cash-only portfolio: **PASS**; historical USD -> TRY conversion used persisted TCMB midpoint rates with latest-on-or-before semantics, both comparisons returned `COMPLETE`, calculated returns matched independently converted benchmark levels, temporary HTTP data rolled back, and production benchmark/FX rows were preserved.
- Data-team BIST100 dataset received from Yahoo Finance/yfinance using `XU100.IS`, `Close`, `5y`, `1d`, `auto_adjust=False`: **1251 rows**, date range **2021-09-06 through 2026-09-04**.
- BIST100 canonicalization validation: **PASS**; all 1251 dates were preserved, duplicate/weekend/non-positive rows were absent, 976 close values were normalized explicitly to 8 decimal places, and maximum absolute rounding adjustment was `0.000000005`.
- Full canonical BIST100 dataset dry validation through the existing backend CSV reader/parser: **PASS**, 1251/1251 observations accepted.
- Real PostgreSQL BIST100 bootstrap: **CREATED** with locked `YAHOO_FINANCE` / `XU100.IS` metadata.
- Real PostgreSQL BIST100 historical import: **PASS**; `canonical_rows_read=1251`, `fetched_rows=1251`, `rows_created=1251`, `rows_updated=0`, source `DATA_TEAM_YAHOO_FINANCE_CLOSE`.
- Real PostgreSQL persisted-dataset verification: **PASS**; 1251 rows, first `2021-09-06 / 1474.69995117`, last `2026-09-04 / 14012.40039063`.
- Real BIST100 end-to-end Benchmark Comparison HTTP smoke: **PASS**; persisted BIST100 data produced HTTP 200, correct hidden baseline/return/excess-return behavior, temporary user/portfolio data rolled back, and all 1251 real benchmark rows remained persisted.

- GPT-5.5 High financial/finality review for Benchmark Daily Sync completed; findings covering Europe/Istanbul operational date handling, future-reference-date protection, provider-range integrity, post-quantization positivity and yfinance dataframe compatibility were fixed.
- Focused Benchmark Daily Sync / Yahoo provider / scheduler / import / catalog / comparison regression suite after High-review fixes: **155 passed**.
- Real Yahoo Finance provider smoke: **PASS**; `XU100.IS`, `^GSPC` and `^NDX` returned real completed daily Close observations for 2026-09-01 through 2026-09-04, all converted to Decimal with 8-decimal canonicalization and no fabricated weekend rows.
- Real PostgreSQL + Yahoo Benchmark Daily Sync rollback smoke: **PASS**; all three supported benchmarks re-fetched the 2026-09-04 Close through the full Yahoo -> client -> daily-sync -> importer -> PostgreSQL path, created exactly one temporary row each with source `YAHOO_FINANCE_DAILY_CLOSE`, performed no revisions, and outer rollback preserved all production benchmark rows.
- Current full backend suite after Benchmark Daily Scheduled Sync + completed-close finality: **1444 passed in 23.35s**.
- `python -m compileall src scripts` and `git diff --check` passed after Benchmark Daily Sync finality fixes.

- Real weekend/holiday Benchmark Daily Sync smoke on 2026-09-06: **PASS**; Yahoo/yfinance returned stale 2026-09-04 rows for all three supported benchmarks despite the requested `[2026-09-05, 2026-09-06)` range. The Yahoo client now ignores pre-start stale observations before Close canonicalization, still rejects `price_date >= end_date`, and the scheduled run completed as a clean no-op for BIST100, SP500 and NASDAQ100 with `fetched_rows=0`, `rows_created=0`, `rows_updated=0`.
- Current full backend suite after the Yahoo weekend/holiday stale-row no-op fix: **1449 passed in 23.35s**.
- Watchlist migration `20260907_0018`, following `20260903_0017`, was applied successfully on real PostgreSQL; `alembic current` reports `20260907_0018 (head)`.
- Focused Watchlist plus relevant Asset/Auth regression: **38 passed**.
- Real PostgreSQL + actual FastAPI Watchlist HTTP smoke: **PASS**. It verified authenticated create/list/delete, exact public response fields, same-user duplicate rejection with HTTP 409, same asset allowed for different users, ownership-isolated listing, cross-user delete isolation with HTTP 404, owner delete with HTTP 204, and outer-transaction rollback cleanup with zero smoke rows surviving.
- Current full backend suite after Watchlist v1: **1472 passed in 25.28s**.
- `python -m compileall src alembic` and `git diff --check` passed for Watchlist v1.
- DataSyncRun / synchronization-status auditing v1 is implemented with migration `20260907_0019`, following `20260907_0018`. The generic `data_sync_runs` table records scheduler-level `TEFAS_DAILY` and `BENCHMARK_DAILY` runs as `RUNNING`, `SUCCESS` or `FAILED`; the existing detailed `TefasFetchLog` remains unchanged.
- Scheduled TEFAS and benchmark entry points now create exactly one durable DataSyncRun per invocation using a separate audit database session. Existing child-job continuation and data-import semantics are preserved, and failed runs persist only safe generic error messages.
- Authenticated `GET /api/v1/data-sync/status` returns the latest persisted run for each supported sync type in deterministic TEFAS-then-Benchmark order and performs no provider calls.
- DataSyncRun migration `20260907_0019` was applied successfully on real PostgreSQL; `alembic current` reports `20260907_0019 (head)`.
- Focused DataSyncRun, scheduler and relevant TefasFetchLog regression: **63 passed**.
- Real PostgreSQL + scheduler audit + actual FastAPI status HTTP smoke: **PASS**. It verified TEFAS success auditing, benchmark partial-failure continuation, safe generic failure persistence, unauthenticated HTTP 401, authenticated HTTP 200, latest-per-type ordering, exact public fields and outer-transaction rollback cleanup with zero smoke rows surviving.
- Current full backend suite after DataSyncRun v1: **1497 passed in 25.31s**.
- `python -m compileall src scripts alembic` and `git diff --check` passed for DataSyncRun v1.
- Notes v1 is implemented with migration `20260907_0020`, following `20260907_0019`. Notes are authenticated user-owned portfolio notes with required `user_id`, `portfolio_id` and `note_text`; no asset/transaction linkage, title, tags, soft delete, PATCH or DELETE behavior was added.
- Notes API provides authenticated `POST /api/v1/notes` and `GET /api/v1/notes`. Create validates portfolio ownership through the existing active-portfolio ownership path, returns HTTP 404 for missing/foreign/deleted portfolios, trims note text and accepts 1-2000 characters. Listing is user-isolated and ordered by `created_at DESC, id DESC` with pagination.
- Existing notes remain persisted and listable after their portfolio is soft-deleted, while new notes cannot be created for a deleted portfolio.
- Notes migration `20260907_0020` was applied successfully on real PostgreSQL; `alembic current` reports `20260907_0020 (head)`.
- Focused Notes suite: **26 passed**; Notes plus relevant Portfolio/Auth regression: **51 passed**.
- Real PostgreSQL + actual FastAPI Notes HTTP smoke: **PASS**. It verified unauthenticated HTTP 401, cross-user portfolio isolation with HTTP 404, owner create with HTTP 201, exact public fields, trimmed text, deterministic listing/pagination, user isolation, deleted-portfolio create rejection, preservation of existing notes after portfolio deletion, and outer-transaction rollback cleanup with zero smoke rows surviving.
- Current full backend suite after Notes v1: **1523 passed in 29.10s**.
- `python -m compileall src alembic` and `git diff --check` passed for Notes v1.
- Generic AssetPrice storage foundation is implemented with migration `20260907_0021`, following `20260907_0020`. `AssetPrice` is a provider-independent historical price store for non-TEFAS assets, initially intended for precious-metal support; TEFAS prices remain canonical in `TefasFundDailyData` and benchmark prices remain canonical in `BenchmarkPrice`.
- `asset_prices` stores required `asset_id`, `price_date`, Decimal `price` (`Numeric(20,8)`) and nonblank `source`. It enforces positive prices and uniqueness on `(asset_id, price_date, source)`.
- AssetPrice repository lookups are explicitly source-aware. Latest-on-or-before never uses future observations; range queries are inclusive and deterministic. Repositories flush without committing.
- AssetPrice foundation intentionally does not yet add provider clients, precious-metal seed rows, currency/unit inference, APIs, schedulers, valuation/P&L wiring, OHLC fields or persisted daily-return values.
- AssetPrice migration `20260907_0021` was applied successfully on real PostgreSQL; `alembic current` reports `20260907_0021 (head)`.
- Focused AssetPrice suite after provenance hardening: **19 passed**.
- Real PostgreSQL AssetPrice smoke: **PASS**. It verified source-isolated historical lookup, future-price exclusion, source-isolated ranges, blank-source rejection, positive-price enforcement, duplicate `(asset_id, price_date, source)` rejection and outer-transaction rollback cleanup with zero smoke rows surviving.
- Current full backend suite after AssetPrice foundation: **1542 passed in 27.15s**.
- `python -m compileall src alembic` and `git diff --check` passed for AssetPrice foundation.
- PortfolioSnapshot storage foundation is implemented with migration `20260907_0022`, following `20260907_0021`. A snapshot is a persisted dated calculated result only and does not replace Transaction, PortfolioCashFlow or dynamic historical valuation as source of truth.
- `portfolio_snapshots` stores required `portfolio_id`, `snapshot_date` and Decimal `total_value_try`, `total_value_usd`, `total_value_eur`, `total_value_gbp` as `Numeric(20,8)`, with uniqueness on `(portfolio_id, snapshot_date)`.
- PortfolioSnapshot repository provides exact-date, latest-on-or-before, inclusive range and latest-by-portfolio lookups with deterministic ordering; repositories flush without committing.
- Zero and negative snapshot totals are intentionally permitted to remain compatible with the current derived-cash semantics.
- PortfolioSnapshot foundation intentionally does not yet add snapshot generation, scheduling, API exposure or any valuation/TWR/benchmark read-path changes.
- PortfolioSnapshot migration `20260907_0022` was applied successfully on real PostgreSQL; `alembic current` reports `20260907_0022 (head)`.
- Focused PortfolioSnapshot suite: **13 passed**; relevant Portfolio/cash repository regression: **27 passed**.
- Real PostgreSQL PortfolioSnapshot smoke: **PASS**. It verified exact lookup, future-snapshot exclusion, portfolio-isolated inclusive ranges, Decimal preservation, zero/negative value acceptance, duplicate `(portfolio_id, snapshot_date)` rejection and outer-transaction rollback cleanup with zero smoke rows surviving.
- Current full backend suite after PortfolioSnapshot foundation: **1555 passed in 27.51s**.
- `python -m compileall src alembic` and `git diff --check` passed for PortfolioSnapshot foundation.

## CORS integration foundation

- FastAPI CORS middleware is configured through `Settings.cors_allowed_origins`; local frontend origins default to `http://127.0.0.1:4173` and `http://localhost:4173`.
- CORS uses an explicit origin allow-list rather than `*`, allows GET/POST/PATCH/DELETE and Authorization/Content-Type, and keeps `allow_credentials=False` for the current Bearer-token auth model.
- `CORS_ALLOWED_ORIGINS` is documented in `.env.example` and can be overridden per environment.
- Packaged Electron `app://local` behavior is intentionally not guessed; it will be verified during real desktop integration before another origin is allowed.
- Focused CORS suite: **3 passed**; Auth/Portfolio/Asset/CORS regression: **35 passed**.
- Real Uvicorn CORS preflight smoke: **PASS** for configured origin and rejection of an unconfigured origin.
- Current full backend suite after CORS integration foundation: **1558 passed in 27.67s**.

## Recent Git milestones

- **PR #29** — short-term evolution metrics; merged.
- **PR #30** — finalize TEFAS capability/gap analysis documentation; merged.
- **PR #31** - refresh `PROJECT_STATUS.md`; merged.
- **TEFAS risk-value feature** - official `riskDegeri` extraction, snapshot persistence and migration `20260817_0008`; merged.
- **PR #34** - multi-kind scheduled daily TEFAS synchronization for YAT, EMK, BYF, GYF and GSYF; merged.
- **Canonical branch:** `main`
- **Risk-value merge commit:** `5acb46c`
- **Multi-kind scheduled-sync merge commit:** `9ce2fda`

## Current data-team handoff status

The TEFAS capability/gap analysis requested for Zeynep's data work is complete.

Final high-level classification:

- Core daily fund data → **TEFAS direct**
- Historical/short-term evolution metrics → **TEFAS derived**
- Estimated net fund flow → **TEFAS derived**
- Verified allocation categories → **TEFAS direct**
- 1-year category ranking → **TEFAS direct**
- Official current risk value → **TEFAS direct; backend extraction and snapshot persistence complete**
- Raw subscription/redemption transactions → **unavailable in the verified TEFAS dataset**
- FVT → **not required for current MVP**
- KAP → **official supplementary source when needed**

## Immediate next backend steps

Work in small controlled increments. The TEFAS backend data foundation is complete; remaining provider-specific items stay pending unless a concrete product requirement makes them necessary.

Benchmark backend implementation is complete and validated, including provider-independent storage/import, real BIST100/SP500/NASDAQ100 historical data, Benchmark Comparison, Benchmark Catalog and completed-close daily Yahoo Finance synchronization. The remaining benchmark step is operational only: coordinate the external one-shot scheduler with the data-integration environment used for the project's daily TEFAS jobs and verify an actual scheduled run. Watchlist v1, DataSyncRun / synchronization-status auditing v1, Notes v1, the provider-independent generic AssetPrice storage foundation and the PortfolioSnapshot storage foundation are now implemented and validated. The precious-metal provider/data contract for gold, silver and platinum remains pending the data-integration owner's confirmed provider/source, identifiers, native currency and price unit; do not infer these values in backend code. PortfolioSnapshot generation and any valuation/TWR read-path integration remain intentionally deferred until the precious-metal valuation path and required multi-currency calculation semantics are complete.

## Current open decisions / remaining data gaps

The following data/provider items remain intentionally unresolved or deferred. They do not invalidate the completed valuation market-data foundation, but must not be guessed when a higher-level valuation requirement depends on them:

- `Asset.currency` remains nullable for TEFAS assets because no verified canonical fund valuation-currency mapping has been established. Do not infer TRY from fund kind/name and do not interpret an empty `getFplDovizList/v2` response as TRY. FX-dependent portfolio valuation must remain explicitly unavailable/incomplete until a reliable asset currency is known.

- The 11 portfolio-allocation raw fields (`bb`, `db`, `dot`, `eut`, `fkb`, `kh`, `kks`, `t`, `vm`, `yba`, `ymk`) remain unresolved/unobserved after the existing broad raw-data scan and must not receive guessed labels.
- `girisKomisyonu` extraction and persistence exist, but no non-null live example has been found, so its exact source semantics remain unverified. `cikisKomisyonu` has a verified non-null example and is preserved as the raw TEFAS percentage-point value.
- YAT/EMK management-fee extraction, history persistence and bulk refresh/history sync are implemented. Scheduler/daily-sync/CLI/API integration and BYF/GYF/GSYF management-fee semantics remain deferred.
- `fonProfilDtyGetir` comparison rows are TEFAS performance-comparison series, not the fund's legal benchmark. If an official benchmark or threshold value becomes an MVP requirement, use a separately verified official source such as KAP.
- The old `getFplFonList.tarih` field remains semantically unresolved and must not be treated as fund inception date. The legacy endpoint is not used as a current production source.
- Fund inception/start date and current founder/operator/lifecycle directory metadata require a separately verified current source if they become product requirements.
- Fund-market-share denominator grouping remains unsuitable for a custom derived production metric until the relevant TEFAS grouping semantics are explicitly defined.
- For BYF, observed evidence distinguishes general-info `fiyat` as calculated per-share fund value / NAV from `borsaBultenFiyat` as exchange-market price. Valuation v1 therefore uses persisted `exchange_bulletin_price` for BYF market valuation and does not silently fall back to NAV when that market price is unavailable.
- TEFAS internal type codes observed through `fonTipiGetir` (`YAT -> F`, `EMK -> M`, `BYF -> N`, `GYF -> 1`, `GSYF -> 0`) are provider-internal metadata and are not persisted as user-facing business classifications. Business-level fund-type history continues to use `fonProfilDtyGetir.fonTuru`.

## Remaining backend scope audit

The current backend scope was re-audited after the PortfolioSnapshot storage foundation. Core portfolio tracking, transaction/cash replay, holdings, valuation, TWR/performance, benchmark comparison/catalog/sync, Watchlist, Notes, DataSyncRun, generic AssetPrice storage and PortfolioSnapshot storage are implemented and validated.

Remaining backend work is intentionally separated as follows:

- **BLOCKED - precious metals:** Gold, silver and platinum provider integration remains blocked until the data-integration owner confirms the canonical provider/source, provider identifiers, native currency and raw price unit. Backend must not infer these values. After that contract is confirmed, the remaining backend work is provider adapter/integration, historical and daily AssetPrice synchronization, and precious-metal valuation/P&L support.
- **BACKEND TODO after precious-metal valuation:** PortfolioSnapshot generation remains pending. Snapshots must remain derived dated calculated results and must not replace Transaction, PortfolioCashFlow or dynamic historical valuation as source of truth. Multi-currency TRY/USD/EUR/GBP snapshot calculation semantics must be finalized before generation is wired.
- **CROSS-TEAM / BACKEND TODO:** `AIAnalysis`, `ExpertSource`, `UserExpertSource`, `SentimentPost`, `ReportDocument` and `ReportChunk` remain unresolved planned entities. AI/sentiment/RAG algorithms and their data contracts belong to the AI workstream, but backend ownership, authorization, persistence, API contracts, upload validation and integration boundaries remain backend responsibilities once those contracts are known.
- **OTHER TEAM / operational handoff:** External scheduling of the already implemented one-shot benchmark synchronization belongs to the shared data-integration runtime/environment and requires coordination rather than new benchmark-domain logic.
- **INTENTIONALLY DEFERRED:** Unverified TEFAS metadata/field semantics, management-fee extensions without a concrete requirement, separate API-version module refactoring, and other provider-specific additions remain deferred rather than guessed.
- **FINAL QA TODO:** Measure and document backend test coverage against the project requirement of at least 70% during final backend verification.

No remaining planned entity should be silently dropped. Each unresolved item must eventually be implemented, explicitly assigned to another workstream with a documented backend contract, or intentionally deferred with a recorded reason.

## Local development commands

On Windows PowerShell, prefer the project's venv Python explicitly when activation is unavailable:

```text
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

Git workflow:

- Create a feature branch for each focused implementation slice.
- Do not use `git add .`.
- Stage changed files explicitly.
- Review `git diff --check` and staged changes before commit.
- Push the feature branch and merge through a PR.
- Return local `main` to `origin/main` after merge.

## Current working method

For every backend task:

```text
plan
-> one small step
-> implement
-> run focused tests
-> review result
-> user confirmation
-> next small step
-> full verification
-> explicit stage
-> commit
-> push
-> PR
-> merge
-> update local main
```

Codex usage:

- Do not use Codex for simple PowerShell, Git or test commands.
- Use GPT-5.5 Medium for focused implementation work when Codex materially helps.
- Use GPT-5.5 High only for genuinely critical correctness review.
- Keep Codex prompts short and task-specific.

## TEFAS Read / History API

Status: COMPLETE — 2026-09-07

- Added authenticated public TEFAS daily-data read endpoints:
  - `GET /api/v1/tefas/funds/{fund_code}/latest`
  - `GET /api/v1/tefas/funds/{fund_code}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- Reads only already persisted `TefasFundDailyData`; no provider/network fetch or sync is triggered by these endpoints.
- Fund codes are normalized with `strip().upper()`.
- Latest returns the newest deterministic stored observation.
- History uses an inclusive date range and returns observations ordered by `data_date ASC`.
- Exposed verified stored fields:
  - `data_date`
  - `price`
  - `exchange_bulletin_price`
  - `shares_outstanding`
  - `investor_count`
  - `portfolio_size`
  - fund identity fields (`asset_id`, `fund_code`, `fund_name`, `fund_kind`, `currency`)
- Missing TEFAS fund returns 404.
- Existing fund without latest daily data returns 404.
- Valid empty history range returns `200` with `items=[]` and `total=0`.
- `start_date > end_date` returns 422.
- Decimal precision and nullable values are preserved.
- No migration, provider integration, scheduler, valuation behavior, frontend code, or unrelated refactor was added.
- Focused/related TEFAS verification: 172 passed.
- Full regression suite: 1579 passed.
- Real PostgreSQL + Uvicorn HTTP smoke passed against persisted TEFAS data, including auth, latest, history, Decimal serialization, and invalid-range validation.

## TEFAS Latest Detail Metadata Read API

Status: COMPLETE - 2026-09-07

- Added authenticated public endpoint:
  - `GET /api/v1/tefas/funds/{fund_code}/metadata/latest`
- Reads only the latest already persisted `TefasFundDetailSnapshot`; no TEFAS provider/network fetch, refresh, sync, scheduler action, or database write is triggered.
- Fund codes are normalized with `strip().upper()`.
- Exposes persisted fund identity fields:
  - `asset_id`
  - `fund_code`
  - `fund_name`
  - `fund_kind`
  - `isin`
  - `currency`
- Exposes verified persisted detail metadata:
  - `observed_at`
  - `source_page`
  - `fund_category`
  - `category_rank`
  - `category_fund_count`
  - `market_share_raw`
  - `risk_value`
  - `tefas_status`
  - `transaction_start_time`
  - `transaction_end_time`
  - `entry_commission_raw`
  - `exit_commission_raw`
  - `interest_content`
  - `fund_sale_valor`
  - `fund_redemption_valor`
- `market_share_raw` and commission fields remain raw source values without inferred percentage semantics.
- Valor fields remain source integer values without inferred settlement semantics.
- `risk_value` is the persisted official TEFAS value and is not recalculated.
- Missing TEFAS fund returns 404.
- Existing TEFAS fund without a detail snapshot returns 404.
- Decimal precision and nullable values are preserved.
- No migration, metadata-history endpoint, provider/scraper change, management-fee API, founder field, frontend work, or unrelated refactor was added.
- Focused metadata tests: 12 passed.
- Focused plus related TEFAS regression tests: 155 passed.
- Full regression suite: 1591 passed.
- Real PostgreSQL + Uvicorn HTTP smoke passed against persisted TEFAS detail metadata, including authentication, latest-snapshot selection, Decimal serialization, nullable risk value, and missing-fund behavior.

## TEFAS Current Management Fee Read API

Status: COMPLETE - 2026-09-07

- Added authenticated public endpoint:
  - `GET /api/v1/tefas/funds/{fund_code}/management-fee/current`
- Reads only the currently open persisted `TefasManagementFeeHistory` row.
- Fund codes are normalized with `strip().upper()`.
- Verified public coverage is limited to `YAT` and `EMK`.
- Unsupported fund kinds such as `BYF`, `GYF` and `GSYF` return 404 rather than exposing unverified fee semantics.
- Exposes:
  - `asset_id`
  - `fund_code`
  - `fund_name`
  - `fund_kind`
  - `management_fee_percentage`
  - `first_observed_at`
  - `last_observed_at`
  - `source_endpoint`
  - `source_field_name`
- `management_fee_percentage` preserves the persisted TEFAS percentage-point value exactly; no multiplication or division by 100 is performed.
- Source endpoint and field name are preserved as provenance.
- Missing TEFAS fund returns 404.
- Supported fund without a current fee row returns 404.
- Read endpoint does not trigger TEFAS network fetch, refresh, sync, scheduler action, database write, flush or commit.
- No migration, history API, provider/scraper change, frontend work or unrelated refactor was added.
- Focused tests: 18 passed.
- Related management-fee/TEFAS read regression tests: 128 passed.
- Full regression suite: 1609 passed.
- Real PostgreSQL + Uvicorn HTTP smoke passed using temporary seeded YAT/current-fee data; authentication, Decimal preservation, provenance and missing-fund behavior were verified and all temporary smoke data was cleaned.
