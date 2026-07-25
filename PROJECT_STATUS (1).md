# PROJECT_STATUS.md

## Project identity

- **Project:** AI-Assisted Portfolio Management System
- **Type:** Browser-based web application
- **Team size:** 4
- **Supervisor:** Prof. Dr. Hakan Altınçay
- **Current backend stage:** Authentication and database foundation implemented; portfolio domain not started
- **Status updated:** 2026-07-25

## Product summary

The system will allow an individual investor to track TEFAS funds, precious metals and supported currency-based investments in one portfolio application. It will calculate portfolio value in multiple currencies and later add benchmark comparison and AI-supported analysis.

The current repository only contains the backend foundation and the first verified user authentication flow.

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
| Authentication API | Complete | `register`, `login` and `me` endpoints are implemented |
| Auth tests | Complete | Pytest coverage added for happy path, duplicate email, invalid login and protected `/me` |
| Portfolio / Asset / Transaction domain | Not started | No portfolio models, routes or calculations yet |
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

## Implemented API

```text
GET  /api/v1/health
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

## Verification performed

- `python -m compileall src tests alembic`
- `python -m pytest`
- `python -m alembic upgrade head` verified against a temporary SQLite database by setting `DATABASE_URL=sqlite:///./tmp_alembic_test.db`

## Git analysis note

The repository history currently contains only one pre-analysis project commit (`aa5b107`, dated 2026-07-24) plus the analysis baseline commit created on 2026-07-25. Missing auth/database source files were **not** recoverable from Git history, branches or prior commits; they were recreated in this stage.

## Immediate next backend steps

1. Keep auth stable and add negative-path tests such as duplicate username, malformed token and inactive user.
2. Add central exception formatting if the team wants uniform API error bodies.
3. Freeze the authentication contract with the frontend before starting any portfolio features.
4. Only after auth contract is stable, start Portfolio, Asset and Transaction entities in a vertical slice.

## Local commands

```text
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
python -m pytest
uvicorn src.main:app --reload
```