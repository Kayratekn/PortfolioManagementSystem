# TEFAS Fetch Log Database Contract

## Purpose

This document defines the MVP database structure for recording TEFAS
synchronization attempts.

A fetch-log record represents one synchronization execution, including its
requested scope, result counters, completion status and possible error.

This contract defines only the fetch-log database structure and the future
transaction strategy.

It does not yet implement:

- SQLAlchemy model
- Alembic migration
- Repository
- Synchronization logging
- Scheduler
- API routes

## Table

Table name:

```text
tefas_fetch_logs
```

## Fields

| Field | Database type | Nullable | Notes |
|---|---|---:|---|
| `id` | INTEGER | No | Primary key, autoincrement |
| `data_source` | VARCHAR(20) | No | MVP value: `TEFAS` |
| `fund_kind` | VARCHAR(10) | No | MVP value: `YAT` |
| `fund_code` | VARCHAR(20) | Yes | Null for bulk requests; fund code for single-fund requests |
| `start_date` | DATE | No | Requested data-range start date |
| `end_date` | DATE | No | Requested data-range end date |
| `status` | VARCHAR(20) | No | `RUNNING`, `SUCCESS` or `FAILED` |
| `fetched_rows` | INTEGER | No | Number of normalized TEFAS rows returned |
| `assets_created` | INTEGER | No | Number of new asset records |
| `assets_updated` | INTEGER | No | Number of changed asset records |
| `daily_rows_created` | INTEGER | No | Number of new daily-data records |
| `daily_rows_updated` | INTEGER | No | Number of changed daily-data records |
| `error_message` | TEXT | Yes | Original failure message when status is `FAILED` |
| `started_at` | TIMESTAMP WITH TIME ZONE | No | Time at which synchronization started |
| `completed_at` | TIMESTAMP WITH TIME ZONE | Yes | Time at which synchronization finished |
| `created_at` | TIMESTAMP WITH TIME ZONE | No | Provided by `TimestampMixin` |
| `updated_at` | TIMESTAMP WITH TIME ZONE | No | Provided by `TimestampMixin` |

## Default values

The initial status must be:

```text
RUNNING
```

All result counters must initially be:

```text
0
```

Fields with zero defaults:

```text
fetched_rows
assets_created
assets_updated
daily_rows_created
daily_rows_updated
```

The initial values represent a synchronization that has started but has not
yet produced a result.

## Status values

Allowed status values:

```text
RUNNING
SUCCESS
FAILED
```

Database check constraint:

```text
status IN ('RUNNING', 'SUCCESS', 'FAILED')
```

Recommended constraint name:

```text
ck_tefas_fetch_logs_status_allowed
```

### RUNNING

The log was created, but synchronization has not finished.

Expected state:

```text
status = RUNNING
completed_at = NULL
error_message = NULL
```

### SUCCESS

The synchronization completed and its database transaction was committed.

Expected state:

```text
status = SUCCESS
completed_at IS NOT NULL
error_message = NULL
```

Result counters contain the values returned by `TefasSyncResult`.

### FAILED

The synchronization failed and its main database transaction was rolled back.

Expected state:

```text
status = FAILED
completed_at IS NOT NULL
error_message IS NOT NULL
```

Counters may remain zero when the operation fails before a complete result is
available.

## Date constraint

The requested start date must not be later than the end date.

Database check constraint:

```text
start_date <= end_date
```

Recommended constraint name:

```text
ck_tefas_fetch_logs_date_range_valid
```

## Counter constraints

All counters must be greater than or equal to zero.

Database checks:

```text
fetched_rows >= 0
assets_created >= 0
assets_updated >= 0
daily_rows_created >= 0
daily_rows_updated >= 0
```

Recommended constraint names:

```text
ck_tefas_fetch_logs_fetched_rows_nonnegative
ck_tefas_fetch_logs_assets_created_nonnegative
ck_tefas_fetch_logs_assets_updated_nonnegative
ck_tefas_fetch_logs_daily_rows_created_nonnegative
ck_tefas_fetch_logs_daily_rows_updated_nonnegative
```

## Index

Fetch logs will commonly be queried by data source, fund kind and execution
time.

Recommended index:

```text
INDEX (data_source, fund_kind, started_at)
```

Recommended index name:

```text
ix_tefas_fetch_logs_source_kind_started_at
```

## Uniqueness decision

The table must not have a unique constraint for request date, fund kind or fund
code.

The same synchronization may legitimately be executed multiple times.

Example:

```text
YAT + AAL + 2026-04-24
```

Running this request twice must create two separate fetch-log records because
they represent two separate executions.

## Normalization decisions

Before storing request information:

- `data_source` must be uppercase.
- `fund_kind` must be uppercase.
- `fund_code` must be trimmed and uppercase when provided.
- Empty `fund_code` values should be stored as null.
- Error messages must preserve the original exception message.
- Missing result values must not be fabricated.

Normalization belongs to the service layer, not the database model.

## Transaction strategy

Fetch logging must remain observable even when the main TEFAS synchronization
transaction fails.

The future implementation must therefore use separate sessions:

```text
Sync Session
- Asset insert/update
- Daily-data insert/update
- Main synchronization transaction

Log Session
- RUNNING log creation
- SUCCESS or FAILED log update
```

The fetch-log record must not be part of the same transaction as the asset and
daily-data upserts.

Otherwise, a rollback of the synchronization transaction would also delete the
failure log.

## Future execution lifecycle

### Start

Before processing TEFAS rows:

```text
1. Open log session.
2. Create one fetch-log row.
3. Set status to RUNNING.
4. Set started_at.
5. Commit the log session.
```

### Success

After the main synchronization transaction commits:

```text
1. Set status to SUCCESS.
2. Copy TefasSyncResult counters.
3. Set completed_at.
4. Keep error_message null.
5. Commit the log session.
```

### Failure

When synchronization raises an exception:

```text
1. Roll back the main sync session.
2. Set log status to FAILED.
3. Store the original exception message.
4. Set completed_at.
5. Commit the log session.
6. Re-raise the original exception.
```

Logging must not suppress or replace the original synchronization error.

## Example successful log

```text
data_source: TEFAS
fund_kind: YAT
fund_code: AAL
start_date: 2026-04-24
end_date: 2026-04-24
status: SUCCESS
fetched_rows: 1
assets_created: 1
assets_updated: 0
daily_rows_created: 1
daily_rows_updated: 0
error_message: NULL
```

## Example failed log

```text
data_source: TEFAS
fund_kind: YAT
fund_code: NULL
start_date: 2026-04-24
end_date: 2026-04-24
status: FAILED
fetched_rows: 0
assets_created: 0
assets_updated: 0
daily_rows_created: 0
daily_rows_updated: 0
error_message: TEFAS request failed: request timed out
```

## Out-of-scope items

This database-model step must not implement:

- Fetch-log repository
- Fetch-log service
- Changes to `TefasSyncService`
- Separate log-session creation
- Scheduler
- API route
- Email or notification behavior
- Log cleanup or retention policy
- Asset-allocation logging
- Other external data-source logs

## Next implementation steps

After this contract is approved:

1. Create the `TefasFetchLog` SQLAlchemy model.
2. Register the model in SQLAlchemy metadata and Alembic.
3. Create one Alembic migration.
4. Test migration upgrade and downgrade.
5. Add model and constraint tests.
6. Commit the database-model foundation.
7. Implement fetch-log repository and lifecycle behavior separately.