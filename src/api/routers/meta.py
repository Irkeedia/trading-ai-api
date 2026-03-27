from fastapi import APIRouter, Depends

from ..deps import get_config
from ...utils.config import AppConfig

router = APIRouter(tags=["config"])


@router.get("/api/config")
async def get_config_endpoint(cfg: AppConfig = Depends(get_config)):
    """Configuration actuelle (sans secrets)."""
    return {
        "trading": {
            "mode": cfg.trading.mode,
            "base_currency": cfg.trading.base_currency,
            "max_open_positions": cfg.trading.max_open_positions,
            "check_interval_seconds": cfg.trading.check_interval_seconds,
        },
        "exchange": cfg.primary_exchange,
        "watchlist": cfg.watchlist,
        "risk": {
            "max_portfolio_risk_pct": cfg.risk.max_portfolio_risk_pct,
            "max_position_size_pct": cfg.risk.max_position_size_pct,
            "stop_loss_pct": cfg.risk.stop_loss_pct,
            "take_profit_pct": cfg.risk.take_profit_pct,
            "trailing_stop_pct": cfg.risk.trailing_stop_pct,
            "max_daily_loss_pct": cfg.risk.max_daily_loss_pct,
        },
        "ai": {
            "provider": cfg.ai.provider,
            "model": cfg.ai.model,
        },
    }
