# PROJECT_STATUS.md

## Project identity

- **Project:** AI-Assisted Portfolio Management System
- **Type:** Browser-based web application
- **Team size:** 4
- **Supervisor:** Prof. Dr. Hakan Altınçay
- **Current backend stage:** Authentication and database foundation implemented; Portfolio CRUD vertical slice implemented and verified locally with automated tests and PostgreSQL.
- **Status updated:** 2026-07-30

## Product summary

The system will allow an individual investor to track TEFAS funds, precious metals and supported currency-based investments in one portfolio application. It will calculate portfolio value in multiple currencies and later add benchmark comparison and AI-supported analysis.

The current repository contains the backend foundation, the verified authentication flow and the completed Portfolio CRUD vertical slice. Portfolio functionality has been verified with automated tests, Alembic migrations and manual PostgreSQL API tests.

## Current repository structure

```text
src/
├── config/
├── controller/
├── exception/
├── mapper/
├── model/
├── repositories/
├── request/
├── response/
└── services/
alembic/
tests/
```

## Current implementation status

| Area | Status | Notes |
|---|---|---|
| Backend folder structure | Complete | Modular backend layout exists under `src/` |
| FastAPI application factory | Complete | Application created in `src/main.py` |
| API versioning | Partial | Current routes use `/api/v1`; no separate version module layer yet |
| Health endpoint | Complete | `GET /api/v1/health` is registered |
| Environment configuration | Complete | `.env.example` and Pydantic settings are present |
| SQLAlchemy base/session | Complete | Engine, session factory and FastAPI DB dependency are implemented |
| Alembic scaffold | Complete | `alembic.ini`, `env.py` and initial revision were added |
| Initial users migration | Complete | `alembic/versions/20260724_0001_create_users_table.py` exists and was verified on SQLite |
| User entity | Complete | SQLAlchemy `User` model implemented |
| User repository | Complete | Lookup and create operations implemented |
| Authentication service | Complete | Password hashing, JWT creation/validation and user service are implemented |
| Authentication API | Complete | `register`, `login` and `me` endpoints are implemented; flow verified locally with both SQLite and PostgreSQL |
| Auth tests | Complete | Pytest coverage added for happy path plus duplicate email, wrong password and invalid token negative cases |
| Portfolio domain | Complete | CRUD, ownership, pagination and soft delete implemented and verified |
| Asset domain | Not started | No asset model, migration or endpoints yet |
| Transaction domain | Not started | No transaction model, migration or calculations yet |
| Market-data integration | Not started | No adapters or sync services yet |
| AI integration | Not started | No analytics, sentiment or report modules yet |
| Frontend integration | Not started | No frontend contract work yet |

## Implemented files added in this stage

### Database and models

- `src/config/database.py`
- `src/config/dependencies.py`
- `src/model/base.py`
- `src/model/user.py`
- `src/repositories/user_repository.py`

### Authentication flow

- `src/services/user_service.py`
- `src/controller/auth_controller.py`
- `src/services/token_service.py`
- `src/services/password_service.py`

### Migration and tests

- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/20260724_0001_create_users_table.py`
- `tests/conftest.py`
- `tests/test_auth.py`

### Portfolio management

- `src/model/portfolio.py`
- `src/repositories/portfolio_repository.py`
- `src/services/portfolio_service.py`
- `src/request/portfolio_request.py`
- `src/response/portfolio_response.py`
- `src/controller/portfolio_controller.py`

### Portfolio migration and tests

- `alembic/versions/20260730_0002_create_portfolios_table.py`
- `tests/test_portfolio.py`

## Implemented API

```text
GET  /api/v1/health
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST   /api/v1/portfolios
GET    /api/v1/portfolios
GET    /api/v1/portfolios/{portfolio_id}
PATCH  /api/v1/portfolios/{portfolio_id}
DELETE /api/v1/portfolios/{portfolio_id}
```

## Verification performed

- `python -m compileall src tests alembic`
- `python -m pytest`
- `python -m alembic upgrade head` verified against a temporary SQLite database by setting `DATABASE_URL=sqlite:///./tmp_alembic_test.db`
- Auth flow verified locally through Swagger with SQLite for `GET /api/v1/health`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, JWT authorize and `GET /api/v1/auth/me`
- PostgreSQL connection, `python -m alembic upgrade head`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, JWT authorize and `GET /api/v1/auth/me` were verified locally
- Portfolio compileall verification completed successfully.
- Pytest result: 25 passed.
- Alembic migration upgrade, downgrade and re-upgrade were verified using a temporary SQLite database.
- Alembic current on PostgreSQL: `20260730_0002 (head)`.
- `POST /api/v1/portfolios` returned `201 Created` on PostgreSQL.
- Portfolio list, detail and update endpoints returned `200 OK` on PostgreSQL.
- Lowercase currency input was normalized to uppercase.
- `DELETE /api/v1/portfolios/{portfolio_id}` returned `204 No Content` and performed soft delete.
- A soft-deleted portfolio returned `404 Not Found` and disappeared from the active portfolio listing.

## Git analysis note

The repository history currently contains only one pre-analysis project commit (`aa5b107`, dated 2026-07-24) plus the analysis baseline commit created on 2026-07-25. Missing auth/database source files were **not** recoverable from Git history, branches or prior commits; they were recreated in this stage.

## Immediate next backend steps

1. Define the Asset domain fields and agree on the backend/data integration contract.
2. Keep auth stable and expand remaining negative-path coverage such as duplicate username or inactive user if needed.
3. Add central exception formatting if the team wants uniform API error bodies.
4. After the Asset contract is finalized, implement the Asset vertical slice without starting Transaction development.

## Local commands

```text
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
python -m pytest
uvicorn src.main:app --reload
```

