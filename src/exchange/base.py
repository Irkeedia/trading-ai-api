"""
Interface abstraite pour les exchanges.
"""
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class BaseExchange(ABC):
    """Interface commune pour tous les exchanges."""

    @abstractmethod
    async def connect(self):
        """Établit la connexion à l'exchange."""
        ...

    @abstractmethod
    async def disconnect(self):
        """Ferme la connexion."""
        ...

    @abstractmethod
    async def get_balance(self) -> dict:
        """Retourne le solde du compte."""
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> dict:
        """Retourne le prix actuel d'un symbole."""
        ...

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str = "1h",
                        limit: int = 200) -> pd.DataFrame:
        """Retourne les données OHLCV sous forme de DataFrame."""
        ...

    @abstractmethod
    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Retourne le carnet d'ordres."""
        ...

    @abstractmethod
    async def create_market_buy(self, symbol: str, amount: float) -> dict:
        """Passe un ordre d'achat au marché."""
        ...

    @abstractmethod
    async def create_market_sell(self, symbol: str, amount: float) -> dict:
        """Passe un ordre de vente au marché."""
        ...

    @abstractmethod
    async def create_limit_buy(self, symbol: str, amount: float,
                               price: float) -> dict:
        """Passe un ordre d'achat limit."""
        ...

    @abstractmethod
    async def create_limit_sell(self, symbol: str, amount: float,
                                price: float) -> dict:
        """Passe un ordre de vente limit."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Annule un ordre."""
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: str = None) -> list:
        """Retourne les ordres ouverts."""
        ...

    @abstractmethod
    async def get_positions(self) -> list:
        """Retourne les positions ouvertes."""
        ...
