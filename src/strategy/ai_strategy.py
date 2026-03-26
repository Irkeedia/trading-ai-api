"""
Stratégie de trading IA.
Combine analyse technique, sentiment, et IA Gemini pour prendre des décisions.
"""
import asyncio
from dataclasses import dataclass
from loguru import logger


@dataclass
class TradeDecision:
    """Décision de trading complète."""
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float
    amount: float = 0.0
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reasoning: str = ""
    sources: dict = None  # tech, ai, sentiment


class AIStrategy:
    """Stratégie de trading combinant TA + IA + Sentiment."""

    def __init__(self, technical_analyzer, ai_analyst, sentiment_analyzer,
                 risk_manager, config):
        self.ta = technical_analyzer
        self.ai = ai_analyst
        self.sentiment = sentiment_analyzer
        self.risk = risk_manager
        self.config = config

        # Pondération des sources
        self.weights = {
            "technical": 0.35,
            "ai": 0.45,
            "sentiment": 0.20,
        }

    async def evaluate(self, symbol: str, ohlcv_data: dict,
                       ticker: dict, portfolio_context: str = "") -> TradeDecision:
        """Évalue un symbole et retourne une décision de trading."""
        price = ticker.get("last", 0)
        if price == 0:
            return TradeDecision(symbol=symbol, action="HOLD", confidence=0,
                                 reasoning="Prix indisponible")

        # 1. Analyse technique multi-timeframe
        tech_results = {}
        for tf, df in ohlcv_data.items():
            tech_results[tf] = self.ta.analyze(df, symbol, tf)

        tech_summary = self._summarize_technical(tech_results)

        # 2. Résumé news/sentiment
        news_summary = self.sentiment.get_news_summary(symbol)

        # 3. Analyse IA Gemini
        ai_result = await self.ai.analyze_market(
            symbol=symbol,
            technical_summary=tech_summary["text"],
            current_price=price,
            ticker_data=ticker,
            news_summary=news_summary,
            portfolio_context=portfolio_context,
        )

        # 4. Combiner les signaux
        decision = self._combine_signals(
            symbol=symbol,
            price=price,
            tech=tech_summary,
            ai=ai_result,
            ticker=ticker,
        )

        return decision

    def _summarize_technical(self, results: dict) -> dict:
        """Résume les résultats techniques de tous les timeframes."""
        buy_count = 0
        sell_count = 0
        neutral_count = 0
        total_strength = 0
        details = []

        for tf, summary in results.items():
            sig = summary.overall_signal
            strength = summary.overall_strength

            if sig == "BUY":
                buy_count += 1
                total_strength += strength
            elif sig == "SELL":
                sell_count += 1
                total_strength -= strength
            else:
                neutral_count += 1

            details.append(f"{tf}: {sig} (force: {strength:.2f})")
            for s in summary.signals[:3]:
                details.append(f"  └ {s.indicator}: {s.signal} - {s.details}")

        total = buy_count + sell_count + neutral_count
        if total == 0:
            overall = "NEUTRAL"
            score = 0
        elif buy_count > sell_count and buy_count > neutral_count:
            overall = "BUY"
            score = total_strength / total
        elif sell_count > buy_count and sell_count > neutral_count:
            overall = "SELL"
            score = total_strength / total
        else:
            overall = "NEUTRAL"
            score = 0

        text = f"Signal Global: {overall}\n"
        text += f"BUY: {buy_count} | SELL: {sell_count} | NEUTRAL: {neutral_count}\n"
        text += "\n".join(details)

        return {
            "signal": overall,
            "score": score,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "neutral_count": neutral_count,
            "text": text,
        }

    def _combine_signals(self, symbol: str, price: float,
                          tech: dict, ai: dict, ticker: dict) -> TradeDecision:
        """Combine l'analyse technique, IA et sentiment en une décision finale."""

        # Score technique normalisé (-1 à +1)
        tech_signal = tech["signal"]
        if tech_signal == "BUY":
            tech_score = abs(tech.get("score", 0.5))
        elif tech_signal == "SELL":
            tech_score = -abs(tech.get("score", 0.5))
        else:
            tech_score = 0

        # Score IA normalisé (-1 à +1)
        ai_action = ai.get("action", "HOLD")
        ai_confidence = ai.get("confidence", 0)
        if ai_action == "BUY":
            ai_score = ai_confidence
        elif ai_action == "SELL":
            ai_score = -ai_confidence
        else:
            ai_score = 0

        # Score sentiment (simplifié basé sur les news)
        sentiment_score = 0  # Sera enrichi par l'interprétation IA des news

        # Score combiné pondéré
        combined_score = (
            tech_score * self.weights["technical"] +
            ai_score * self.weights["ai"] +
            sentiment_score * self.weights["sentiment"]
        )

        # Seuils de décision
        if combined_score > 0.3:
            action = "BUY"
            confidence = min(abs(combined_score), 1.0)
        elif combined_score < -0.3:
            action = "SELL"
            confidence = min(abs(combined_score), 1.0)
        else:
            action = "HOLD"
            confidence = 1.0 - abs(combined_score)

        # Calculer les niveaux si c'est un BUY
        stop_loss = ai.get("stop_loss") or price * (1 - self.risk.stop_loss_pct / 100)
        take_profit = ai.get("take_profit") or price * (1 + self.risk.take_profit_pct / 100)

        # Taille de position basée sur le risque
        amount = 0.0
        if action == "BUY":
            amount = self.risk.get_position_size(price, stop_loss, 0)  # sera ajusté par l'engine

        reasoning = (
            f"Score combiné: {combined_score:+.3f} | "
            f"Tech: {tech_signal} ({tech_score:+.2f}) | "
            f"IA: {ai_action} (conf: {ai_confidence:.2f}) | "
            f"Sentiment: {sentiment_score:+.2f}\n"
            f"Raison IA: {ai.get('reasoning', 'N/A')}"
        )

        if ai.get("warnings"):
            reasoning += f"\nAvertissements: {', '.join(ai['warnings'])}"

        decision = TradeDecision(
            symbol=symbol,
            action=action,
            confidence=confidence,
            amount=amount,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            sources={"technical": tech, "ai": ai},
        )

        logger.info(
            f"[{symbol}] Décision: {action} (confiance: {confidence:.2f}) | "
            f"Score: {combined_score:+.3f}"
        )

        return decision
