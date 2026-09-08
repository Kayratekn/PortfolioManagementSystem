from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Support running `python src/main.py` by ensuring the project root is importable.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import get_settings
from src.controller.ai_analysis_history_controller import (
    portfolio_router as ai_analysis_history_portfolio_router,
)
from src.controller.ai_analysis_history_controller import router as ai_analysis_history_router
from src.controller.ai_portfolio_analysis_controller import router as ai_portfolio_analysis_router
from src.controller.ai_robustness_controller import router as ai_robustness_router
from src.controller.asset_controller import router as asset_router
from src.controller.auth_controller import router as auth_router
from src.controller.benchmark_catalog_controller import router as benchmark_catalog_router
from src.controller.benchmark_comparison_controller import router as benchmark_comparison_router
from src.controller.cost_basis_controller import router as cost_basis_router
from src.controller.data_sync_status_controller import router as data_sync_status_router
from src.controller.health_controller import router as health_router
from src.controller.holding_controller import router as holding_router
from src.controller.note_controller import router as note_router
from src.controller.portfolio_cash_flow_controller import router as portfolio_cash_flow_router
from src.controller.portfolio_controller import router as portfolio_router
from src.controller.portfolio_valuation_controller import router as portfolio_valuation_router
from src.controller.portfolio_performance_controller import router as portfolio_performance_router
from src.controller.realized_pl_controller import router as realized_pl_router
from src.controller.report_controller import router as report_router
from src.controller.transaction_controller import router as transaction_router
from src.controller.watchlist_controller import router as watchlist_router
from src.controller.unrealized_pl_controller import router as unrealized_pl_router
from src.controller.tefas_fund_controller import router as tefas_fund_router


settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(health_router)
app.include_router(ai_analysis_history_router)
app.include_router(ai_analysis_history_portfolio_router)
app.include_router(ai_portfolio_analysis_router)
app.include_router(ai_robustness_router)
app.include_router(auth_router)
app.include_router(report_router)
app.include_router(asset_router)
app.include_router(portfolio_router)
app.include_router(portfolio_cash_flow_router)
app.include_router(transaction_router)
app.include_router(watchlist_router)
app.include_router(note_router)
app.include_router(holding_router)
app.include_router(portfolio_valuation_router)
app.include_router(portfolio_performance_router)
app.include_router(benchmark_catalog_router)
app.include_router(benchmark_comparison_router)
app.include_router(data_sync_status_router)
app.include_router(cost_basis_router)
app.include_router(unrealized_pl_router)
app.include_router(realized_pl_router)
app.include_router(tefas_fund_router)
