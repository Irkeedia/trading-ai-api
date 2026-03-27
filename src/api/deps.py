from fastapi import HTTPException, Request

from ..utils.config import AppConfig
from ..utils.database import Database


def get_db(request: Request) -> Database:
    db: Database | None = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(503, "Database not ready")
    return db


def get_config(request: Request) -> AppConfig:
    cfg: AppConfig | None = getattr(request.app.state, "config", None)
    if not cfg:
        raise HTTPException(503, "Config not ready")
    return cfg


def get_db_optional(request: Request) -> Database | None:
    return getattr(request.app.state, "db", None)
