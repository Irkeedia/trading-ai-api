"""
Injecte des données de démonstration dans la base pour tester le dashboard.
"""
import asyncio
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from src.utils.config import AppConfig
from src.utils.database import Database


async def seed():
    config = AppConfig("config/config.yaml")
    db = Database(config.env.database_url)
    await db.initialize()
    print("✅ Connexion BDD OK, injection des données de démo...")

    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
    now = datetime.utcnow()

    # --- Trades (30 trades sur les 7 derniers jours) ---
    for i in range(30):
        ts = now - timedelta(hours=random.randint(1, 168))
        sym = random.choice(symbols)
        side = random.choice(["buy", "sell"])
        price = {
            "BTC/USDT": random.uniform(60000, 70000),
            "ETH/USDT": random.uniform(3200, 4000),
            "SOL/USDT": random.uniform(120, 190),
            "BNB/USDT": random.uniform(550, 700),
            "XRP/USDT": random.uniform(0.5, 1.2),
        }[sym]
        amount = random.uniform(0.001, 0.5)
        pnl = random.uniform(-50, 120) if side == "sell" else 0

        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO trades (timestamp, symbol, side, price, amount, cost, pnl, strategy, exchange)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                ts, sym, side, price, amount, price * amount, pnl, "ai_strategy", "binance"
            )
    print(f"  📊 30 trades injectés")

    # --- Signals (20) ---
    for i in range(20):
        ts = now - timedelta(hours=random.randint(0, 48))
        sym = random.choice(symbols)
        sig_type = random.choice(["BUY", "SELL", "HOLD"])
        strength = random.uniform(0.2, 0.95)

        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO signals (timestamp, symbol, signal_type, strength, source, timeframe, details)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                ts, sym, sig_type, strength, "ai_strategy", random.choice(["1h", "4h", "1d"]),
                f"RSI={random.uniform(20,80):.1f}, MACD bullish, EMA cross up"
            )
    print(f"  📡 20 signaux injectés")

    # --- Portfolio snapshots (7 jours, 1 par heure) ---
    base_value = 10000
    for h in range(168):
        ts = now - timedelta(hours=168 - h)
        change = random.uniform(-80, 100)
        base_value += change
        base_value = max(base_value, 5000)
        positions_val = base_value * random.uniform(0.1, 0.4)
        available = base_value - positions_val
        daily_pnl = random.uniform(-150, 200)
        total_pnl = base_value - 10000

        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO portfolio_snapshots 
                   (timestamp, total_value_usdt, available_balance, positions_value, daily_pnl, total_pnl, positions_json)
                   VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
                ts, base_value, available, positions_val, daily_pnl, total_pnl, "{}"
            )
    print(f"  📈 168 snapshots portfolio (7 jours)")

    # --- AI Analyses (10) ---
    import json
    for i in range(10):
        ts = now - timedelta(hours=random.randint(0, 72))
        sym = random.choice(symbols)
        action = random.choice(["BUY", "SELL", "HOLD"])
        confidence = random.uniform(0.4, 0.95)
        result = json.dumps({
            "action": action,
            "confidence": round(confidence, 2),
            "reasoning": f"Analyse technique montre un momentum {random.choice(['haussier', 'baissier', 'neutre'])}. "
                         f"RSI à {random.uniform(25, 75):.0f}, MACD {"positif" if action == "BUY" else "négatif"}. "
                         f"Volume en {"hausse" if random.random() > 0.5 else "baisse"} sur les 4 dernières heures.",
            "stop_loss": round(random.uniform(0.02, 0.05), 3),
            "take_profit": round(random.uniform(0.04, 0.10), 3),
        })
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO ai_analyses (timestamp, symbol, analysis_type, provider, result, confidence, tokens_used)
                   VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)""",
                ts, sym, "market_analysis", "gemini", result, confidence, random.randint(500, 2000)
            )
    print(f"  🤖 10 analyses IA injectées")

    # --- News (15) ---
    news_titles = [
        "Bitcoin franchit les 65 000$ dans un contexte de demande institutionnelle",
        "Ethereum 2.0 : les stakers dépassent les 30 millions d'ETH",
        "Solana atteint un nouveau ATH grâce à l'écosystème DeFi",
        "La SEC approuve un nouvel ETF crypto spot",
        "Binance annonce de nouvelles mesures de conformité",
        "Le marché crypto en hausse après les déclarations de la Fed",
        "XRP gagne 15% suite à une décision judiciaire favorable",
        "L'adoption crypto accélère en Asie du Sud-Est",
        "DeFi TVL dépasse les 100 milliards de dollars",
        "Nouvelle régulation crypto en Europe : ce qui change",
        "Bitcoin mining : la difficulté atteint un record",
        "Avalanche lance un programme de 100M$ pour les développeurs",
        "Polygon : le bridge zkEVM dépasse 1 milliard de transactions",
        "Chainlink CCIP : adoption massive par les institutions",
        "Le volume des DEX explose au T1 2025",
    ]
    for title in news_titles:
        ts = now - timedelta(hours=random.randint(0, 96))
        sentiment = random.uniform(-0.5, 0.8)
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO news_items (timestamp, title, source, url, sentiment_score, relevance_score, related_symbols)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                ts, title, random.choice(["CoinTelegraph", "CoinDesk", "Decrypt"]),
                "https://example.com", sentiment, random.uniform(0.3, 1.0),
                random.choice(["BTC", "ETH", "SOL", "BNB", "XRP"])
            )
    print(f"  📰 15 news injectées")

    # --- Engine status ---
    async with db.pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO engine_status (timestamp, status, mode, exchange, cycle_count, uptime_seconds)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            now, "running", "PAPER", "binance", 42, 7200
        )
    print(f"  ⚙️  Statut moteur injecté")

    await db.close()
    print("\n✅ Données de démo injectées avec succès !")
    print("   Vous pouvez maintenant voir le dashboard rempli.")


if __name__ == "__main__":
    asyncio.run(seed())
