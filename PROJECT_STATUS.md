# PROJECT_STATUS.md

## Project identity

- **Project:** AI-Assisted Portfolio Management System
- **Type:** Browser-based web application
- **Team size:** 4
- **Supervisor:** Prof. Dr. Hakan Altınçay
- **Current backend stage:** Authentication and Portfolio CRUD are stable. TEFAS market-data integration, fund-detail snapshots, portfolio-allocation mapping and short-term evolution metrics are implemented and documented. Official TEFAS fund risk-value extraction is merged. Multi-kind scheduled daily TEFAS synchronization for YAT, EMK, BYF, GYF and GSYF is implemented, verified against TEFAS and PostgreSQL, and merged into main in PR #34. YAT/EMK management-fee source extraction and history persistence are implemented; bulk refresh/sync integration remains deferred.
- **Status updated:** 2026-08-20

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
| Asset/data foundation | Implemented | Asset-linked TEFAS snapshots and related repositories/services/tests exist; nullable Asset-level ISIN metadata persistence/enrichment is implemented |
| Transaction domain | Not started / deferred | Transaction vertical slice has not been the current focus; do not start it before the active TEFAS/data task is closed |
| TEFAS client/integration | Implemented and actively extended | General info, historical price, portfolio breakdown, management-fee source extraction/history persistence for YAT/EMK and fund-detail page data are used through the backend integration/service layer |
| TEFAS daily raw data | Implemented | Core raw fields include fund code/name/date, price, shares outstanding, investor count, portfolio size and BYF exchange bulletin price where available |
| TEFAS scheduled daily sync | Complete / merged | Default scheduled sync runs YAT, EMK, BYF, GYF and GSYF sequentially using fund-kind-level bulk general-info requests; merged in PR #34 |
| TEFAS detail snapshot | Implemented | Includes fund category, 1-year category rank, category fund count, raw market-share value and official TEFAS risk value |
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

POST   /api/v1/portfolios
GET    /api/v1/portfolios
GET    /api/v1/portfolios/{portfolio_id}
PATCH  /api/v1/portfolios/{portfolio_id}
DELETE /api/v1/portfolios/{portfolio_id}
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

The backend detail snapshot currently preserves:

- `fund_category`
- `category_rank`
- `category_fund_count`
- `market_share_raw`
- `risk_value`

`category_rank` / `category_fund_count` were validated against the TEFAS detail-analysis semantics as the current 1-year category ranking and category fund count.

The official TEFAS 1–7 fund risk value is source-confirmed, extracted from exact-matching `profilData["riskDegeri"]`, validated to 1..7 and persisted in fund-detail snapshots. Do not substitute a derived volatility score when the official source value is unavailable.

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
- Current full backend test-suite result: **619 passed**.
- `git diff --check` passed for the current TEFAS management-fee history persistence change.
- Short-term evolution metrics were implemented and merged in PR #29.

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

Work in small controlled increments. The multi-kind scheduled daily TEFAS sync is complete and merged.

1. **Select the next backend/data-contract task**
   - Keep the verified daily `YAT`, `EMK`, `BYF`, `GYF` and `GSYF` bulk sync stable.
   - The data team is handling the five-year historical bulk dataset; do not duplicate that collection work in this backend slice.
   - Review the remaining TEFAS/data-contract gaps and choose the highest-value unresolved backend task.

2. **Before the next implementation**
   - Perform source/code discovery first.
   - Define the smallest correct implementation slice.
   - Run focused tests and the full suite before PR.
   - Do not jump directly into Transaction development without an explicit priority decision.

## Current open decisions / remaining data gaps

Remaining TEFAS/data gaps to consider when selecting the next task:

- TEFAS ISIN extraction and Asset-level opportunistic persistence/enrichment are implemented. A separate whole-universe ISIN backfill strategy is intentionally not part of the daily bulk sync. Stable extraction paths for platform status, transaction times, commissions and interest-content information remain unresolved.
- Exact business mapping across the multiple TEFAS classification structures.
- YAT/EMK management-fee source extraction and history persistence are implemented; scheduler/daily-sync/bulk-refresh integration and BYF/GYF/GSYF management-fee semantics remain intentionally deferred.
- Official benchmark field vs comparison-series semantics.
- Exact meaning of `getFplFonList.tarih`.
- Settlement/value-date source strategy if TEFAS extraction is not stable.
- Cross-endpoint authoritative price semantics for BYF and any other affected fund types.

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
