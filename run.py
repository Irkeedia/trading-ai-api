#!/usr/bin/env python3
"""
Trading IA - Point d'entrée principal.
Système de trading autonome intelligent utilisant l'IA Gemini.

Usage:
    python run.py              # Démarre le trading autonome
    python run.py --mode paper # Mode simulation (par défaut)
    python run.py --mode live  # Mode réel (ATTENTION !)
    python run.py --dashboard  # Active le dashboard web
"""
import asyncio
import argparse
import sys
import os

# S'assurer que le répertoire du projet est dans le path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.config import AppConfig
from src.utils.logger import setup_logger
from src.core.engine import TradingEngine


def parse_args():
    parser = argparse.ArgumentParser(
        description="Trading IA - Système de trading autonome intelligent"
    )
    parser.add_argument(
        "--mode", choices=["paper", "live"], default="paper",
        help="Mode de trading: paper (simulation) ou live (réel)"
    )
    parser.add_argument(
        "--config", default="config/config.yaml",
        help="Chemin vers le fichier de configuration"
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Active le dashboard web"
    )
    parser.add_argument(
        "--exchange", default=None,
        help="Exchange à utiliser (ex: binance, kraken)"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    # Charger la configuration
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    config = AppConfig(args.config)

    # Override mode si spécifié
    if args.mode:
        config.trading.mode = args.mode.upper()
    if args.exchange:
        config.primary_exchange = args.exchange

    # Setup logger
    log = setup_logger(
        log_level=config.logging.level,
        log_file=config.logging.file,
        rotation=config.logging.rotation,
        retention=config.logging.retention,
    )

    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║          🤖 TRADING IA - Démarrage du système          ║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    if config.trading.mode == "LIVE":
        log.warning("⚠️  MODE LIVE ACTIVÉ - TRADES RÉELS !")
        log.warning("⚠️  Appuyez sur Ctrl+C dans 10 secondes pour annuler...")
        await asyncio.sleep(10)

    # Créer et initialiser le moteur
    engine = TradingEngine(config)

    try:
        await engine.initialize()

        # Dashboard en parallèle si activé
        if args.dashboard and config.dashboard.enabled:
            log.info(f"Dashboard disponible sur http://{config.dashboard.host}:{config.dashboard.port}")

        # Lancer la boucle de trading
        await engine.run()

    except KeyboardInterrupt:
        log.info("\n⛔ Interruption utilisateur")
    except Exception as e:
        log.error(f"Erreur fatale: {e}")
        import traceback
        log.error(traceback.format_exc())
    finally:
        await engine.shutdown()
        log.info("Système arrêté. À bientôt ! 👋")


if __name__ == "__main__":
    asyncio.run(main())
