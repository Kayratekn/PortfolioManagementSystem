# TEFAS Database Contract

## Purpose

This document defines the approved MVP database structure for storing stable
asset information and daily raw TEFAS fund data.

This step defines only the database contract. It does not implement database
models, migrations, repositories, upsert logic, API routes or scheduling.

## MVP scope

The first MVP version will support only:

```text
fund_kind = YAT
data_source = TEFAS
asset_type = FUND
```

Other fund kinds such as `EMK`, `BYF`, `GYF` and `GSYF` may be added after the
MVP structure is verified.

## Assets table

Table name:

```text
assets
```

Purpose:

The `assets` table stores stable information about financial assets.

For TEFAS funds:

```text
asset_code = TEFAS fund code
asset_name = TEFAS fund name
asset_type = FUND
fund_kind = YAT
data_source = TEFAS
```

### Fields

| Field | Database type | Nullable | Notes |
|---|---|---:|---|
| `id` | INTEGER | No | Primary key, autoincrement |
| `asset_code` | VARCHAR(20) | No | TEFAS fund code |
| `asset_name` | VARCHAR(255) | No | Full fund name |
| `asset_type` | VARCHAR(30) | No | MVP value: `FUND` |
| `fund_kind` | VARCHAR(10) | Yes | MVP TEFAS value: `YAT` |
| `currency` | VARCHAR(3) | Yes | Must not be guessed from the current TEFAS response |
| `data_source` | VARCHAR(20) | No | MVP value: `TEFAS` |
| `is_active` | BOOLEAN | No | Default: `true` |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | Provided by `TimestampMixin` |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | Provided by `TimestampMixin` |

### Constraints

A fund must be unique within its data source.

```text
UNIQUE (data_source, asset_code)
```

This prevents duplicate TEFAS assets while allowing another data source to use
the same asset code in the future.

### Validation decisions

- `asset_code` must be trimmed and converted to uppercase.
- `asset_name` must have leading and trailing whitespace removed.
- `asset_type` must be uppercase.
- `fund_kind` must be uppercase when provided.
- `data_source` must be uppercase.
- `currency` remains nullable because the verified TEFAS general-information
  response does not expose a reliable currency field.
- Currency must not be guessed or automatically hardcoded as `TRY`.

## TEFAS fund daily data table

Table name:

```text
tefas_fund_daily_data
```

Purpose:

This table stores daily raw TEFAS values that change over time.

### Fields

| Field | Database type | Nullable | Notes |
|---|---|---:|---|
| `id` | INTEGER | No | Primary key, autoincrement |
| `asset_id` | INTEGER | No | Foreign key to `assets.id` |
| `data_date` | DATE | No | Date of the TEFAS data |
| `price` | NUMERIC(20,8) | No | Fund unit price |
| `shares_outstanding` | NUMERIC(25,4) | Yes | Participation-share count |
| `investor_count` | INTEGER | Yes | Number of investors |
| `portfolio_size` | NUMERIC(25,4) | Yes | Total fund portfolio size |
| `exchange_bulletin_price` | NUMERIC(20,8) | Yes | May be null |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | Provided by `TimestampMixin` |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | Provided by `TimestampMixin` |

### Foreign key

```text
asset_id → assets.id
```

Each daily TEFAS record must belong to an existing asset.

### Unique constraint

The same asset must have at most one daily record for a date.

```text
UNIQUE (asset_id, data_date)
```

Future upsert behavior:

```text
Record does not exist → INSERT
Record already exists → UPDATE
```

The upsert implementation is not included in this step.

### Indexing decision

A separate non-unique index on `asset_id + data_date` will not be created.

The unique constraint:

```text
UNIQUE (asset_id, data_date)
```

already creates a PostgreSQL unique B-tree index. This index prevents duplicate
daily records and supports queries that filter one asset's historical data by
`asset_id` and order it by `data_date`.

Creating another index with the same columns would be redundant and would add
unnecessary storage and write overhead.

## TEFAS field mapping

The normalized TEFAS values will be stored as follows:

| Normalized field | Database destination |
|---|---|
| `fund_code` | `assets.asset_code` |
| `fund_name` | `assets.asset_name` |
| `fund_kind` | `assets.fund_kind` |
| `data_date` | `tefas_fund_daily_data.data_date` |
| `price` | `tefas_fund_daily_data.price` |
| `shares_outstanding` | `tefas_fund_daily_data.shares_outstanding` |
| `investor_count` | `tefas_fund_daily_data.investor_count` |
| `portfolio_size` | `tefas_fund_daily_data.portfolio_size` |
| `exchange_bulletin_price` | `tefas_fund_daily_data.exchange_bulletin_price` |

Additional fixed values for TEFAS funds:

```text
assets.asset_type = FUND
assets.data_source = TEFAS
assets.is_active = true
```

## Raw and derived data separation

The following values are raw TEFAS data and belong in the daily table:

- Price
- Share count
- Investor count
- Portfolio size
- Exchange bulletin price

The following values must not be stored as raw TEFAS fields:

- `estimated_money_flow`
- Daily return
- Risk score
- Performance score
- Sentiment score
- Recommendation result

`estimated_money_flow` is a derived analytics metric.

A possible future calculation is:

```text
shares_change =
current_shares_outstanding - previous_shares_outstanding

estimated_money_flow =
shares_change × current_price
```

This calculation is outside the current database-model step.

## Asset allocation decision

Asset-allocation information will not be stored in
`tefas_fund_daily_data`.

It requires a separate TEFAS endpoint and a separate table design.

Possible future table:

```text
fund_asset_allocations
```

The exact fields will be defined only after the portfolio-breakdown endpoint
is live-tested and its raw response fields are verified.

## Daily and historical data strategy

Approved MVP strategy:

### Daily data

Daily general information may be collected for all supported `YAT` funds using
a bulk request.

```text
1 request = YAT + 1 day + multiple funds
```

### Historical data

Long historical backfill should initially focus on:

- Funds contained in user portfolios
- Funds contained in user watchlists

This avoids unnecessary large historical imports during the MVP stage.

## Out-of-scope items

The following items must not be implemented in this database-model step:

- Repository classes
- Database upsert service
- `TefasSyncService`
- API routes
- Daily scheduler
- Fetch-log table
- Retry and rate-limit implementation
- Asset-allocation table
- Analytics calculations
- `estimated_money_flow`
- `EMK`, `BYF`, `GYF` or `GSYF` synchronization
- Frontend integration

## Next implementation steps

After this contract is approved:

1. Create the `Asset` SQLAlchemy model.
2. Create the `TefasFundDailyData` SQLAlchemy model.
3. Add both models to the model registry.
4. Create one Alembic migration.
5. Verify migration upgrade and downgrade.
6. Add model and constraint tests.
7. Review and merge the data-model Pull Request.
8. Implement repository and upsert behavior in a separate branch.