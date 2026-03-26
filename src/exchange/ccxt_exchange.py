"""
Implémentation de l'interface exchange via CCXT.
Supporte Binance, Kraken, Coinbase, et tous les exchanges CCXT.
"""
import asyncio
from typing import Optional
import ccxt.async_support as ccxt
import pandas as pd
from loguru import logger

from .base import BaseExchange


class CCXTExchange(BaseExchange):
    """Connexion universelle aux exchanges crypto via CCXT."""

    def __init__(self, exchange_id: str, api_key: str = "",
                 secret: str = "", sandbox: bool = True,
                 trading_mode: str = "PAPER"):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.secret = secret
        self.sandbox = sandbox
        self.trading_mode = trading_mode
        self.exchange: Optional[ccxt.Exchange] = None
        self._paper_balance = {
            "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0}
        }
        self._paper_positions = {}

    async def connect(self):
        """Initialise la connexion à l'exchange."""
        exchange_class = getattr(ccxt, self.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{self.exchange_id}' non supporté par CCXT")

        config = {
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }

        if self.api_key and self.secret:
            config["apiKey"] = self.api_key
            config["secret"] = self.secret

        self.exchange = exchange_class(config)

        if self.sandbox:
            if hasattr(self.exchange, "set_sandbox_mode"):
                self.exchange.set_sandbox_mode(True)
                logger.info(f"Mode sandbox activé pour {self.exchange_id}")

        await self.exchange.load_markets()
        logger.info(
            f"Connecté à {self.exchange_id} | "
            f"Marchés: {len(self.exchange.markets)} | "
            f"Mode: {'PAPER' if self.trading_mode == 'PAPER' else 'LIVE'}"
        )

    async def disconnect(self):
        if self.exchange:
            await self.exchange.close()
            logger.info(f"Déconnecté de {self.exchange_id}")

    async def get_balance(self) -> dict:
        if self.trading_mode == "PAPER":
            return self._paper_balance

        balance = await self.exchange.fetch_balance()
        return {
            currency: {
                "free": info["free"] or 0,
                "used": info["used"] or 0,
                "total": info["total"] or 0,
            }
            for currency, info in balance.items()
            if isinstance(info, dict) and info.get("total", 0) and info["total"] > 0
        }

    async def get_ticker(self, symbol: str) -> dict:
        ticker = await self.exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "last": ticker["last"],
            "bid": ticker["bid"],
            "ask": ticker["ask"],
            "high": ticker["high"],
            "low": ticker["low"],
            "volume": ticker["baseVolume"],
            "change_pct": ticker.get("percentage", 0),
            "timestamp": ticker["timestamp"],
        }

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h",
                        limit: int = 200) -> pd.DataFrame:
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        book = await self.exchange.fetch_order_book(symbol, limit)
        return {
            "bids": book["bids"][:limit],
            "asks": book["asks"][:limit],
            "spread": book["asks"][0][0] - book["bids"][0][0] if book["asks"] and book["bids"] else 0,
        }

    async def create_market_buy(self, symbol: str, amount: float) -> dict:
        if self.trading_mode == "PAPER":
            return await self._paper_market_order(symbol, "buy", amount)

        order = await self.exchange.create_market_buy_order(symbol, amount)
        logger.info(f"ACHAT MARCHÉ: {amount} {symbol} | ID: {order['id']}")
        return self._format_order(order)

    async def create_market_sell(self, symbol: str, amount: float) -> dict:
        if self.trading_mode == "PAPER":
            return await self._paper_market_order(symbol, "sell", amount)

        order = await self.exchange.create_market_sell_order(symbol, amount)
        logger.info(f"VENTE MARCHÉ: {amount} {symbol} | ID: {order['id']}")
        return self._format_order(order)

    async def create_limit_buy(self, symbol: str, amount: float,
                               price: float) -> dict:
        if self.trading_mode == "PAPER":
            return await self._paper_market_order(symbol, "buy", amount, price)

        order = await self.exchange.create_limit_buy_order(symbol, amount, price)
        logger.info(f"ACHAT LIMIT: {amount} {symbol} @ {price} | ID: {order['id']}")
        return self._format_order(order)

    async def create_limit_sell(self, symbol: str, amount: float,
                                price: float) -> dict:
        if self.trading_mode == "PAPER":
            return await self._paper_market_order(symbol, "sell", amount, price)

        order = await self.exchange.create_limit_sell_order(symbol, amount, price)
        logger.info(f"VENTE LIMIT: {amount} {symbol} @ {price} | ID: {order['id']}")
        return self._format_order(order)

    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        if self.trading_mode == "PAPER":
            return {"id": order_id, "status": "cancelled"}

        result = await self.exchange.cancel_order(order_id, symbol)
        logger.info(f"Ordre annulé: {order_id} ({symbol})")
        return result

    async def get_open_orders(self, symbol: str = None) -> list:
        if self.trading_mode == "PAPER":
            return []

        orders = await self.exchange.fetch_open_orders(symbol)
        return [self._format_order(o) for o in orders]

    async def get_positions(self) -> list:
        if self.trading_mode == "PAPER":
            return [
                {"symbol": s, **p}
                for s, p in self._paper_positions.items()
                if p.get("amount", 0) > 0
            ]

        try:
            positions = await self.exchange.fetch_positions()
            return [
                {
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "amount": p["contracts"],
                    "entry_price": p["entryPrice"],
                    "unrealized_pnl": p["unrealizedPnl"],
                    "liquidation_price": p.get("liquidationPrice"),
                }
                for p in positions
                if p["contracts"] and p["contracts"] > 0
            ]
        except Exception:
            return []

    async def get_multiple_tickers(self, symbols: list[str]) -> dict:
        """Récupère les tickers de plusieurs symboles en parallèle."""
        tasks = [self.get_ticker(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        tickers = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning(f"Erreur ticker {symbol}: {result}")
            else:
                tickers[symbol] = result
        return tickers

    async def get_multiple_ohlcv(self, symbols: list[str],
                                  timeframe: str = "1h",
                                  limit: int = 200) -> dict[str, pd.DataFrame]:
        """Récupère les OHLCV de plusieurs symboles."""
        result = {}
        for symbol in symbols:
            try:
                result[symbol] = await self.get_ohlcv(symbol, timeframe, limit)
                await asyncio.sleep(self.exchange.rateLimit / 1000)
            except Exception as e:
                logger.warning(f"Erreur OHLCV {symbol}/{timeframe}: {e}")
        return result

    # --- Paper Trading Engine ---

    async def _paper_market_order(self, symbol: str, side: str,
                                   amount: float,
                                   price: float = None) -> dict:
        """Simule un ordre en mode paper trading."""
        if price is None:
            ticker = await self.get_ticker(symbol)
            price = ticker["last"]

        cost = amount * price
        base, quote = symbol.split("/")

        if side == "buy":
            available = self._paper_balance.get(quote, {}).get("free", 0)
            if cost > available:
                raise ValueError(
                    f"Solde insuffisant: {cost:.2f} {quote} requis, "
                    f"{available:.2f} disponible"
                )
            self._paper_balance.setdefault(quote, {"free": 0, "used": 0, "total": 0})
            self._paper_balance[quote]["free"] -= cost
            self._paper_balance[quote]["total"] -= cost

            if symbol not in self._paper_positions:
                self._paper_positions[symbol] = {
                    "amount": 0, "entry_price": 0, "side": "long"
                }
            pos = self._paper_positions[symbol]
            if pos["amount"] > 0:
                total_cost = pos["entry_price"] * pos["amount"] + cost
                pos["amount"] += amount
                pos["entry_price"] = total_cost / pos["amount"]
            else:
                pos["amount"] = amount
                pos["entry_price"] = price

        elif side == "sell":
            pos = self._paper_positions.get(symbol, {})
            if pos.get("amount", 0) < amount:
                raise ValueError(
                    f"Position insuffisante: {amount} requis, "
                    f"{pos.get('amount', 0)} disponible"
                )
            pnl = (price - pos["entry_price"]) * amount
            self._paper_balance.setdefault(quote, {"free": 0, "used": 0, "total": 0})
            self._paper_balance[quote]["free"] += cost
            self._paper_balance[quote]["total"] += cost
            pos["amount"] -= amount
            if pos["amount"] <= 0:
                del self._paper_positions[symbol]

            logger.info(f"[PAPER] PnL sur {symbol}: {pnl:+.2f} {quote}")

        import uuid
        order = {
            "id": str(uuid.uuid4())[:8],
            "symbol": symbol,
            "side": side,
            "type": "market",
            "price": price,
            "amount": amount,
            "cost": cost,
            "status": "closed",
            "paper": True,
        }
        logger.info(
            f"[PAPER] {side.upper()} {amount} {symbol} @ {price:.4f} "
            f"(coût: {cost:.2f} {quote})"
        )
        return order

    def _format_order(self, order: dict) -> dict:
        return {
            "id": order.get("id"),
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "type": order.get("type"),
            "price": order.get("price") or order.get("average"),
            "amount": order.get("amount"),
            "cost": order.get("cost"),
            "status": order.get("status"),
            "paper": False,
        }
