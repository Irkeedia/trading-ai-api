"""
Gestion du portfolio : positions, valeurs, PnL.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class Position:
    """Position individuelle."""
    symbol: str
    side: str  # "long"
    amount: float
    entry_price: float
    current_price: float = 0.0
    highest_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    opened_at: str = ""
    strategy: str = ""

    @property
    def unrealized_pnl(self) -> float:
        if self.side == "long":
            return (self.current_price - self.entry_price) * self.amount
        return 0.0

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.side == "long":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        return 0.0

    @property
    def value(self) -> float:
        return self.amount * self.current_price

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "highest_price": self.highest_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
            "value": round(self.value, 2),
            "opened_at": self.opened_at,
            "strategy": self.strategy,
        }


class Portfolio:
    """Gestion centralisée du portfolio."""

    def __init__(self):
        self.positions: dict[str, Position] = {}
        self.available_balance: float = 0.0
        self.total_realized_pnl: float = 0.0
        self.trade_history: list[dict] = []

    def update_balance(self, balance: dict, base_currency: str = "USDT"):
        """Met à jour le solde depuis les données de l'exchange."""
        if base_currency in balance:
            self.available_balance = balance[base_currency].get("free", 0)

    def open_position(self, symbol: str, amount: float, entry_price: float,
                      stop_loss: float = 0, take_profit: float = 0,
                      strategy: str = ""):
        """Ouvre une nouvelle position."""
        pos = Position(
            symbol=symbol,
            side="long",
            amount=amount,
            entry_price=entry_price,
            current_price=entry_price,
            highest_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=datetime.utcnow().isoformat(),
            strategy=strategy,
        )
        self.positions[symbol] = pos
        logger.info(
            f"Position ouverte: {symbol} | {amount} @ {entry_price} | "
            f"SL: {stop_loss} | TP: {take_profit}"
        )

    def close_position(self, symbol: str, close_price: float) -> float:
        """Ferme une position et retourne le PnL réalisé."""
        if symbol not in self.positions:
            logger.warning(f"Pas de position ouverte pour {symbol}")
            return 0.0

        pos = self.positions[symbol]
        pnl = (close_price - pos.entry_price) * pos.amount

        self.total_realized_pnl += pnl
        self.trade_history.append({
            "symbol": symbol,
            "entry_price": pos.entry_price,
            "close_price": close_price,
            "amount": pos.amount,
            "pnl": round(pnl, 2),
            "pnl_pct": round(((close_price - pos.entry_price) / pos.entry_price) * 100, 2),
            "opened_at": pos.opened_at,
            "closed_at": datetime.utcnow().isoformat(),
            "strategy": pos.strategy,
        })

        del self.positions[symbol]
        logger.info(f"Position fermée: {symbol} @ {close_price} | PnL: {pnl:+.2f}")
        return pnl

    def update_prices(self, tickers: dict):
        """Met à jour les prix courants des positions."""
        for symbol, pos in self.positions.items():
            if symbol in tickers:
                price = tickers[symbol].get("last", pos.current_price)
                pos.current_price = price
                if price > pos.highest_price:
                    pos.highest_price = price

    @property
    def total_value(self) -> float:
        positions_value = sum(p.value for p in self.positions.values())
        return self.available_balance + positions_value

    @property
    def positions_value(self) -> float:
        return sum(p.value for p in self.positions.values())

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def open_positions_count(self) -> int:
        return len(self.positions)

    def get_position(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def get_positions_list(self) -> list[dict]:
        return [p.to_dict() for p in self.positions.values()]

    def get_summary(self) -> dict:
        return {
            "total_value": round(self.total_value, 2),
            "available_balance": round(self.available_balance, 2),
            "positions_value": round(self.positions_value, 2),
            "unrealized_pnl": round(self.total_unrealized_pnl, 2),
            "realized_pnl": round(self.total_realized_pnl, 2),
            "open_positions": self.open_positions_count,
            "positions": self.get_positions_list(),
        }

    def to_json(self) -> str:
        return json.dumps(self.get_summary(), indent=2, default=str)
