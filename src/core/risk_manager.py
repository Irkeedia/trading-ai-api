"""
Gestionnaire de risque.
Contrôle toutes les décisions de trading pour protéger le capital.
"""
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class RiskCheck:
    """Résultat d'une vérification de risque."""
    approved: bool
    reason: str
    adjusted_amount: float = 0.0
    adjusted_stop_loss: float = 0.0
    adjusted_take_profit: float = 0.0
    risk_score: float = 0.0  # 0 = très sûr, 1 = très risqué


class RiskManager:
    """Gestionnaire de risque pour contrôler les trades."""

    def __init__(self, config):
        self.max_portfolio_risk_pct = config.max_portfolio_risk_pct
        self.max_position_size_pct = config.max_position_size_pct
        self.stop_loss_pct = config.stop_loss_pct
        self.take_profit_pct = config.take_profit_pct
        self.trailing_stop_pct = config.trailing_stop_pct
        self.max_daily_loss_pct = config.max_daily_loss_pct
        self.min_risk_reward_ratio = config.min_risk_reward_ratio
        self.cooldown_minutes = config.cooldown_after_loss_minutes

        self._daily_losses = 0.0
        self._last_loss_time: datetime | None = None
        self._trade_count_today = 0
        self._day_start = datetime.utcnow().date()

    def check_trade(self, side: str, symbol: str, amount: float,
                    price: float, portfolio_value: float,
                    current_positions: list,
                    ai_confidence: float = 0.5,
                    stop_loss: float = None,
                    take_profit: float = None,
                    max_open_positions: int = 5) -> RiskCheck:
        """Vérifie si un trade est autorisé selon les règles de risque."""

        # Reset compteurs journaliers si nouveau jour
        today = datetime.utcnow().date()
        if today != self._day_start:
            self._daily_losses = 0.0
            self._trade_count_today = 0
            self._day_start = today

        cost = amount * price

        # 1. Vérifier le cooldown après perte
        if self._last_loss_time:
            cooldown_end = self._last_loss_time + timedelta(minutes=self.cooldown_minutes)
            if datetime.utcnow() < cooldown_end:
                remaining = (cooldown_end - datetime.utcnow()).seconds // 60
                return RiskCheck(
                    approved=False,
                    reason=f"Cooldown actif après perte ({remaining}min restantes)"
                )

        # 2. Vérifier la perte journalière max
        if portfolio_value > 0:
            daily_loss_pct = (self._daily_losses / portfolio_value) * 100
            if daily_loss_pct >= self.max_daily_loss_pct:
                return RiskCheck(
                    approved=False,
                    reason=f"Perte journalière max atteinte ({daily_loss_pct:.1f}% >= {self.max_daily_loss_pct}%)"
                )

        # 3. Vérifier le nombre de positions ouvertes
        if side == "buy" and len(current_positions) >= max_open_positions:
            return RiskCheck(
                approved=False,
                reason=f"Nombre max de positions atteint ({len(current_positions)}/{max_open_positions})"
            )

        # 4. Vérifier la taille de position
        if portfolio_value > 0:
            position_pct = (cost / portfolio_value) * 100
            if position_pct > self.max_position_size_pct:
                adjusted_cost = portfolio_value * (self.max_position_size_pct / 100)
                adjusted_amount = adjusted_cost / price
                logger.warning(
                    f"Position réduite: {position_pct:.1f}% → {self.max_position_size_pct}% "
                    f"({amount:.6f} → {adjusted_amount:.6f})"
                )
                amount = adjusted_amount
                cost = amount * price

        # 5. Calculer stop loss et take profit si non fournis
        if stop_loss is None:
            if side == "buy":
                stop_loss = price * (1 - self.stop_loss_pct / 100)
            else:
                stop_loss = price * (1 + self.stop_loss_pct / 100)

        if take_profit is None:
            if side == "buy":
                take_profit = price * (1 + self.take_profit_pct / 100)
            else:
                take_profit = price * (1 - self.take_profit_pct / 100)

        # 6. Vérifier le ratio risque/récompense
        if side == "buy":
            risk = price - stop_loss
            reward = take_profit - price
        else:
            risk = stop_loss - price
            reward = price - take_profit

        if risk > 0:
            rr_ratio = reward / risk
            if rr_ratio < self.min_risk_reward_ratio:
                return RiskCheck(
                    approved=False,
                    reason=(
                        f"Ratio R/R insuffisant ({rr_ratio:.2f} < {self.min_risk_reward_ratio}). "
                        f"Risque: {risk:.4f}, Récompense: {reward:.4f}"
                    )
                )

        # 7. Vérifier le risque par rapport au portfolio
        potential_loss = amount * abs(price - stop_loss)
        if portfolio_value > 0:
            risk_pct = (potential_loss / portfolio_value) * 100
            if risk_pct > self.max_portfolio_risk_pct:
                max_loss = portfolio_value * (self.max_portfolio_risk_pct / 100)
                if abs(price - stop_loss) > 0:
                    adjusted_amount = max_loss / abs(price - stop_loss)
                    logger.warning(
                        f"Risque réduit: {risk_pct:.1f}% → {self.max_portfolio_risk_pct}% "
                        f"(amount: {amount:.6f} → {adjusted_amount:.6f})"
                    )
                    amount = adjusted_amount

        # 8. Vérifier la confiance IA
        if ai_confidence < 0.3:
            return RiskCheck(
                approved=False,
                reason=f"Confiance IA trop faible ({ai_confidence:.2f} < 0.30)"
            )

        # 9. Calculer le risk score
        risk_score = self._calculate_risk_score(
            ai_confidence, cost, portfolio_value,
            len(current_positions), max_open_positions
        )

        return RiskCheck(
            approved=True,
            reason="Trade approuvé",
            adjusted_amount=amount,
            adjusted_stop_loss=stop_loss,
            adjusted_take_profit=take_profit,
            risk_score=risk_score,
        )

    def record_loss(self, loss_amount: float):
        """Enregistre une perte pour le suivi journalier."""
        self._daily_losses += abs(loss_amount)
        self._last_loss_time = datetime.utcnow()
        self._trade_count_today += 1
        logger.warning(f"Perte enregistrée: {loss_amount:.2f} | Total jour: {self._daily_losses:.2f}")

    def record_win(self, profit_amount: float):
        """Enregistre un gain."""
        self._trade_count_today += 1
        logger.info(f"Gain: +{profit_amount:.2f}")

    def _calculate_risk_score(self, confidence: float, cost: float,
                               portfolio_value: float,
                               current_positions: int,
                               max_positions: int) -> float:
        """Calcule un score de risque global (0 = sûr, 1 = risqué)."""
        scores = []

        # Taille de position relative
        if portfolio_value > 0:
            size_score = cost / portfolio_value
            scores.append(size_score * 2)

        # Confiance IA inverse
        scores.append(1 - confidence)

        # Concentration des positions
        if max_positions > 0:
            scores.append(current_positions / max_positions)

        # Pertes journalières
        if portfolio_value > 0:
            daily_score = self._daily_losses / (portfolio_value * self.max_daily_loss_pct / 100)
            scores.append(min(daily_score, 1.0))

        return sum(scores) / len(scores) if scores else 0.5

    def get_position_size(self, price: float, stop_loss: float,
                          portfolio_value: float) -> float:
        """Calcule la taille de position optimale (méthode de Kelly modifiée)."""
        risk_per_unit = abs(price - stop_loss)
        if risk_per_unit == 0:
            return 0

        max_risk_amount = portfolio_value * (self.max_portfolio_risk_pct / 100)
        amount = max_risk_amount / risk_per_unit

        max_position_cost = portfolio_value * (self.max_position_size_pct / 100)
        max_amount = max_position_cost / price

        return min(amount, max_amount)

    def should_close_position(self, entry_price: float, current_price: float,
                               side: str, highest_price: float = None) -> dict:
        """Vérifie si une position doit être clôturée (stop loss / trailing stop)."""
        if side == "long" or side == "buy":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Stop loss
            if pnl_pct <= -self.stop_loss_pct:
                return {"close": True, "reason": f"Stop loss atteint ({pnl_pct:.2f}%)"}

            # Take profit
            if pnl_pct >= self.take_profit_pct:
                return {"close": True, "reason": f"Take profit atteint ({pnl_pct:.2f}%)"}

            # Trailing stop
            if highest_price and highest_price > entry_price:
                trail_pct = ((current_price - highest_price) / highest_price) * 100
                if trail_pct <= -self.trailing_stop_pct:
                    return {"close": True, "reason": f"Trailing stop ({trail_pct:.2f}% depuis le plus haut)"}

        return {"close": False, "reason": "Position dans les limites"}

    def get_status(self) -> dict:
        """Retourne l'état du gestionnaire de risque."""
        return {
            "daily_losses": self._daily_losses,
            "trade_count_today": self._trade_count_today,
            "cooldown_active": self._last_loss_time is not None and
                              datetime.utcnow() < self._last_loss_time + timedelta(minutes=self.cooldown_minutes),
            "limits": {
                "max_portfolio_risk_pct": self.max_portfolio_risk_pct,
                "max_position_size_pct": self.max_position_size_pct,
                "stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
                "max_daily_loss_pct": self.max_daily_loss_pct,
            }
        }
