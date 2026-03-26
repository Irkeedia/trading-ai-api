"""
Analyse IA via Google Gemini (SDK google-genai).
Interprète les données de marché, l'analyse technique, et les news
pour générer des recommandations de trading intelligentes.
"""
import json
from datetime import datetime
from google import genai
from google.genai import types
from loguru import logger


class AIAnalyst:
    """Analyste IA utilisant Gemini pour l'interprétation avancée du marché."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 temperature: float = 0.3):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.temperature = temperature
        self.system_instruction = self._system_prompt()
        logger.info(f"IA Analyste initialisé avec {model}")

    def _system_prompt(self) -> str:
        return """Tu es un analyste de trading quantitatif expert spécialisé dans les cryptomonnaies.
Ton rôle est d'analyser les données de marché et de fournir des recommandations de trading précises.

RÈGLES STRICTES:
1. Tu réponds UNIQUEMENT en JSON valide
2. Tu es objectif et basé sur les données
3. Tu prends en compte le risque avant tout
4. Tu ne recommandes jamais d'investir plus que ce que le risk management autorise
5. Tu donnes une confiance entre 0.0 et 1.0
6. Tu identifies les niveaux clés de support/résistance
7. Tu prends en compte le sentiment de marché quand disponible

FORMAT DE RÉPONSE OBLIGATOIRE:
{
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "explication courte",
    "entry_price": number | null,
    "stop_loss": number | null,
    "take_profit": number | null,
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "timeframe": "short" | "medium" | "long",
    "key_factors": ["facteur1", "facteur2", ...],
    "warnings": ["avertissement1", ...]
}"""

    async def _generate(self, prompt: str) -> str:
        """Appel à Gemini et extraction du texte de réponse."""
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=self.temperature,
                max_output_tokens=4096,
            ),
        )
        return response.text.strip()

    def _parse_json(self, text: str) -> dict:
        """Parse une réponse JSON potentiellement enveloppée dans des backticks."""
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)

    async def analyze_market(self, symbol: str,
                             technical_summary: str,
                             current_price: float,
                             ticker_data: dict,
                             news_summary: str = "",
                             portfolio_context: str = "") -> dict:
        """Analyse complète d'un actif par l'IA."""
        prompt = f"""Analyse le marché pour {symbol}.

PRIX ACTUEL: {current_price}
VARIATION 24H: {ticker_data.get('change_pct', 'N/A')}%
VOLUME 24H: {ticker_data.get('volume', 'N/A')}
HIGH 24H: {ticker_data.get('high', 'N/A')}
LOW 24H: {ticker_data.get('low', 'N/A')}

ANALYSE TECHNIQUE:
{technical_summary}

ACTUALITÉS ET SENTIMENT:
{news_summary if news_summary else 'Aucune actualité récente disponible.'}

CONTEXTE PORTFOLIO:
{portfolio_context if portfolio_context else 'Portfolio standard, gestion de risque active.'}

Donne ta recommandation en JSON."""

        try:
            result_text = await self._generate(prompt)
            result = self._parse_json(result_text)

            required_keys = ["action", "confidence", "reasoning"]
            for key in required_keys:
                if key not in result:
                    result[key] = ("HOLD" if key == "action"
                                   else (0.0 if key == "confidence"
                                         else "Données insuffisantes"))

            logger.info(
                f"IA Analyse {symbol}: {result['action']} "
                f"(confiance: {result['confidence']:.2f})"
            )

            result["_meta"] = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "model": self.model_name,
            }

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON IA pour {symbol}: {e}")
            return self._fallback_response(symbol, str(e))
        except Exception as e:
            logger.error(f"Erreur IA pour {symbol}: {e}")
            return self._fallback_response(symbol, str(e))

    async def analyze_portfolio(self, positions: list,
                                 market_overview: str,
                                 total_value: float,
                                 daily_pnl: float) -> dict:
        """Analyse globale du portfolio."""
        prompt = f"""Analyse ce portfolio de trading crypto et donne des recommandations.

VALEUR TOTALE: {total_value} USDT
PnL JOURNALIER: {daily_pnl:+.2f} USDT

POSITIONS OUVERTES:
{json.dumps(positions, indent=2, default=str)}

APERÇU DU MARCHÉ:
{market_overview}

Réponds en JSON avec:
{{
    "portfolio_health": "GOOD" | "WARNING" | "DANGER",
    "risk_level": "LOW" | "MEDIUM" | "HIGH",
    "recommendations": ["action1", "action2", ...],
    "positions_to_close": ["symbol1", ...],
    "positions_to_reduce": ["symbol1", ...],
    "rebalancing_needed": true | false,
    "reasoning": "explication"
}}"""

        try:
            result_text = await self._generate(prompt)
            return self._parse_json(result_text)
        except Exception as e:
            logger.error(f"Erreur analyse portfolio IA: {e}")
            return {
                "portfolio_health": "WARNING",
                "risk_level": "MEDIUM",
                "recommendations": ["Vérifier manuellement - erreur IA"],
                "reasoning": str(e),
            }

    async def interpret_news(self, news_items: list[dict],
                              symbols: list[str]) -> dict:
        """Interprète l'impact de news sur les symboles surveillés."""
        prompt = f"""Analyse ces actualités crypto et leur impact potentiel sur le marché.

ACTUALITÉS:
{json.dumps(news_items[:10], indent=2, default=str)}

SYMBOLES SURVEILLÉS: {', '.join(symbols)}

Réponds en JSON avec:
{{
    "overall_sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
    "sentiment_score": -1.0 à 1.0,
    "impacted_symbols": {{
        "SYMBOL": {{
            "impact": "POSITIVE" | "NEGATIVE" | "NEUTRAL",
            "magnitude": "LOW" | "MEDIUM" | "HIGH",
            "reason": "explication"
        }}
    }},
    "market_moving_news": ["titre1", ...],
    "summary": "résumé en 2-3 phrases"
}}"""

        try:
            result_text = await self._generate(prompt)
            return self._parse_json(result_text)
        except Exception as e:
            logger.error(f"Erreur interprétation news IA: {e}")
            return {
                "overall_sentiment": "NEUTRAL",
                "sentiment_score": 0.0,
                "impacted_symbols": {},
                "summary": f"Erreur d'analyse: {e}",
            }

    def _fallback_response(self, symbol: str, error: str) -> dict:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reasoning": f"Erreur IA - pas de recommandation ({error})",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_level": "HIGH",
            "timeframe": "short",
            "key_factors": ["Erreur technique"],
            "warnings": ["L'IA n'a pas pu analyser - prudence maximale"],
            "_meta": {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "model": self.model_name,
                "error": error,
            },
        }