# TEFAS Scheduler Setup Guide

## Purpose

This document explains how to run the portable TEFAS scheduler wrapper
automatically on a Windows deployment computer.

The repository does not automatically create an operating-system task.

The scheduled task must be configured separately on the computer or server
that will perform data collection.

The execution flow is:

```text
Windows Task Scheduler
-> scripts/sync_tefas_scheduled.py
-> scripts/sync_tefas_daily.py
-> TEFAS
-> PostgreSQL
-> SUCCESS or FAILED fetch log
```

## Important deployment rule

The destination database is controlled by the local:

```text
DATABASE_URL
```

Examples:

```text
DATABASE_URL points to localhost
-> data is stored on that computer

DATABASE_URL points to a shared PostgreSQL server
-> data is stored in the shared database
```

The scheduler does not contain database credentials.

Do not copy another team member's personal `.env` file.

Each deployment environment must create its own `.env` file from:

```text
.env.example
```

## Recommended ownership

The scheduled task should eventually run on:

```text
A shared deployment computer
or
A shared server
```

It should not permanently depend on a team member's personal development
computer.

During development, the command may be tested manually on a local computer.

## Prerequisites

The deployment computer must have:

- Git
- Python
- PostgreSQL access
- The cloned project repository
- A project virtual environment
- Installed Python dependencies
- A local `.env` file
- Database migrations applied
- Network access to TEFAS
- Network access to the configured PostgreSQL database

## Repository setup

Clone the repository:

```powershell
git clone https://github.com/Kayratekn/PortfolioManagementSystem.git
cd PortfolioManagementSystem
```

Create a virtual environment:

```powershell
python -m venv venv
```

Install dependencies without requiring PowerShell activation:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Update the local `.env` file with the deployment environment's own settings.

Do not commit `.env`.

Apply database migrations:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

Run all automated tests:

```powershell
.\venv\Scripts\python.exe -m pytest
```

## Environment configuration

The `.env` file must include a valid database connection.

Example structure:

```env
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/ai_portfolio
```

The real username, password and host belong to the deployment environment.

TEFAS settings may use the repository defaults:

```env
TEFAS_BASE_URL=https://www.tefas.gov.tr
TEFAS_TIMEOUT_SECONDS=30
TEFAS_MAX_RETRIES=3
TEFAS_RETRY_WAIT_SECONDS=10
```

## Two retry levels

The system has two different retry levels.

### HTTP request retries

Configured through:

```text
TEFAS_MAX_RETRIES
TEFAS_RETRY_WAIT_SECONDS
```

These retries happen inside one script execution when a TEFAS request fails.

### Scheduled-task retries

Configured in Windows Task Scheduler.

These retries start the complete script again after it exits unsuccessfully.

Recommended MVP settings:

```text
Restart interval: 30 minutes
Restart attempts: 3
```

## Manual verification before scheduling

Before creating a Windows scheduled task, test the wrapper manually.

Example:

```powershell
.\venv\Scripts\python.exe scripts\sync_tefas_scheduled.py `
  --kind YAT `
  --fund-code AAL `
  --date-mode previous-business-day `
  --reference-date 2026-04-27
```

Expected selected date:

```text
2026-04-24
```

A successful execution should print:

```text
TEFAS scheduled sync
TEFAS sync completed successfully
```

It should also create a `SUCCESS` record in:

```text
tefas_fetch_logs
```

## Recommended production command

Program:

```text
FULL_PROJECT_PATH\venv\Scripts\python.exe
```

Arguments:

```text
scripts\sync_tefas_scheduled.py --kind YAT --date-mode previous-business-day
```

Start-in directory:

```text
FULL_PROJECT_PATH
```

Example only:

```text
C:\Projects\PortfolioManagementSystem
```

Do not copy another computer's project path.

## Recommended schedule

Initial MVP deployment policy:

```text
Days: Monday, Tuesday, Wednesday, Thursday, Friday
Time: 09:00
Date mode: previous-business-day
Fund kind: YAT
Fund code: omitted
Retry interval: 30 minutes
Retry attempts: 3
Run missed task when available: enabled
Parallel execution: disabled
```

These are configurable deployment defaults.

The data team may later change them.

## Windows Task Scheduler GUI setup

### 1. Open Task Scheduler

Open the Windows Start menu and search for:

```text
Task Scheduler
```

Choose:

```text
Create Task
```

Do not use `Create Basic Task` because advanced retry and missed-run settings
are needed.

### 2. General tab

Suggested task name:

```text
PortfolioManagement-TEFAS-DailySync
```

Suggested description:

```text
Fetches daily TEFAS YAT data and stores the result in the configured
PostgreSQL database.
```

The account running the task must be able to:

- Read the project directory
- Run the virtual-environment Python executable
- Read the local `.env` file
- Connect to TEFAS
- Connect to PostgreSQL

The task does not require personal database credentials in its command-line
arguments.

### 3. Triggers tab

Create a new trigger.

Use:

```text
Begin the task: On a schedule
Schedule type: Weekly
Weeks interval: 1
Days:
- Monday
- Tuesday
- Wednesday
- Thursday
- Friday
Start time: 09:00
Enabled: Yes
```

The actual time can be changed later without modifying Python code.

### 4. Actions tab

Create a new action.

Action:

```text
Start a program
```

Program/script:

```text
FULL_PROJECT_PATH\venv\Scripts\python.exe
```

Add arguments:

```text
scripts\sync_tefas_scheduled.py --kind YAT --date-mode previous-business-day
```

Start in:

```text
FULL_PROJECT_PATH
```

The `Start in` value is important because the project uses relative paths such
as:

```text
scripts\sync_tefas_scheduled.py
```

Do not include quotation marks around the Start-in directory in the GUI field.

### 5. Conditions tab

The task requires network access.

The deployment computer must be able to reach:

- TEFAS
- The configured PostgreSQL server

Laptop-specific power settings should be chosen according to the deployment
environment.

A shared server is preferred over a personal laptop.

### 6. Settings tab

Enable:

```text
Allow task to be run on demand
Run task as soon as possible after a scheduled start is missed
```

Configure failure restart:

```text
Restart every: 30 minutes
Attempt to restart up to: 3 times
```

For parallel execution select:

```text
Do not start a new instance
```

This prevents two bulk TEFAS synchronization executions from running at the
same time.

Optionally set an execution time limit suitable for the deployment
environment.

## Optional PowerShell registration template

This template creates the task on the computer where it is executed.

It is not executed automatically by the repository.

Replace only the project path:

```powershell
$projectRoot = "C:\CHANGE\THIS\PortfolioManagementSystem"
$pythonPath = Join-Path $projectRoot "venv\Scripts\python.exe"

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "scripts\sync_tefas_scheduled.py --kind YAT --date-mode previous-business-day" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -WeeksInterval 1 `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At 9:00AM

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName "PortfolioManagement-TEFAS-DailySync" `
    -Description "Runs the scheduled TEFAS YAT synchronization." `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings
```

This command registers a task only on the computer where the command is run.

It does not create a task for other developers or GitHub users.

## Verification after registration

Open Task Scheduler and locate:

```text
PortfolioManagement-TEFAS-DailySync
```

Run the task manually once.

Verify:

1. The task finishes.
2. The Last Run Result indicates success.
3. A new row exists in `tefas_fetch_logs`.
4. The row has either:
   - `SUCCESS`, or
   - `FAILED` with an error message.
5. No duplicate asset or daily-data row is created.
6. Both `started_at` and `completed_at` are populated.

## Checking the latest fetch log

From the project root:

```powershell
@'
from sqlalchemy import select

from src.config.database import SessionLocal
from src.model.tefas_fetch_log import TefasFetchLog

session = SessionLocal()

try:
    fetch_log = session.scalar(
        select(TefasFetchLog)
        .order_by(TefasFetchLog.id.desc())
        .limit(1)
    )

    if fetch_log is None:
        print("FETCH LOG NOT FOUND")
    else:
        print("id:", fetch_log.id)
        print("status:", fetch_log.status)
        print("fund_kind:", fetch_log.fund_kind)
        print("fund_code:", fetch_log.fund_code)
        print("start_date:", fetch_log.start_date)
        print("end_date:", fetch_log.end_date)
        print("fetched_rows:", fetch_log.fetched_rows)
        print("error_message:", fetch_log.error_message)
        print("started_at:", fetch_log.started_at)
        print("completed_at:", fetch_log.completed_at)
finally:
    session.close()
'@ | .\venv\Scripts\python.exe -
```

## Changing the execution time

The data team may change the execution time from Windows Task Scheduler.

Changing:

```text
09:00
```

to another time does not require changing:

- TEFAS client code
- Database models
- Repository code
- Upsert service
- Fetch-log service
- Scheduler wrapper code

## Changing the requested date policy

Previous business day:

```text
scripts\sync_tefas_scheduled.py --kind YAT --date-mode previous-business-day
```

Same day:

```text
scripts\sync_tefas_scheduled.py --kind YAT --date-mode today
```

This can be changed in the Task Scheduler action arguments.

## Running one fund only

Example:

```text
scripts\sync_tefas_scheduled.py --kind YAT --date-mode previous-business-day --fund-code AAL
```

For the normal bulk task, omit `--fund-code`.

## Updating the deployed code

Before pulling new changes:

1. Confirm that no synchronization is currently running.
2. Open the project directory.
3. Pull the latest `main`.
4. Install any new dependencies.
5. Apply migrations.
6. Run tests.
7. Run one manual scheduled-wrapper test.
8. Re-enable or manually run the scheduled task.

Example:

```powershell
git switch main
git pull origin main
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m pytest
```

## Security rules

Never place these values in Task Scheduler arguments:

- PostgreSQL password
- Database URL
- JWT secret
- `.env` contents
- Personal credentials

Never commit:

```text
.env
```

The repository should contain only:

```text
.env.example
```

Use a dedicated database user for the shared deployment environment when
possible.

## Troubleshooting

### The script works in the terminal but not in Task Scheduler

Check:

- Program/script points to the virtual-environment Python executable.
- Start-in directory is the repository root.
- The deployment account can read `.env`.
- The deployment account can access PostgreSQL.
- The deployment account has network access.
- Database migrations are at the latest revision.
- Task arguments contain no incorrect quotation marks.
- The project path exists on that computer.

### Task returns exit code 1

Inspect the latest `FAILED` row in:

```text
tefas_fetch_logs
```

The `error_message` field contains the original synchronization error when the
failure log was successfully written.

### Task creates a RUNNING row but does not complete

Possible causes include:

- The process was terminated.
- The computer shut down during execution.
- The Python process was killed.
- The database became unavailable before the log update.
- The task exceeded its configured execution limit.

A future maintenance process may detect and investigate stale `RUNNING` rows.

### No data is returned

Possible causes include:

- The selected date has no published data.
- The date is a weekend or holiday.
- The requested fund code is invalid.
- TEFAS returned an empty response.
- Network or TEFAS availability problems occurred.

Check the fetch log and retry after verifying the selected date.

## Removing the task

The task may be removed from Windows Task Scheduler without deleting:

- The GitHub repository
- The Python wrapper
- Database data
- Fetch logs
- TEFAS integration code

Removing the operating-system task only stops future automatic executions.

## Production migration

When the project moves from a personal computer to a shared server:

1. Clone the repository on the server.
2. Create the server's own virtual environment.
3. Create the server's own `.env`.
4. Configure the shared `DATABASE_URL`.
5. Apply migrations.
6. Run tests.
7. Test the wrapper manually.
8. Register the scheduler on the server.
9. Disable the old personal-computer task.

Only one production scheduler should be active for the same data scope.

## Current MVP limitations

The current business-day calculation skips:

- Saturday
- Sunday

It does not yet skip official Turkish holidays.

The current MVP supports:

```text
YAT
```

Additional fund kinds can be added later after the data contract is approved.