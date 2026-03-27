"""
API FastAPI — Point d'entrée du backend Trading IA.
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from ..utils.config import AppConfig, EnvSettings
from ..utils.database import Database
from .routers import analyses, dashboard, engine, exchange, health, meta, news, portfolio, signals, trades


def _parse_cors_origins(raw: str) -> list[str]:
    parts = [o.strip() for o in (raw or "").split(",") if o.strip()]
    return parts if parts else ["http://localhost:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarrage & arrêt propres."""
    cfg = AppConfig()
    app.state.config = cfg
    app.state.db = Database(cfg.env.database_url)
    app.state.engine_task = None
    app.state.engine_ref = None

    import logging as pylog

    try:
        await app.state.db.initialize()
    except Exception as e:
        pylog.warning(f"DB connection failed at startup: {e}")
        app.state.db = None

    yield

    if app.state.db:
        await app.state.db.close()


app = FastAPI(
    title="Trading IA API",
    version="1.0.0",
    description="API backend pour le système de trading autonome IA",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    logger.bind(request_id=rid).debug(f"{request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


_cors_origins = _parse_cors_origins(EnvSettings().cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(signals.router)
app.include_router(analyses.router)
app.include_router(news.router)
app.include_router(engine.router)
app.include_router(exchange.router)
app.include_router(meta.router)
