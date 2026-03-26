"""
Base de données PostgreSQL async (Neon) pour stocker trades, signaux, et performances.
Compatible aussi avec SQLite pour le dev local.
"""
import asyncpg
from datetime import datetime
from loguru import logger


class Database:
    def __init__(self, database_url: str = ""):
        self.database_url = database_url
        self.pool = None

    async def initialize(self):
        """Crée le pool de connexions et les tables."""
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
        )
        await self._create_tables()
        logger.info("Base de données PostgreSQL (Neon) initialisée")

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    amount DOUBLE PRECISION NOT NULL,
                    cost DOUBLE PRECISION NOT NULL,
                    fee DOUBLE PRECISION DEFAULT 0,
                    pnl DOUBLE PRECISION DEFAULT 0,
                    strategy TEXT,
                    exchange TEXT,
                    order_id TEXT,
                    status TEXT DEFAULT 'executed',
                    notes TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    strength DOUBLE PRECISION NOT NULL,
                    source TEXT NOT NULL,
                    timeframe TEXT,
                    details TEXT,
                    acted_on BOOLEAN DEFAULT FALSE
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    total_value_usdt DOUBLE PRECISION NOT NULL,
                    available_balance DOUBLE PRECISION NOT NULL,
                    positions_value DOUBLE PRECISION NOT NULL,
                    daily_pnl DOUBLE PRECISION DEFAULT 0,
                    total_pnl DOUBLE PRECISION DEFAULT 0,
                    positions_json JSONB DEFAULT '{}'
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_analyses (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    symbol TEXT,
                    analysis_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_summary TEXT,
                    result JSONB NOT NULL,
                    confidence DOUBLE PRECISION,
                    tokens_used INTEGER DEFAULT 0
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS news_items (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    title TEXT NOT NULL,
                    source TEXT,
                    url TEXT,
                    sentiment_score DOUBLE PRECISION,
                    relevance_score DOUBLE PRECISION,
                    related_symbols TEXT,
                    summary TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS engine_status (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    status TEXT NOT NULL DEFAULT 'stopped',
                    mode TEXT DEFAULT 'PAPER',
                    exchange TEXT,
                    cycle_count INTEGER DEFAULT 0,
                    uptime_seconds INTEGER DEFAULT 0,
                    error TEXT,
                    details JSONB DEFAULT '{}'
                )
            """)
            # Index pour les performances
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON portfolio_snapshots(timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_timestamp ON ai_analyses(timestamp DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_engine_timestamp ON engine_status(timestamp DESC)")

    # --- Trades ---

    async def record_trade(self, symbol: str, side: str, price: float,
                           amount: float, cost: float, fee: float = 0,
                           pnl: float = 0, strategy: str = "",
                           exchange: str = "", order_id: str = "",
                           notes: str = ""):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO trades 
                   (timestamp, symbol, side, price, amount, cost, fee, pnl, strategy, exchange, order_id, notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
                datetime.utcnow(), symbol, side, price, amount,
                cost, fee, pnl, strategy, exchange, order_id, notes
            )
        logger.info(f"Trade enregistré: {side} {amount} {symbol} @ {price}")

    async def get_recent_trades(self, symbol: str = None, limit: int = 50) -> list[dict]:
        async with self.pool.acquire() as conn:
            if symbol:
                rows = await conn.fetch(
                    "SELECT * FROM trades WHERE symbol = $1 ORDER BY timestamp DESC LIMIT $2",
                    symbol, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM trades ORDER BY timestamp DESC LIMIT $1", limit
                )
            return [dict(r) for r in rows]

    async def get_daily_pnl(self) -> float:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COALESCE(SUM(pnl), 0) as daily_pnl FROM trades WHERE timestamp::date = CURRENT_DATE"
            )
            return row["daily_pnl"] if row else 0

    async def get_trades_stats(self) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE pnl > 0) as winning_trades,
                    COUNT(*) FILTER (WHERE pnl < 0) as losing_trades,
                    COALESCE(SUM(pnl), 0) as total_pnl,
                    COALESCE(AVG(pnl), 0) as avg_pnl,
                    COALESCE(MAX(pnl), 0) as best_trade,
                    COALESCE(MIN(pnl), 0) as worst_trade
                FROM trades
            """)
            return dict(row) if row else {}

    # --- Signals ---

    async def record_signal(self, symbol: str, signal_type: str,
                            strength: float, source: str,
                            timeframe: str = "", details: str = ""):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO signals
                   (timestamp, symbol, signal_type, strength, source, timeframe, details)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                datetime.utcnow(), symbol, signal_type, strength,
                source, timeframe, details
            )

    async def get_recent_signals(self, symbol: str = None, limit: int = 20) -> list[dict]:
        async with self.pool.acquire() as conn:
            if symbol:
                rows = await conn.fetch(
                    "SELECT * FROM signals WHERE symbol = $1 ORDER BY timestamp DESC LIMIT $2",
                    symbol, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM signals ORDER BY timestamp DESC LIMIT $1", limit
                )
            return [dict(r) for r in rows]

    # --- AI Analyses ---

    async def record_ai_analysis(self, symbol: str, analysis_type: str,
                                 provider: str, result: str,
                                 confidence: float = 0,
                                 prompt_summary: str = "",
                                 tokens_used: int = 0):
        import json as _json
        result_json = result if isinstance(result, dict) else _json.loads(result) if isinstance(result, str) else {}
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ai_analyses
                   (timestamp, symbol, analysis_type, provider, prompt_summary, result, confidence, tokens_used)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)""",
                datetime.utcnow(), symbol, analysis_type, provider,
                prompt_summary, _json.dumps(result_json), confidence, tokens_used
            )

    async def get_recent_analyses(self, symbol: str = None, limit: int = 10) -> list[dict]:
        async with self.pool.acquire() as conn:
            if symbol:
                rows = await conn.fetch(
                    "SELECT * FROM ai_analyses WHERE symbol = $1 ORDER BY timestamp DESC LIMIT $2",
                    symbol, limit
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM ai_analyses ORDER BY timestamp DESC LIMIT $1", limit
                )
            return [dict(r) for r in rows]

    # --- Portfolio Snapshots ---

    async def record_portfolio_snapshot(self, total_value: float,
                                        available: float,
                                        positions_value: float,
                                        daily_pnl: float = 0,
                                        total_pnl: float = 0,
                                        positions_json: str = "{}"):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO portfolio_snapshots
                   (timestamp, total_value_usdt, available_balance, positions_value, daily_pnl, total_pnl, positions_json)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
                datetime.utcnow(), total_value, available,
                positions_value, daily_pnl, total_pnl, positions_json
            )

    async def get_portfolio_history(self, limit: int = 100) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT $1", limit
            )
            return [dict(r) for r in rows]

    async def get_latest_snapshot(self) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
            )
            return dict(row) if row else None

    # --- News ---

    async def record_news(self, title: str, source: str = "", url: str = "",
                          sentiment_score: float = 0, relevance_score: float = 0,
                          related_symbols: str = "", summary: str = ""):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO news_items
                   (timestamp, title, source, url, sentiment_score, relevance_score, related_symbols, summary)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                datetime.utcnow(), title, source, url,
                sentiment_score, relevance_score, related_symbols, summary
            )

    async def get_recent_news(self, limit: int = 30) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM news_items ORDER BY timestamp DESC LIMIT $1", limit
            )
            return [dict(r) for r in rows]

    # --- Engine Status ---

    async def update_engine_status(self, status: str, mode: str = "",
                                    exchange: str = "", cycle_count: int = 0,
                                    uptime_seconds: int = 0, error: str = "",
                                    details: dict = None):
        import json as _json
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO engine_status
                   (timestamp, status, mode, exchange, cycle_count, uptime_seconds, error, details)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)""",
                datetime.utcnow(), status, mode, exchange,
                cycle_count, uptime_seconds, error,
                _json.dumps(details or {})
            )

    async def get_engine_status(self) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM engine_status ORDER BY timestamp DESC LIMIT 1"
            )
            return dict(row) if row else None

    # --- Dashboard aggregations ---

    async def get_dashboard_summary(self) -> dict:
        async with self.pool.acquire() as conn:
            snapshot = await conn.fetchrow(
                "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
            )
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE pnl > 0) as wins,
                    COUNT(*) FILTER (WHERE pnl < 0) as losses,
                    COALESCE(SUM(pnl), 0) as total_pnl,
                    COALESCE(SUM(pnl) FILTER (WHERE timestamp::date = CURRENT_DATE), 0) as today_pnl
                FROM trades
            """)
            engine = await conn.fetchrow(
                "SELECT * FROM engine_status ORDER BY timestamp DESC LIMIT 1"
            )
            active_signals = await conn.fetch(
                "SELECT * FROM signals ORDER BY timestamp DESC LIMIT 5"
            )
            return {
                "portfolio": dict(snapshot) if snapshot else {},
                "stats": dict(stats) if stats else {},
                "engine": dict(engine) if engine else {},
                "recent_signals": [dict(s) for s in active_signals],
            }

    async def get_performance_chart(self, days: int = 30) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    timestamp::date as date,
                    MAX(total_value_usdt) as value,
                    MAX(total_pnl) as pnl
                FROM portfolio_snapshots
                WHERE timestamp > NOW() - INTERVAL '1 day' * $1
                GROUP BY timestamp::date
                ORDER BY date
            """, days)
            return [dict(r) for r in rows]

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Pool PostgreSQL fermé")
