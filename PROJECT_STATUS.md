# PROJECT_STATUS.md

## Project identity

- **Project:** AI-Assisted Portfolio Management System
- **Type:** Browser-based web application
- **Team size:** 4
- **Supervisor:** Prof. Dr. Hakan Altınçay
- **Current backend stage:** Authentication, Portfolio CRUD, Transaction and Holdings foundations are stable. TEFAS valuation-price and TCMB FX foundations are implemented and validated. Portfolio Valuation Aggregation v1 is implemented and validated, exposed through a stable authenticated API contract: `GET /api/v1/portfolios/{portfolio_id}/valuation?valuation_date=YYYY-MM-DD`, and Portfolio Weights v1 is now implemented and validated through that existing endpoint. `valuation_date` is required. Each valuation item exposes `weight: Decimal | None`; weights are `0..1` ratios based on portfolio-currency `market_value`, complete portfolios calculate exact Decimal weights, and incomplete portfolios expose null weight for every item without partial-subset weights. The API preserves `COMPLETE`/`INCOMPLETE` status, unavailable reason, price provenance and FX provenance. Decimal monetary values and weights remain Decimal internally and serialize safely through the Pydantic/FastAPI response contract. No new endpoint or migration was introduced for weights. Cost Basis v1 is now implemented and validated through the public authenticated API `GET /api/v1/portfolios/{portfolio_id}/cost-basis?as_of_date=YYYY-MM-DD`, using the documented Moving Weighted Average Cost methodology. Unrealized P/L v1 is now implemented and validated through the public authenticated API `GET /api/v1/portfolios/{portfolio_id}/unrealized-pl?as_of_date=YYYY-MM-DD`, using the previously documented native-currency-only methodology and completed service implementation. `as_of_date` is required, the endpoint is authenticated and ownership-protected, and the response remains native-currency only. Unrealized P/L v1 has no portfolio-base-currency P/L, FX-adjusted cost basis, portfolio-level Unrealized P/L total, Unrealized P/L percentage, Realized P/L, migration, table or schema change. Cost Basis remains transaction-based, derives native-currency cost basis through deterministic Decimal replay, requires `as_of_date`, preserves ownership isolation, serializes Decimal values as JSON strings, and does not add a mutable cost-basis/holdings table, migration, portfolio-level summed cost-basis total, realized P/L implementation or FX conversion of cost basis/P&L. Public Realized P/L v1 API is now implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/realized-pl?as_of_date=YYYY-MM-DD`. `as_of_date` is required, authentication is required, and portfolio ownership isolation returns 404 with `Portfolio not found.`. The response exposes `portfolio_id`, `as_of_date`, `status` and `items`; each item exposes `asset_id`, `asset_code`, `asset_name`, `asset_currency`, `status`, `unavailable_reason`, `sold_quantity`, `realized_proceeds`, `realized_cost_basis` and `native_realized_pl`. Decimal financial values remain Decimal internally and serialize as JSON strings. Realized P/L remains transaction-sourced, cumulative through one `as_of_date`, native-currency only, and uses SELL activity on or before `as_of_date` as its asset universe so fully sold assets remain included. Missing or blank `Asset.currency` produces an `UNAVAILABLE` item that preserves `sold_quantity` while exposing null monetary outputs. Cost Basis and Realized P/L continue to share one canonical Moving Weighted Average Cost replay helper. Transaction History public API is now implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/transactions` with authentication, ownership isolation, `skip`/`limit` pagination, deterministic `transaction_date ASC, id ASC` ordering and `TransactionListResponse`. Asset Catalog public API is now implemented and validated at `GET /api/v1/assets` with authentication, active-asset-only scope, `skip`/`limit` pagination, optional case-insensitive search across `asset_code` and `asset_name`, deterministic `asset_code ASC, id ASC` ordering and nullable `isin`/`currency` preservation. No market price or freshness metadata is exposed by the Asset Catalog API. No portfolio-level Realized P/L total, FX/base-currency conversion, market-price dependency, percentage/return, from/to period behavior, fees/taxes, migration or schema change was added.
- **Status updated:** 2026-09-02

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
| Transaction domain | Implemented / validated (public create + history API) | PostgreSQL `transactions` table foundation was introduced via migration `20260825_0012`; migration `20260902_0014` adds nullable `transaction_currency` (`TRY`/`USD`/`EUR`/`GBP`) for legacy-safe currency snapshots. New API-created BUY/SELL transactions require `transaction_currency`, normalize it at the request boundary, persist it, and expose it through create/history responses; legacy rows with null currency remain readable. Transactions for the same portfolio + asset must use the same non-null transaction currency. BUY and SELL creation both acquire the owned portfolio row with PostgreSQL `FOR UPDATE` before currency-consistency validation, historical SELL quantity validation and insert/commit, preventing concurrent first-write mixed-currency history through the normal service path. Existing Decimal / NUMERIC precision, portfolio ownership isolation, asset existence validation, deterministic `transaction_date ASC, id ASC` history ordering and `TransactionListResponse` behavior remain intact. No `Asset.currency` inference/backfill was introduced. Frontend integration is not complete. |
| Holdings domain | Implemented / validated (foundation) | Holdings are derived from Transaction history without duplicated persisted holdings truth. `GET /api/v1/portfolios/{portfolio_id}/holdings` returns asset metadata and Decimal quantity for positive current holdings only; fully sold assets are omitted and ownership isolation is enforced. Service-level valuation aggregation is implemented; portfolio weights are implemented; Cost Basis v1 service and Unrealized P/L v1 service use positive historical/as-of holdings from transactions. Realized P/L v1 public API is implemented and validated. |
| Cost Basis v1 | Implemented / validated (public API contract) | `GET /api/v1/portfolios/{portfolio_id}/cost-basis?as_of_date=YYYY-MM-DD` is implemented as a public authenticated API. `as_of_date` is required; missing or invalid dates return 422, authentication is required and unauthenticated requests return 401, and portfolio ownership isolation returns 404 with `Portfolio not found.`. The response exposes `portfolio_id`, `as_of_date`, `status` and `items`; each item exposes `asset_id`, `asset_code`, `asset_name`, `asset_currency`, `status`, `unavailable_reason`, `quantity`, `total_cost_basis` and `average_cost_per_unit`. Decimal values remain Decimal internally and serialize as JSON strings. No portfolio-level `total_cost_basis` is exposed because native asset currencies can differ. Moving Weighted Average Cost service algorithm was not changed: transactions remain the source of truth, cost basis is replayed by `transaction_date ASC`, then `id ASC`, historical/as-of calculation uses `transaction_date <= as_of_date`, future transactions do not affect historical Cost Basis, fully sold assets remain omitted, missing `Asset.currency` remains `UNAVAILABLE` and makes the result `INCOMPLETE`, and manual/non-TEFAS assets with known currency are supported. No mutable cost-basis/holdings table, migration, realized P/L or FX conversion of cost basis/P&L was added in the Cost Basis slice. |
| Unrealized P/L v1 | Implemented / validated (public API contract) | Unrealized P/L v1 methodology was documented previously, the service implementation is complete, and the public API is implemented at `GET /api/v1/portfolios/{portfolio_id}/unrealized-pl?as_of_date=YYYY-MM-DD`. `as_of_date` is required, and the endpoint is authenticated and ownership-protected. The response is native-currency only and uses the existing `UnrealizedPlService`, composed from `CostBasisService`, `TransactionRepository` and `TefasValuationPriceService`; it does not use `PortfolioValuationService` or `FxConversionService`. Public response items include asset identity/currency, `status`, `unavailable_reason`, `quantity`, `total_cost_basis`, `average_cost_per_unit`, selected price/provenance, `price_freshness`, `native_market_value` and `native_unrealized_pl`. Availability and financial semantics remain those documented in `AGENTS (2).md`: no portfolio-base-currency Unrealized P/L, FX-adjusted cost basis, portfolio-level Unrealized P/L total, Unrealized P/L percentage, Realized P/L, migrations or schema changes. |
| Realized P/L v1 | Implemented / validated (public API contract) | Public Realized P/L v1 API is implemented and validated at `GET /api/v1/portfolios/{portfolio_id}/realized-pl?as_of_date=YYYY-MM-DD`. `as_of_date` is required, authentication is required, and portfolio ownership isolation returns 404 with `Portfolio not found.`. The response exposes `portfolio_id`, `as_of_date`, `status` and `items`; each item exposes `asset_id`, `asset_code`, `asset_name`, `asset_currency`, `status`, `unavailable_reason`, `sold_quantity`, `realized_proceeds`, `realized_cost_basis` and `native_realized_pl`. Decimal financial values remain Decimal internally and serialize as JSON strings. Fully sold assets remain included because the Realized P/L universe is SELL activity on or before `as_of_date`. Missing or blank `Asset.currency` remains `UNAVAILABLE`, preserves `sold_quantity`, and exposes null monetary outputs. Realized P/L remains cumulative through `as_of_date` and native-currency only. No portfolio-level Realized P/L total, FX/base-currency conversion, market-price dependency, percentage/return, from/to period behavior, fees/taxes, migration or schema change was added. `RealizedPlService` and the shared MWAC replay were unchanged during this API slice. |
| Exchange-rate / TCMB foundation | Implemented / validated | PostgreSQL `exchange_rates` via migration `20260826_0013`; TCMB current/historical XML client preserves effective rate date and Decimal `ForexBuying`/`ForexSelling`; idempotent TCMB sync persists USD/TRY, EUR/TRY and GBP/TRY observations. |
| Valuation market-data foundation | Implemented / validated (v1) | YAT/EMK/GYF/GSYF valuation uses TEFAS NAV `price`; BYF uses `exchange_bulletin_price` as exchange-market price with no silent NAV fallback. Price and FX lookups use latest-on-or-before semantics. FX conversion uses Decimal TCMB midpoint reference rates for identity/direct/inverse/cross conversions; foreign-to-foreign cross legs require the same effective date. |
| Market Data Freshness | Implemented / validated (focused API contract) | Shared freshness contract is implemented for market-data observations with `requested_date`, `effective_date`, `age_days` and `status`. Status values are `CURRENT`, `STALE`, `UNAVAILABLE` and `NOT_APPLICABLE`. `CURRENT` means `effective_date == requested_date`; `STALE` means an older latest-on-or-before market observation was used; `UNAVAILABLE` means required market data is missing; `NOT_APPLICABLE` is used for identity FX. No arbitrary stale-day threshold exists. Portfolio Valuation exposes `price_freshness` and `fx_freshness`; Unrealized P/L exposes `price_freshness`. Existing price/FX selection, Decimal financial calculations, `COMPLETE`/`INCOMPLETE` behavior, ownership and `unavailable_reason` semantics were not changed. TEFAS metrics/allocation APIs were not changed, and no migration/model/table/provider changes were introduced. No PostgreSQL-specific smoke was required because DB/query behavior did not change. |
| Portfolio valuation aggregation | Implemented / validated (v1 API + weights) | As-of holdings are derived from transactions using `transaction_date <= valuation_date` for positive holdings only, then composed with the TEFAS price selector and FX conversion using Decimal arithmetic. Results expose `COMPLETE` / `INCOMPLETE` status, preserve price and FX provenance, keep `total_market_value` as `None` when any positive holding is unavailable, and expose item `weight: Decimal | None`, `price_freshness` and `fx_freshness`. `GET /api/v1/portfolios/{portfolio_id}/valuation` exposes valuation through an authenticated Pydantic response contract with required `valuation_date`, preserved ownership isolation and unavailable positive holdings visible in `items`; complete portfolios calculate exact `0..1` Decimal weights from portfolio-currency `market_value`, while incomplete portfolios expose null weights for every item with no partial-subset weights. |
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

Historical Performance discovery resolved the external-flow direction before implementation: BUY/SELL remain investment transactions, while user-entered DEPOSIT/WITHDRAWAL will represent external portfolio cash flows for performance calculations. `transaction_currency` is now persisted as a prerequisite for future cash replay. The next focused backend slice is **PortfolioCashFlow DEPOSIT/WITHDRAWAL foundation**. After that foundation is stable, continue in controlled slices with derived per-currency cash replay, historical assets + cash valuation, TWR performance, and then benchmark comparison. Benchmark provider/source implementation remains a later focused slice and must still use verified provider contracts rather than guessed mappings.

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
