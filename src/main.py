from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

# Support running `python src/main.py` by ensuring the project root is importable.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import get_settings
from src.controller.auth_controller import router as auth_router
from src.controller.health_controller import router as health_router
from src.controller.portfolio_controller import router as portfolio_router


settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(portfolio_router)
