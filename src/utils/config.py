"""
Gestion de la configuration centralisée via Pydantic + YAML + .env
"""
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ExchangeConfig(BaseModel):
    name: str
    enabled: bool = False
    sandbox: bool = True


class TradingConfig(BaseModel):
    mode: str = "PAPER"
    base_currency: str = "USDT"
    max_open_positions: int = 5
    check_interval_seconds: int = 60


class RiskConfig(BaseModel):
    max_portfolio_risk_pct: float = 2.0
    max_position_size_pct: float = 10.0
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0
    trailing_stop_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    min_risk_reward_ratio: float = 2.0
    cooldown_after_loss_minutes: int = 30


class AIConfig(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.0-flash"
    analysis_interval_minutes: int = 15
    max_tokens: int = 4096
    temperature: float = 0.3


class SentimentConfig(BaseModel):
    enabled: bool = True
    sources: list[str] = ["cryptopanic", "rss_feeds"]
    rss_feeds: list[str] = []
    update_interval_minutes: int = 10


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/trading.log"
    rotation: str = "10 MB"
    retention: str = "30 days"


class DashboardConfig(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8050


class EnvSettings(BaseSettings):
    """Clés API chargées depuis .env"""
    gemini_api_key: str = ""
    binance_api_key: str = ""
    binance_secret_key: str = ""
    kraken_api_key: str = ""
    kraken_secret_key: str = ""
    coinbase_api_key: str = ""
    coinbase_secret_key: str = ""
    news_api_key: str = ""
    trading_mode: str = "PAPER"
    database_url: str = "postgresql://localhost/trading"
    api_secret_key: str = "change-me-in-production"
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


class AppConfig:
    """Configuration globale de l'application."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.env = EnvSettings()
        self._raw = self._load_yaml(config_path)

        self.trading = TradingConfig(**self._raw.get("trading", {}))
        self.trading.mode = self.env.trading_mode or self.trading.mode

        exchanges_cfg = self._raw.get("exchanges", {})
        self.primary_exchange = exchanges_cfg.get("primary", "binance")
        self.exchanges = [
            ExchangeConfig(**ex)
            for ex in exchanges_cfg.get("available", [])
        ]

        self.watchlist = self._raw.get("symbols", {}).get("watchlist", [])

        analysis = self._raw.get("analysis", {})
        tech = analysis.get("technical", {})
        self.timeframes = tech.get("timeframes", ["1h", "4h", "1d"])
        self.indicators = tech.get("indicators", ["RSI", "MACD", "BB", "EMA"])

        self.ai = AIConfig(**analysis.get("ai", {}))
        self.sentiment = SentimentConfig(**analysis.get("sentiment", {}))

        self.risk = RiskConfig(**self._raw.get("risk_management", {}))
        self.logging = LoggingConfig(**self._raw.get("logging", {}))
        self.dashboard = DashboardConfig(**self._raw.get("dashboard", {}))

    def _load_yaml(self, path: str) -> dict:
        config_file = Path(path)
        if not config_file.exists():
            return {}
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_exchange_credentials(self, exchange_name: str) -> dict:
        """Retourne les credentials pour un exchange donné."""
        creds_map = {
            "binance": {
                "apiKey": self.env.binance_api_key,
                "secret": self.env.binance_secret_key,
            },
            "kraken": {
                "apiKey": self.env.kraken_api_key,
                "secret": self.env.kraken_secret_key,
            },
            "coinbase": {
                "apiKey": self.env.coinbase_api_key,
                "secret": self.env.coinbase_secret_key,
            },
        }
        return creds_map.get(exchange_name, {})

    def is_sandbox(self, exchange_name: str) -> bool:
        for ex in self.exchanges:
            if ex.name == exchange_name:
                return ex.sandbox
        return True
