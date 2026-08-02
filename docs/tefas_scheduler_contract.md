# TEFAS Scheduler Contract

## Purpose

This document defines the MVP scheduling policy and the portable wrapper
script that will trigger the existing TEFAS daily synchronization command.

The scheduler must reuse the already tested synchronization flow:

```text
scheduled wrapper
→ sync_tefas_daily.py
→ TEFAS request
→ database upsert
→ SUCCESS or FAILED fetch log
```

The scheduler must not duplicate TEFAS request, database, retry or fetch-log
logic.

## Scope

This MVP consists of two separate parts:

1. A portable Python wrapper stored in the GitHub repository.
2. An operating-system scheduler configured on the deployment computer or
   server.

The GitHub repository contains the portable wrapper and documentation.

The actual execution hour and retry schedule belong to the deployment
environment and are not hardcoded into Python.

## Responsibility separation

### Python wrapper

The Python wrapper decides:

- Which data date should be requested.
- Which fund kind should be forwarded.
- Whether all funds or one fund code should be requested.
- Which arguments should be passed to the existing daily sync command.
- Which exit code should be returned to the operating-system scheduler.

### Operating-system scheduler

The operating-system scheduler decides:

- Execution days.
- Execution time.
- Time zone of the scheduler host.
- Retry interval.
- Retry count.
- Whether a missed execution should run when the host becomes available.

### Database destination

The destination database is determined only by:

```text
DATABASE_URL
```

The scheduler must not contain a database address, username, password or
secret.

Examples:

```text
Local DATABASE_URL
→ data is stored in the local PostgreSQL database

Shared-server DATABASE_URL
→ data is stored in the shared PostgreSQL database
```

## MVP deployment defaults

Recommended initial deployment settings:

```text
Execution days: Monday to Friday
Execution time: 09:00
Scheduler host time zone: Europe/Istanbul
Retry interval: 30 minutes
Retry count after the first attempt: 3
Run missed task when the host becomes available: Yes
```

These values are deployment defaults, not permanent application rules.

They may later be changed without modifying the TEFAS synchronization
services.

## Default data policy

The default wrapper behavior is:

```text
Fund kind: YAT
Fund code: None
Date mode: previous-business-day
```

A null fund code means all funds belonging to the selected fund kind.

Examples:

```text
Monday execution
→ request Friday data

Tuesday execution
→ request Monday data

Wednesday execution
→ request Tuesday data
```

## Scheduled wrapper

Create:

```text
scripts/sync_tefas_scheduled.py
```

The wrapper must call the existing Python entry point from:

```text
scripts/sync_tefas_daily.py
```

It must not reimplement:

- TEFAS HTTP requests
- Retry and timeout behavior
- Row normalization
- Asset upsert behavior
- Daily-data upsert behavior
- Database transaction handling
- Fetch-log lifecycle handling

## Command-line interface

The scheduled wrapper must support:

```text
--kind
--fund-code
--date-mode
--reference-date
```

### --kind

Allowed MVP value:

```text
YAT
```

Default:

```text
YAT
```

The design must allow more fund kinds to be added later.

### --fund-code

Optional value.

Examples:

```text
--fund-code AAL
```

When omitted:

```text
fund_code = None
```

This means all funds in the selected fund kind.

The wrapper should forward the value to the existing daily sync command.

### --date-mode

Allowed values:

```text
previous-business-day
today
```

Default:

```text
previous-business-day
```

#### previous-business-day

Select the latest weekday before the reference date.

Weekend dates must be skipped.

Examples:

```text
Reference date: Monday
Selected date: Previous Friday

Reference date: Sunday
Selected date: Previous Friday

Reference date: Saturday
Selected date: Previous Friday

Reference date: Wednesday
Selected date: Tuesday
```

This MVP business-day calculation skips only Saturday and Sunday.

It does not yet contain an official Turkish holiday calendar.

#### today

Select the reference date without subtracting a day.

This option allows the data team to change the policy later without modifying
the wrapper implementation.

### --reference-date

Optional ISO date:

```text
YYYY-MM-DD
```

Example:

```text
--reference-date 2026-08-03
```

When supplied, this value is used to calculate the requested data date.

When omitted, the wrapper uses:

```python
date.today()
```

This argument exists primarily for:

- Deterministic automated tests
- Manual verification
- Controlled reruns
- Debugging date calculations

## Business-day calculation

Create a focused function such as:

```python
previous_business_day(reference_date: date) -> date
```

Required behavior:

1. Subtract one calendar day.
2. Continue subtracting while the date is Saturday or Sunday.
3. Return the resulting weekday.

The function must not access the database or network.

## Daily sync invocation

After calculating the target date, the wrapper must invoke the existing daily
sync entry point with equivalent arguments.

Example logical call:

```text
sync_tefas_daily.main(
    [
        "--kind",
        "YAT",
        "--date",
        "2026-07-31",
    ]
)
```

When a fund code is provided:

```text
sync_tefas_daily.main(
    [
        "--kind",
        "YAT",
        "--date",
        "2026-07-31",
        "--fund-code",
        "AAL",
    ]
)
```

The wrapper must return the exact exit code returned by the daily sync command.

Expected exit codes:

```text
0 → synchronization and fetch-log update succeeded
1 → synchronization or fetch-log operation failed
2 → invalid command-line arguments
```

## Output

Before calling the daily sync command, the wrapper should print a concise
schedule summary:

```text
TEFAS scheduled sync
reference date: 2026-08-03
selected data date: 2026-07-31
date mode: previous-business-day
fund kind: YAT
fund code: None
```

The existing daily sync command remains responsible for printing:

- Synchronization result counters
- Successful completion output
- Failure output

## Windows Task Scheduler command

The deployment computer may execute the wrapper using its virtual-environment
Python interpreter.

Example program:

```text
C:\path\to\Portfolio Management System\venv\Scripts\python.exe
```

Example arguments:

```text
scripts\sync_tefas_scheduled.py --kind YAT --date-mode previous-business-day
```

Example start-in directory:

```text
C:\path\to\Portfolio Management System
```

The exact path depends on the deployment computer.

Paths must not be hardcoded into the repository.

## Security rules

The scheduled task must not contain:

- Database passwords
- JWT secrets
- TEFAS credentials
- Personal PostgreSQL credentials
- A copied `.env` file inside command arguments

Configuration must continue to come from the deployment environment's local
`.env` file.

The real `.env` file must remain outside Git tracking.

## Portability

The Python wrapper must not depend on Windows Task Scheduler APIs.

This allows the same wrapper to be triggered later by:

```text
Windows Task Scheduler
Linux cron
Docker scheduled job
Cloud scheduler
CI/CD scheduled workflow
```

Only the external scheduling configuration changes.

The synchronization code remains the same.

## Testing requirements

Create focused tests for:

1. Tuesday selects Monday.
2. Monday selects Friday.
3. Saturday selects Friday.
4. Sunday selects Friday.
5. `today` mode keeps the reference date.
6. Default fund kind is `YAT`.
7. Optional fund code is forwarded.
8. Missing fund code is omitted from daily-sync arguments.
9. The exact selected date is forwarded.
10. The wrapper returns the exact daily-sync exit code.
11. Invalid reference dates produce argument parsing failure.
12. Invalid date modes produce argument parsing failure.

Tests must:

- Use no real network.
- Use no real database.
- Not create Windows scheduled tasks.
- Patch the existing daily sync entry point.
- Use explicit reference dates for deterministic results.

## Manual verification

A safe local verification may use a known historical date and one fund:

```powershell
.\venv\Scripts\python.exe scripts\sync_tefas_scheduled.py `
  --kind YAT `
  --fund-code AAL `
  --date-mode previous-business-day `
  --reference-date 2026-04-27
```

Expected selected data date:

```text
2026-04-24
```

This manual command may write to the database configured by the local
`DATABASE_URL`.

No permanent Windows scheduled task is required during repository
development.

## Out-of-scope items

This MVP step does not implement:

- Official Turkish holiday calculations
- Database-stored scheduler configuration
- Scheduler administration API
- Scheduler settings in the frontend
- Email notifications
- Slack notifications
- Automatic cleanup of fetch logs
- Deployment to a production server
- Sharing personal `.env` files
- Hardcoded database connection information
- Additional TEFAS fund kinds
- Automatic historical backfill

## Future changes

The data team may later change:

- Execution time
- Execution days
- Requested date mode
- Retry count
- Retry interval
- Fund kinds
- Holiday behavior

These changes should not require modifications to the existing TEFAS client,
upsert services or fetch-log lifecycle.

## Next implementation steps

1. Create `scripts/sync_tefas_scheduled.py`.
2. Add deterministic date-calculation tests.
3. Verify forwarding to `sync_tefas_daily.main`.
4. Run the complete automated test suite.
5. Perform one controlled local manual test.
6. Document the external Task Scheduler setup.
7. Commit and open a pull request.