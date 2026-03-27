"""Modèles Pydantic partagés par l'API."""
from typing import Literal, Optional

from pydantic import BaseModel


class EngineAction(BaseModel):
    action: Literal["start", "stop"]
    mode: Literal["PAPER", "LIVE"] = "PAPER"
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
