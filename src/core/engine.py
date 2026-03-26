"""
Moteur de trading principal.
Orchestre tous les composants : exchange, analyse, stratégie, risque, portfolio.
"""
import asyncio
import json
from datetime import datetime
from loguru import logger

from ..exchange.ccxt_exchange import CCXTExchange
from ..analysis.technical import TechnicalAnalyzer
from ..analysis.ai_analyst import AIAnalyst
from ..analysis.sentiment import SentimentAnalyzer
from ..strategy.ai_strategy import AIStrategy
from ..core.portfolio import Portfolio
from ..core.risk_manager import RiskManager
from ..utils.database import Database
from ..utils.config import AppConfig


class TradingEngine:
    """Moteur de trading autonome."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.running = False
        self._cycle_count = 0

        # Composants
        self.exchange: CCXTExchange | None = None
        self.portfolio = Portfolio()
        self.risk_manager = RiskManager(config.risk)
        self.technical = TechnicalAnalyzer()
        self.ai_analyst: AIAnalyst | None = None
        self.sentiment = SentimentAnalyzer(
            rss_feeds=config.sentiment.rss_feeds,
            news_api_key=config.env.news_api_key,
        )
        self.strategy: AIStrategy | None = None
        self.db = Database(config.env.database_url)
        self._start_time: datetime | None = None

    async def initialize(self):
        """Initialise tous les composants."""
        logger.info("=" * 60)
        logger.info("   TRADING IA - Initialisation du système")
        logger.info("=" * 60)

        # Database
        await self.db.initialize()

        # Exchange
        creds = self.config.get_exchange_credentials(self.config.primary_exchange)
        self.exchange = CCXTExchange(
            exchange_id=self.config.primary_exchange,
            api_key=creds.get("apiKey", ""),
            secret=creds.get("secret", ""),
            sandbox=self.config.is_sandbox(self.config.primary_exchange),
            trading_mode=self.config.trading.mode,
        )
        await self.exchange.connect()

        # Balance initiale
        balance = await self.exchange.get_balance()
        self.portfolio.update_balance(balance, self.config.trading.base_currency)
        logger.info(f"Balance: {self.portfolio.available_balance:.2f} {self.config.trading.base_currency}")

        # IA Analyst
        if self.config.env.gemini_api_key:
            self.ai_analyst = AIAnalyst(
                api_key=self.config.env.gemini_api_key,
                model=self.config.ai.model,
                temperature=self.config.ai.temperature,
            )
            logger.info(f"IA Gemini activée ({self.config.ai.model})")
        else:
            logger.warning("Clé API Gemini non configurée - IA désactivée")

        # Stratégie
        if self.ai_analyst:
            self.strategy = AIStrategy(
                technical_analyzer=self.technical,
                ai_analyst=self.ai_analyst,
                sentiment_analyzer=self.sentiment,
                risk_manager=self.risk_manager,
                config=self.config,
            )

        # News initiales
        await self.sentiment.fetch_all_news()

        logger.info(f"Mode: {self.config.trading.mode}")
        logger.info(f"Exchange: {self.config.primary_exchange}")
        logger.info(f"Watchlist: {', '.join(self.config.watchlist)}")
        logger.info(f"Positions max: {self.config.trading.max_open_positions}")
        logger.info("=" * 60)
        logger.info("   Système prêt - Démarrage du trading")
        logger.info("=" * 60)
        self._start_time = datetime.utcnow()
        await self.db.update_engine_status(
            status="running",
            mode=self.config.trading.mode,
            exchange=self.config.primary_exchange,
        )

    async def run(self):
        """Boucle principale de trading."""
        self.running = True

        while self.running:
            try:
                self._cycle_count += 1
                logger.info(f"\n{'='*40} Cycle #{self._cycle_count} {'='*40}")

                # 1. Mettre à jour les données de marché
                await self._update_market_data()

                # 2. Vérifier les positions existantes
                await self._check_existing_positions()

                # 3. Chercher de nouvelles opportunités
                await self._scan_opportunities()

                # 4. Snapshot portfolio
                await self._record_snapshot()

                # 5. Mettre à jour le statut du moteur
                uptime = int((datetime.utcnow() - self._start_time).total_seconds()) if self._start_time else 0
                await self.db.update_engine_status(
                    status="running",
                    mode=self.config.trading.mode,
                    exchange=self.config.primary_exchange,
                    cycle_count=self._cycle_count,
                    uptime_seconds=uptime,
                )

                # 6. Log status
                self._log_status()

                # Attendre avant le prochain cycle
                interval = self.config.trading.check_interval_seconds
                logger.info(f"Prochain cycle dans {interval}s...")
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Arrêt demandé par l'utilisateur")
                self.running = False
            except Exception as e:
                logger.error(f"Erreur dans le cycle de trading: {e}")
                await asyncio.sleep(30)

        await self.shutdown()

    async def _update_market_data(self):
        """Met à jour les prix et données de marché."""
        # Récupérer les tickers
        symbols_to_check = list(self.config.watchlist)
        for symbol in self.portfolio.positions:
            if symbol not in symbols_to_check:
                symbols_to_check.append(symbol)

        tickers = await self.exchange.get_multiple_tickers(symbols_to_check)
        self.portfolio.update_prices(tickers)

        # Mettre à jour le solde
        balance = await self.exchange.get_balance()
        self.portfolio.update_balance(balance, self.config.trading.base_currency)

        # Mettre à jour les news périodiquement
        if self._cycle_count % 5 == 0:  # Toutes les 5 cycles
            await self.sentiment.fetch_all_news()

        logger.info(f"Données mises à jour pour {len(tickers)} symboles")

    async def _check_existing_positions(self):
        """Vérifie les positions ouvertes pour stop loss / take profit / trailing."""
        positions_to_close = []

        for symbol, pos in list(self.portfolio.positions.items()):
            check = self.risk_manager.should_close_position(
                entry_price=pos.entry_price,
                current_price=pos.current_price,
                side=pos.side,
                highest_price=pos.highest_price,
            )

            if check["close"]:
                positions_to_close.append((symbol, check["reason"]))
                logger.warning(
                    f"[{symbol}] Clôture automatique: {check['reason']} | "
                    f"Prix: {pos.current_price} | Entrée: {pos.entry_price}"
                )

        # Clôturer les positions
        for symbol, reason in positions_to_close:
            await self._close_position(symbol, reason)

    async def _scan_opportunities(self):
        """Scanne la watchlist pour trouver des opportunités."""
        if not self.strategy:
            logger.warning("Pas de stratégie IA configurée - scan ignoré")
            return

        for symbol in self.config.watchlist:
            # Skip si déjà en position
            if self.portfolio.has_position(symbol):
                continue

            # Vérifier le nombre de positions
            if self.portfolio.open_positions_count >= self.config.trading.max_open_positions:
                logger.info("Nombre max de positions atteint, pas de nouvelles opportunités")
                break

            try:
                await self._evaluate_symbol(symbol)
            except Exception as e:
                logger.error(f"Erreur évaluation {symbol}: {e}")

            # Rate limiting
            await asyncio.sleep(2)

    async def _evaluate_symbol(self, symbol: str):
        """Évalue un symbole pour un trade potentiel."""
        # Récupérer les OHLCV pour chaque timeframe
        ohlcv_data = {}
        for tf in self.config.timeframes[:3]:  # Limiter à 3 timeframes pour la vitesse
            try:
                df = await self.exchange.get_ohlcv(symbol, tf, limit=200)
                if df is not None and len(df) >= 30:
                    ohlcv_data[tf] = df
                await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                logger.warning(f"Erreur OHLCV {symbol}/{tf}: {e}")

        if not ohlcv_data:
            return

        # Ticker
        ticker = await self.exchange.get_ticker(symbol)
        price = ticker.get("last", 0)
        if price == 0:
            return

        # Evaluate avec la stratégie IA
        portfolio_ctx = (
            f"Balance: {self.portfolio.available_balance:.2f} USDT | "
            f"Positions: {self.portfolio.open_positions_count}/{self.config.trading.max_open_positions} | "
            f"PnL total: {self.portfolio.total_realized_pnl:+.2f}"
        )

        decision = await self.strategy.evaluate(
            symbol=symbol,
            ohlcv_data=ohlcv_data,
            ticker=ticker,
            portfolio_context=portfolio_ctx,
        )

        # Enregistrer le signal
        await self.db.record_signal(
            symbol=symbol,
            signal_type=decision.action,
            strength=decision.confidence,
            source="ai_strategy",
            details=decision.reasoning[:500],
        )

        # Exécuter si BUY avec confiance suffisante
        if decision.action == "BUY" and decision.confidence >= 0.5:
            await self._execute_buy(decision)

    async def _execute_buy(self, decision):
        """Exécute un ordre d'achat après validation du risk manager."""
        symbol = decision.symbol
        price = decision.price

        # Calculer la taille de position
        amount = self.risk_manager.get_position_size(
            price=price,
            stop_loss=decision.stop_loss,
            portfolio_value=self.portfolio.total_value,
        )

        if amount <= 0:
            logger.info(f"[{symbol}] Taille de position = 0, trade ignoré")
            return

        # Vérification du risk manager
        current_positions = self.portfolio.get_positions_list()
        risk_check = self.risk_manager.check_trade(
            side="buy",
            symbol=symbol,
            amount=amount,
            price=price,
            portfolio_value=self.portfolio.total_value,
            current_positions=current_positions,
            ai_confidence=decision.confidence,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            max_open_positions=self.config.trading.max_open_positions,
        )

        if not risk_check.approved:
            logger.info(f"[{symbol}] Trade refusé par Risk: {risk_check.reason}")
            return

        # Utiliser les montants ajustés
        final_amount = risk_check.adjusted_amount
        final_sl = risk_check.adjusted_stop_loss
        final_tp = risk_check.adjusted_take_profit

        # Exécuter l'ordre
        try:
            order = await self.exchange.create_market_buy(symbol, final_amount)

            # Enregistrer la position
            self.portfolio.open_position(
                symbol=symbol,
                amount=final_amount,
                entry_price=order.get("price", price),
                stop_loss=final_sl,
                take_profit=final_tp,
                strategy="ai_strategy",
            )

            # Enregistrer en base
            await self.db.record_trade(
                symbol=symbol,
                side="buy",
                price=order.get("price", price),
                amount=final_amount,
                cost=order.get("cost", final_amount * price),
                strategy="ai_strategy",
                exchange=self.config.primary_exchange,
                order_id=order.get("id", ""),
                notes=decision.reasoning[:200],
            )

            # Enregistrer l'analyse IA
            if decision.sources and "ai" in decision.sources:
                await self.db.record_ai_analysis(
                    symbol=symbol,
                    analysis_type="market_analysis",
                    provider="gemini",
                    result=json.dumps(decision.sources["ai"], default=str),
                    confidence=decision.confidence,
                )

            logger.info(
                f"✅ ACHAT EXÉCUTÉ: {final_amount:.6f} {symbol} @ {price:.4f} | "
                f"SL: {final_sl:.4f} | TP: {final_tp:.4f} | "
                f"Risque: {risk_check.risk_score:.2f}"
            )

        except Exception as e:
            logger.error(f"Erreur exécution achat {symbol}: {e}")

    async def _close_position(self, symbol: str, reason: str):
        """Ferme une position."""
        pos = self.portfolio.get_position(symbol)
        if not pos:
            return

        try:
            order = await self.exchange.create_market_sell(symbol, pos.amount)
            close_price = order.get("price", pos.current_price)
            pnl = self.portfolio.close_position(symbol, close_price)

            # Enregistrer en base
            await self.db.record_trade(
                symbol=symbol,
                side="sell",
                price=close_price,
                amount=pos.amount,
                cost=order.get("cost", pos.amount * close_price),
                pnl=pnl,
                strategy=pos.strategy,
                exchange=self.config.primary_exchange,
                order_id=order.get("id", ""),
                notes=reason,
            )

            # Notifier le risk manager
            if pnl < 0:
                self.risk_manager.record_loss(abs(pnl))
            else:
                self.risk_manager.record_win(pnl)

            logger.info(
                f"{'✅' if pnl >= 0 else '❌'} VENTE: {symbol} | "
                f"PnL: {pnl:+.2f} USDT | Raison: {reason}"
            )

        except Exception as e:
            logger.error(f"Erreur fermeture position {symbol}: {e}")

    async def _record_snapshot(self):
        """Enregistre un snapshot du portfolio."""
        await self.db.record_portfolio_snapshot(
            total_value=self.portfolio.total_value,
            available=self.portfolio.available_balance,
            positions_value=self.portfolio.positions_value,
            daily_pnl=await self.db.get_daily_pnl(),
            total_pnl=self.portfolio.total_realized_pnl,
            positions_json=self.portfolio.to_json(),
        )

    def _log_status(self):
        """Affiche le statut actuel."""
        summary = self.portfolio.get_summary()
        risk_status = self.risk_manager.get_status()

        logger.info(f"\n{'─'*50}")
        logger.info(f"📊 PORTFOLIO: {summary['total_value']:.2f} USDT")
        logger.info(f"   Balance libre: {summary['available_balance']:.2f} USDT")
        logger.info(f"   En positions: {summary['positions_value']:.2f} USDT")
        logger.info(f"   PnL non réalisé: {summary['unrealized_pnl']:+.2f} USDT")
        logger.info(f"   PnL réalisé: {summary['realized_pnl']:+.2f} USDT")
        logger.info(f"   Positions: {summary['open_positions']}/{self.config.trading.max_open_positions}")

        for pos in summary["positions"]:
            logger.info(
                f"   └ {pos['symbol']}: {pos['amount']:.6f} @ {pos['entry_price']:.4f} "
                f"→ {pos['current_price']:.4f} ({pos['unrealized_pnl_pct']:+.2f}%)"
            )

        logger.info(f"🛡️  RISQUE: Pertes jour: {risk_status['daily_losses']:.2f} | "
                    f"Trades: {risk_status['trade_count_today']} | "
                    f"Cooldown: {'OUI' if risk_status['cooldown_active'] else 'NON'}")
        logger.info(f"{'─'*50}")

    async def shutdown(self):
        """Arrêt propre du système."""
        logger.info("Arrêt du système de trading...")
        self.running = False

        if self.exchange:
            await self.exchange.disconnect()

        await self.db.update_engine_status(status="stopped")
        await self.db.close()
        logger.info("Système arrêté proprement")

    async def manual_buy(self, symbol: str, amount: float = None):
        """Achat manuel (pour tests)."""
        ticker = await self.exchange.get_ticker(symbol)
        price = ticker["last"]

        if amount is None:
            amount = self.risk_manager.get_position_size(
                price, price * 0.97, self.portfolio.total_value
            )

        order = await self.exchange.create_market_buy(symbol, amount)
        self.portfolio.open_position(
            symbol=symbol, amount=amount,
            entry_price=price,
            stop_loss=price * (1 - self.config.risk.stop_loss_pct / 100),
            take_profit=price * (1 + self.config.risk.take_profit_pct / 100),
            strategy="manual",
        )
        return order

    async def manual_sell(self, symbol: str):
        """Vente manuelle (pour tests)."""
        pos = self.portfolio.get_position(symbol)
        if not pos:
            logger.warning(f"Pas de position pour {symbol}")
            return None
        await self._close_position(symbol, "Vente manuelle")
