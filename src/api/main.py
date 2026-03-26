"""
API FastAPI — Point d'entrée du backend Trading IA.
Expose tous les endpoints REST pour le dashboard.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..utils.config import AppConfig
from ..utils.database import Database

# ─── Globals ────────────────────────────────────────────────
config: AppConfig | None = None
db: Database | None = None
engine_task: asyncio.Task | None = None
engine_ref = None  # TradingEngine reference


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage & arrêt propres."""
    global config, db
    config = AppConfig()
    db = Database(config.env.database_url)
    try:
        await db.initialize()
    except Exception as e:
        import logging
        logging.warning(f"DB connection failed at startup: {e}")
        db = None
    yield
    if db:
        await db.close()


app = FastAPI(
    title="Trading IA API",
    version="1.0.0",
    description="API backend pour le système de trading autonome IA",
    lifespan=lifespan,
)

# ─── CORS ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Sera restreint via env en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Modèles Pydantic ──────────────────────────────────────

class EngineAction(BaseModel):
    action: str  # "start" | "stop"
    mode: str = "PAPER"
    exchange: str = "binance"


class ManualTradeRequest(BaseModel):
    symbol: str
    side: str  # "buy" | "sell"
    amount: Optional[float] = None


class ConfigUpdate(BaseModel):
    check_interval_seconds: Optional[int] = None
    max_open_positions: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    max_daily_loss_pct: Optional[float] = None


class ExchangeKeysRequest(BaseModel):
    email: str
    exchange: str = "binance"
    api_key: str
    api_secret: str


class ExchangeKeysDelete(BaseModel):
    email: str
    exchange: str = "binance"


# ─── Health ─────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─── Dashboard Summary ─────────────────────────────────────

@app.get("/api/dashboard")
async def get_dashboard():
    """Résumé complet pour la page principale du dashboard."""
    if not db:
        raise HTTPException(503, "Database not ready")
    return await db.get_dashboard_summary()


# ─── Portfolio ──────────────────────────────────────────────

@app.get("/api/portfolio")
async def get_portfolio():
    """Dernier snapshot du portfolio."""
    if not db:
        raise HTTPException(503, "Database not ready")
    snapshot = await db.get_latest_snapshot()
    return snapshot or {}


@app.get("/api/portfolio/history")
async def get_portfolio_history(days: int = Query(30, ge=1, le=365)):
    """Historique des valeurs du portfolio."""
    if not db:
        raise HTTPException(503, "Database not ready")
    return await db.get_performance_chart(days)


# ─── Trades ─────────────────────────────────────────────────

@app.get("/api/trades")
async def get_trades(
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    if not db:
        raise HTTPException(503, "Database not ready")
    trades = await db.get_recent_trades(symbol, limit)
    # Convert datetime objects for JSON serialization
    for t in trades:
        for k, v in t.items():
            if isinstance(v, datetime):
                t[k] = v.isoformat()
    return trades


@app.get("/api/trades/stats")
async def get_trades_stats():
    if not db:
        raise HTTPException(503, "Database not ready")
    return await db.get_trades_stats()


# ─── Signals ────────────────────────────────────────────────

@app.get("/api/signals")
async def get_signals(
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
):
    if not db:
        raise HTTPException(503, "Database not ready")
    signals = await db.get_recent_signals(symbol, limit)
    for s in signals:
        for k, v in s.items():
            if isinstance(v, datetime):
                s[k] = v.isoformat()
    return signals


# ─── AI Analyses ────────────────────────────────────────────

@app.get("/api/analyses")
async def get_analyses(
    symbol: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
):
    if not db:
        raise HTTPException(503, "Database not ready")
    analyses = await db.get_recent_analyses(symbol, limit)
    for a in analyses:
        for k, v in a.items():
            if isinstance(v, datetime):
                a[k] = v.isoformat()
    return analyses


# ─── News ───────────────────────────────────────────────────

@app.get("/api/news")
async def get_news(limit: int = Query(30, ge=1, le=100)):
    if not db:
        raise HTTPException(503, "Database not ready")
    news = await db.get_recent_news(limit)
    for n in news:
        for k, v in n.items():
            if isinstance(v, datetime):
                n[k] = v.isoformat()
    return news


# ─── Engine Control ─────────────────────────────────────────

@app.get("/api/engine/status")
async def get_engine_status():
    if not db:
        raise HTTPException(503, "Database not ready")
    status = await db.get_engine_status()
    if status:
        for k, v in status.items():
            if isinstance(v, datetime):
                status[k] = v.isoformat()
    return status or {"status": "stopped", "mode": "PAPER"}


@app.post("/api/engine/control")
async def control_engine(action: EngineAction):
    """Démarrer ou arrêter le moteur de trading."""
    global engine_task, engine_ref

    if action.action == "start":
        if engine_ref and engine_ref.running:
            return {"status": "already_running"}

        # Import ici pour éviter les imports circulaires
        from ..core.engine import TradingEngine

        cfg = AppConfig()
        engine_ref = TradingEngine(cfg)
        engine_ref.db = db  # Partager la même BDD

        await engine_ref.initialize()

        # Lancer en background
        engine_task = asyncio.create_task(_run_engine(engine_ref))
        return {"status": "started", "mode": action.mode}

    elif action.action == "stop":
        if engine_ref and engine_ref.running:
            engine_ref.running = False
            if engine_task:
                engine_task.cancel()
                engine_task = None
            engine_ref = None
            return {"status": "stopped"}
        return {"status": "not_running"}

    raise HTTPException(400, f"Action inconnue: {action.action}")


async def _run_engine(engine):
    """Wrapper pour exécuter le moteur en background."""
    try:
        await engine.run()
    except asyncio.CancelledError:
        await engine.shutdown()
    except Exception as e:
        from loguru import logger
        logger.error(f"Engine crashed: {e}")
        if db:
            await db.update_engine_status(
                status="error",
                error=str(e),
            )


# ─── Config ─────────────────────────────────────────────────


# ─── Exchange API Keys ──────────────────────────────────────

@app.post("/api/exchange/keys")
async def save_exchange_keys(req: ExchangeKeysRequest):
    """Save user exchange API keys, then validate them by connecting."""
    if not db:
        raise HTTPException(503, "Database not ready")

    # Validate by attempting a real connection via CCXT
    import ccxt
    exchange_class = getattr(ccxt, req.exchange, None)
    if not exchange_class:
        raise HTTPException(400, f"Exchange '{req.exchange}' non supporté")

    try:
        ex = exchange_class({
            "apiKey": req.api_key,
            "secret": req.api_secret,
            "enableRateLimit": True,
        })
        # Fetch balance to verify keys work
        balance = await asyncio.get_event_loop().run_in_executor(
            None, ex.fetch_balance
        )
        usdt_free = balance.get("USDT", {}).get("free", 0)
        usdt_total = balance.get("USDT", {}).get("total", 0)
    except ccxt.AuthenticationError:
        raise HTTPException(401, "Clés API invalides — vérifiez votre API key et secret")
    except ccxt.ExchangeError as e:
        raise HTTPException(400, f"Erreur exchange: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de connexion: {str(e)}")

    # Keys valid — save to DB
    await db.save_user_api_keys(req.email, req.exchange, req.api_key, req.api_secret)

    return {
        "status": "connected",
        "exchange": req.exchange,
        "balance_usdt": {
            "free": usdt_free,
            "total": usdt_total,
        },
    }


@app.get("/api/exchange/keys")
async def get_exchange_keys(email: str = Query(...)):
    """Get user's saved exchange connections (secrets masked)."""
    if not db:
        raise HTTPException(503, "Database not ready")
    keys = await db.get_user_api_keys(email)
    for k in keys:
        for field, v in k.items():
            if isinstance(v, datetime):
                k[field] = v.isoformat()
    return keys


@app.delete("/api/exchange/keys")
async def delete_exchange_keys(req: ExchangeKeysDelete):
    """Disconnect an exchange."""
    if not db:
        raise HTTPException(503, "Database not ready")
    await db.delete_user_api_keys(req.email, req.exchange)
    return {"status": "deleted", "exchange": req.exchange}


@app.get("/api/config")
async def get_config():
    """Retourne la configuration actuelle (sans secrets)."""
    if not config:
        raise HTTPException(503, "Config not ready")
    return {
        "trading": {
            "mode": config.trading.mode,
            "base_currency": config.trading.base_currency,
            "max_open_positions": config.trading.max_open_positions,
            "check_interval_seconds": config.trading.check_interval_seconds,
        },
        "exchange": config.primary_exchange,
        "watchlist": config.watchlist,
        "risk": {
            "max_portfolio_risk_pct": config.risk.max_portfolio_risk_pct,
            "max_position_size_pct": config.risk.max_position_size_pct,
            "stop_loss_pct": config.risk.stop_loss_pct,
            "take_profit_pct": config.risk.take_profit_pct,
            "trailing_stop_pct": config.risk.trailing_stop_pct,
            "max_daily_loss_pct": config.risk.max_daily_loss_pct,
        },
        "ai": {
            "provider": config.ai.provider,
            "model": config.ai.model,
        },
    }
