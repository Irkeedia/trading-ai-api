import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import get_db
from ..schemas import EngineAction
from ..security import verify_sensitive_api_key
from ...utils.config import AppConfig
from ...utils.database import Database

router = APIRouter(prefix="/api/engine", tags=["engine"])


@router.get("/status")
async def get_engine_status(db: Database = Depends(get_db)):
    status = await db.get_engine_status()
    if status:
        for k, v in status.items():
            if isinstance(v, datetime):
                status[k] = v.isoformat()
    return status or {"status": "stopped", "mode": "PAPER"}


@router.post("/control", dependencies=[Depends(verify_sensitive_api_key)])
async def control_engine(request: Request, action: EngineAction):
    """Démarrer ou arrêter le moteur de trading."""
    db: Database | None = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(503, "Database not ready")

    engine_ref = getattr(request.app.state, "engine_ref", None)
    engine_task = getattr(request.app.state, "engine_task", None)

    if action.action == "start":
        if engine_ref and engine_ref.running:
            return {"status": "already_running"}

        from ...core.engine import TradingEngine

        cfg = AppConfig()
        engine_ref = TradingEngine(cfg)
        engine_ref.db = db

        await engine_ref.initialize()

        request.app.state.engine_ref = engine_ref
        request.app.state.engine_task = asyncio.create_task(
            _run_engine(request.app, engine_ref)
        )
        return {"status": "started", "mode": action.mode}

    if action.action == "stop":
        if engine_ref and engine_ref.running:
            engine_ref.running = False
            t = getattr(request.app.state, "engine_task", None)
            if t:
                t.cancel()
            request.app.state.engine_task = None
            request.app.state.engine_ref = None
            return {"status": "stopped"}
        return {"status": "not_running"}

    raise HTTPException(400, f"Action inconnue: {action.action}")


async def _run_engine(app, engine):
    """Wrapper pour exécuter le moteur en background."""
    db: Database | None = getattr(app.state, "db", None)
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
