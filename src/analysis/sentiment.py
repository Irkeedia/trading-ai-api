"""
Analyse de sentiment via news et flux RSS.
Collecte et analyse les actualités crypto pour détecter le sentiment du marché.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
import feedparser
from loguru import logger


class SentimentAnalyzer:
    """Collecte et analyse le sentiment du marché à partir de news et RSS."""

    def __init__(self, rss_feeds: list[str] = None, news_api_key: str = ""):
        self.rss_feeds = rss_feeds or [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://decrypt.co/feed",
        ]
        self.news_api_key = news_api_key
        self._cache: list[dict] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=10)

    async def fetch_all_news(self, force: bool = False) -> list[dict]:
        """Récupère toutes les news depuis les sources configurées."""
        if (not force and self._last_fetch and
                datetime.utcnow() - self._last_fetch < self._cache_duration):
            return self._cache

        all_news = []

        rss_news = await self._fetch_rss_feeds()
        all_news.extend(rss_news)

        if self.news_api_key:
            api_news = await self._fetch_cryptopanic()
            all_news.extend(api_news)

        all_news.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        self._cache = all_news[:100]
        self._last_fetch = datetime.utcnow()

        logger.info(f"News collectées: {len(all_news)} articles")
        return self._cache

    async def _fetch_rss_feeds(self) -> list[dict]:
        """Parse les flux RSS."""
        news = []

        async with aiohttp.ClientSession() as session:
            for feed_url in self.rss_feeds:
                try:
                    async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            feed = feedparser.parse(content)
                            for entry in feed.entries[:15]:
                                published = ""
                                if hasattr(entry, "published"):
                                    published = entry.published
                                elif hasattr(entry, "updated"):
                                    published = entry.updated

                                news.append({
                                    "title": entry.get("title", ""),
                                    "summary": entry.get("summary", "")[:500],
                                    "url": entry.get("link", ""),
                                    "source": feed.feed.get("title", feed_url),
                                    "timestamp": published,
                                    "type": "rss",
                                })
                except Exception as e:
                    logger.warning(f"Erreur RSS {feed_url}: {e}")

        return news

    async def _fetch_cryptopanic(self) -> list[dict]:
        """Récupère les news depuis CryptoPanic API."""
        if not self.news_api_key:
            return []

        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={self.news_api_key}&kind=news&filter=important"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return [
                            {
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "source": item.get("source", {}).get("title", "CryptoPanic"),
                                "timestamp": item.get("published_at", ""),
                                "sentiment": item.get("votes", {}),
                                "currencies": [c["code"] for c in item.get("currencies", [])],
                                "type": "cryptopanic",
                            }
                            for item in data.get("results", [])[:20]
                        ]
        except Exception as e:
            logger.warning(f"Erreur CryptoPanic API: {e}")

        return []

    def get_news_for_symbol(self, symbol: str) -> list[dict]:
        """Filtre les news pertinentes pour un symbole donné."""
        base = symbol.split("/")[0].upper()
        keywords = self._symbol_keywords(base)

        relevant = []
        for news in self._cache:
            title_lower = news.get("title", "").lower()
            summary_lower = news.get("summary", "").lower()
            text = f"{title_lower} {summary_lower}"

            if any(kw.lower() in text for kw in keywords):
                relevant.append(news)
            elif "currencies" in news:
                if base in news["currencies"]:
                    relevant.append(news)

        return relevant[:10]

    def get_news_summary(self, symbol: str = None) -> str:
        """Génère un résumé textuel des news pour l'IA."""
        if symbol:
            news = self.get_news_for_symbol(symbol)
        else:
            news = self._cache[:15]

        if not news:
            return "Aucune actualité récente."

        lines = []
        for i, n in enumerate(news[:10], 1):
            source = n.get("source", "Unknown")
            title = n.get("title", "")
            lines.append(f"{i}. [{source}] {title}")

        return "\n".join(lines)

    def _symbol_keywords(self, base: str) -> list[str]:
        """Retourne les mots-clés associés à un symbole."""
        keyword_map = {
            "BTC": ["bitcoin", "btc", "satoshi"],
            "ETH": ["ethereum", "eth", "vitalik", "merge"],
            "SOL": ["solana", "sol"],
            "BNB": ["binance", "bnb"],
            "XRP": ["ripple", "xrp", "sec"],
            "ADA": ["cardano", "ada"],
            "AVAX": ["avalanche", "avax"],
            "DOT": ["polkadot", "dot"],
            "LINK": ["chainlink", "link", "oracle"],
            "MATIC": ["polygon", "matic"],
        }
        return keyword_map.get(base, [base.lower()])
