"""
Analyse technique avancée avec pandas-ta.
Calcule tous les indicateurs majeurs et génère des signaux.
"""
import pandas as pd
import pandas_ta as ta
import numpy as np
from loguru import logger
from dataclasses import dataclass, field


@dataclass
class TechnicalSignal:
    """Signal d'analyse technique."""
    indicator: str
    signal: str  # "BUY", "SELL", "NEUTRAL"
    strength: float  # 0.0 à 1.0
    value: float
    details: str = ""


@dataclass
class TechnicalSummary:
    """Résumé complet de l'analyse technique."""
    symbol: str
    timeframe: str
    signals: list = field(default_factory=list)
    overall_signal: str = "NEUTRAL"
    overall_strength: float = 0.0
    indicators: dict = field(default_factory=dict)

    @property
    def buy_count(self):
        return sum(1 for s in self.signals if s.signal == "BUY")

    @property
    def sell_count(self):
        return sum(1 for s in self.signals if s.signal == "SELL")

    @property
    def neutral_count(self):
        return sum(1 for s in self.signals if s.signal == "NEUTRAL")

    def to_text(self) -> str:
        lines = [
            f"=== Analyse Technique {self.symbol} ({self.timeframe}) ===",
            f"Signal global: {self.overall_signal} (force: {self.overall_strength:.2f})",
            f"Achats: {self.buy_count} | Ventes: {self.sell_count} | Neutre: {self.neutral_count}",
            "--- Détails ---"
        ]
        for s in self.signals:
            lines.append(f"  {s.indicator}: {s.signal} (force: {s.strength:.2f}) - {s.details}")
        return "\n".join(lines)


class TechnicalAnalyzer:
    """Moteur d'analyse technique complet."""

    def analyze(self, df: pd.DataFrame, symbol: str = "",
                timeframe: str = "") -> TechnicalSummary:
        """Analyse complète d'un DataFrame OHLCV."""
        if df is None or len(df) < 30:
            logger.warning(f"Données insuffisantes pour {symbol}/{timeframe}")
            return TechnicalSummary(symbol=symbol, timeframe=timeframe)

        summary = TechnicalSummary(symbol=symbol, timeframe=timeframe)

        self._calc_rsi(df, summary)
        self._calc_macd(df, summary)
        self._calc_bollinger(df, summary)
        self._calc_ema(df, summary)
        self._calc_sma(df, summary)
        self._calc_stochastic(df, summary)
        self._calc_adx(df, summary)
        self._calc_atr(df, summary)
        self._calc_obv(df, summary)
        self._calc_vwap(df, summary)
        self._calc_ichimoku(df, summary)
        self._calc_support_resistance(df, summary)

        self._compute_overall(summary)
        return summary

    def _calc_rsi(self, df: pd.DataFrame, summary: TechnicalSummary):
        rsi = ta.rsi(df["close"], length=14)
        if rsi is None or rsi.empty:
            return
        val = rsi.iloc[-1]
        summary.indicators["RSI"] = val

        if val < 30:
            sig = TechnicalSignal("RSI", "BUY", 0.8, val, f"Survendu ({val:.1f})")
        elif val < 40:
            sig = TechnicalSignal("RSI", "BUY", 0.4, val, f"Zone basse ({val:.1f})")
        elif val > 70:
            sig = TechnicalSignal("RSI", "SELL", 0.8, val, f"Suracheté ({val:.1f})")
        elif val > 60:
            sig = TechnicalSignal("RSI", "SELL", 0.4, val, f"Zone haute ({val:.1f})")
        else:
            sig = TechnicalSignal("RSI", "NEUTRAL", 0.2, val, f"Neutre ({val:.1f})")
        summary.signals.append(sig)

    def _calc_macd(self, df: pd.DataFrame, summary: TechnicalSummary):
        macd = ta.macd(df["close"])
        if macd is None or macd.empty:
            return
        macd_line = macd.iloc[-1, 0]
        signal_line = macd.iloc[-1, 1]
        histogram = macd.iloc[-1, 2]

        summary.indicators["MACD"] = macd_line
        summary.indicators["MACD_signal"] = signal_line
        summary.indicators["MACD_hist"] = histogram

        prev_hist = macd.iloc[-2, 2] if len(macd) > 1 else 0

        if histogram > 0 and prev_hist <= 0:
            sig = TechnicalSignal("MACD", "BUY", 0.8, histogram, "Croisement haussier")
        elif histogram > 0 and histogram > prev_hist:
            sig = TechnicalSignal("MACD", "BUY", 0.5, histogram, "Momentum haussier croissant")
        elif histogram < 0 and prev_hist >= 0:
            sig = TechnicalSignal("MACD", "SELL", 0.8, histogram, "Croisement baissier")
        elif histogram < 0 and histogram < prev_hist:
            sig = TechnicalSignal("MACD", "SELL", 0.5, histogram, "Momentum baissier croissant")
        else:
            sig = TechnicalSignal("MACD", "NEUTRAL", 0.2, histogram, f"Hist: {histogram:.4f}")
        summary.signals.append(sig)

    def _calc_bollinger(self, df: pd.DataFrame, summary: TechnicalSummary):
        bb = ta.bbands(df["close"], length=20, std=2)
        if bb is None or bb.empty:
            return
        lower = bb.iloc[-1, 0]
        mid = bb.iloc[-1, 1]
        upper = bb.iloc[-1, 2]
        price = df["close"].iloc[-1]

        summary.indicators["BB_upper"] = upper
        summary.indicators["BB_mid"] = mid
        summary.indicators["BB_lower"] = lower

        bb_pct = (price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        if bb_pct < 0.05:
            sig = TechnicalSignal("BB", "BUY", 0.8, bb_pct, f"Prix sous bande basse ({bb_pct:.2%})")
        elif bb_pct < 0.2:
            sig = TechnicalSignal("BB", "BUY", 0.5, bb_pct, f"Proche bande basse ({bb_pct:.2%})")
        elif bb_pct > 0.95:
            sig = TechnicalSignal("BB", "SELL", 0.8, bb_pct, f"Prix au-dessus bande haute ({bb_pct:.2%})")
        elif bb_pct > 0.8:
            sig = TechnicalSignal("BB", "SELL", 0.5, bb_pct, f"Proche bande haute ({bb_pct:.2%})")
        else:
            sig = TechnicalSignal("BB", "NEUTRAL", 0.2, bb_pct, f"Dans les bandes ({bb_pct:.2%})")
        summary.signals.append(sig)

    def _calc_ema(self, df: pd.DataFrame, summary: TechnicalSummary):
        ema_9 = ta.ema(df["close"], length=9)
        ema_21 = ta.ema(df["close"], length=21)
        ema_50 = ta.ema(df["close"], length=50)

        if ema_9 is None or ema_21 is None:
            return

        price = df["close"].iloc[-1]
        e9 = ema_9.iloc[-1]
        e21 = ema_21.iloc[-1]
        e50 = ema_50.iloc[-1] if ema_50 is not None and not ema_50.empty else e21

        summary.indicators["EMA_9"] = e9
        summary.indicators["EMA_21"] = e21
        summary.indicators["EMA_50"] = e50

        if price > e9 > e21 > e50:
            sig = TechnicalSignal("EMA", "BUY", 0.8, e9, "Tendance haussière forte (prix > EMA9 > EMA21 > EMA50)")
        elif price > e9 > e21:
            sig = TechnicalSignal("EMA", "BUY", 0.6, e9, "Tendance haussière (prix > EMA9 > EMA21)")
        elif price < e9 < e21 < e50:
            sig = TechnicalSignal("EMA", "SELL", 0.8, e9, "Tendance baissière forte (prix < EMA9 < EMA21 < EMA50)")
        elif price < e9 < e21:
            sig = TechnicalSignal("EMA", "SELL", 0.6, e9, "Tendance baissière (prix < EMA9 < EMA21)")
        else:
            sig = TechnicalSignal("EMA", "NEUTRAL", 0.3, e9, "EMAs croisées - pas de tendance claire")
        summary.signals.append(sig)

    def _calc_sma(self, df: pd.DataFrame, summary: TechnicalSummary):
        sma_50 = ta.sma(df["close"], length=50)
        sma_200 = ta.sma(df["close"], length=200)

        if sma_50 is None or sma_200 is None:
            return
        if sma_50.empty or sma_200.empty:
            return

        s50 = sma_50.iloc[-1]
        s200 = sma_200.iloc[-1]
        prev_50 = sma_50.iloc[-2] if len(sma_50) > 1 else s50
        prev_200 = sma_200.iloc[-2] if len(sma_200) > 1 else s200

        summary.indicators["SMA_50"] = s50
        summary.indicators["SMA_200"] = s200

        if s50 > s200 and prev_50 <= prev_200:
            sig = TechnicalSignal("SMA", "BUY", 1.0, s50, "GOLDEN CROSS (SMA50 croise au-dessus SMA200)")
        elif s50 < s200 and prev_50 >= prev_200:
            sig = TechnicalSignal("SMA", "SELL", 1.0, s50, "DEATH CROSS (SMA50 croise en-dessous SMA200)")
        elif s50 > s200:
            sig = TechnicalSignal("SMA", "BUY", 0.4, s50, "SMA50 au-dessus SMA200")
        else:
            sig = TechnicalSignal("SMA", "SELL", 0.4, s50, "SMA50 en-dessous SMA200")
        summary.signals.append(sig)

    def _calc_stochastic(self, df: pd.DataFrame, summary: TechnicalSummary):
        stoch = ta.stoch(df["high"], df["low"], df["close"])
        if stoch is None or stoch.empty:
            return
        k = stoch.iloc[-1, 0]
        d = stoch.iloc[-1, 1]

        summary.indicators["STOCH_K"] = k
        summary.indicators["STOCH_D"] = d

        if k < 20 and d < 20:
            sig = TechnicalSignal("STOCH", "BUY", 0.7, k, f"Zone survendue (K={k:.1f}, D={d:.1f})")
        elif k > 80 and d > 80:
            sig = TechnicalSignal("STOCH", "SELL", 0.7, k, f"Zone surachetée (K={k:.1f}, D={d:.1f})")
        elif k > d and k < 50:
            sig = TechnicalSignal("STOCH", "BUY", 0.4, k, f"Croisement haussier (K={k:.1f} > D={d:.1f})")
        elif k < d and k > 50:
            sig = TechnicalSignal("STOCH", "SELL", 0.4, k, f"Croisement baissier (K={k:.1f} < D={d:.1f})")
        else:
            sig = TechnicalSignal("STOCH", "NEUTRAL", 0.2, k, f"Neutre (K={k:.1f}, D={d:.1f})")
        summary.signals.append(sig)

    def _calc_adx(self, df: pd.DataFrame, summary: TechnicalSummary):
        adx = ta.adx(df["high"], df["low"], df["close"])
        if adx is None or adx.empty:
            return
        adx_val = adx.iloc[-1, 0]
        plus_di = adx.iloc[-1, 1]
        minus_di = adx.iloc[-1, 2]

        summary.indicators["ADX"] = adx_val
        summary.indicators["DI+"] = plus_di
        summary.indicators["DI-"] = minus_di

        if adx_val > 25:
            if plus_di > minus_di:
                sig = TechnicalSignal("ADX", "BUY", min(adx_val / 50, 1.0), adx_val,
                                      f"Tendance haussière forte (ADX={adx_val:.1f})")
            else:
                sig = TechnicalSignal("ADX", "SELL", min(adx_val / 50, 1.0), adx_val,
                                      f"Tendance baissière forte (ADX={adx_val:.1f})")
        else:
            sig = TechnicalSignal("ADX", "NEUTRAL", 0.2, adx_val,
                                  f"Pas de tendance claire (ADX={adx_val:.1f})")
        summary.signals.append(sig)

    def _calc_atr(self, df: pd.DataFrame, summary: TechnicalSummary):
        atr = ta.atr(df["high"], df["low"], df["close"])
        if atr is None or atr.empty:
            return
        atr_val = atr.iloc[-1]
        price = df["close"].iloc[-1]
        atr_pct = (atr_val / price) * 100

        summary.indicators["ATR"] = atr_val
        summary.indicators["ATR_pct"] = atr_pct

    def _calc_obv(self, df: pd.DataFrame, summary: TechnicalSummary):
        obv = ta.obv(df["close"], df["volume"])
        if obv is None or obv.empty or len(obv) < 20:
            return

        obv_sma = ta.sma(obv, length=20)
        if obv_sma is None or obv_sma.empty:
            return

        obv_val = obv.iloc[-1]
        obv_sma_val = obv_sma.iloc[-1]

        summary.indicators["OBV"] = obv_val

        if obv_val > obv_sma_val * 1.05:
            sig = TechnicalSignal("OBV", "BUY", 0.5, obv_val, "Volume en accumulation")
        elif obv_val < obv_sma_val * 0.95:
            sig = TechnicalSignal("OBV", "SELL", 0.5, obv_val, "Volume en distribution")
        else:
            sig = TechnicalSignal("OBV", "NEUTRAL", 0.2, obv_val, "Volume neutre")
        summary.signals.append(sig)

    def _calc_vwap(self, df: pd.DataFrame, summary: TechnicalSummary):
        vwap = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        if vwap is None or vwap.empty:
            return

        vwap_val = vwap.iloc[-1]
        price = df["close"].iloc[-1]

        summary.indicators["VWAP"] = vwap_val

        diff_pct = ((price - vwap_val) / vwap_val) * 100

        if diff_pct > 2:
            sig = TechnicalSignal("VWAP", "SELL", 0.5, vwap_val, f"Prix {diff_pct:.1f}% au-dessus VWAP")
        elif diff_pct < -2:
            sig = TechnicalSignal("VWAP", "BUY", 0.5, vwap_val, f"Prix {abs(diff_pct):.1f}% en-dessous VWAP")
        else:
            sig = TechnicalSignal("VWAP", "NEUTRAL", 0.2, vwap_val, f"Prix proche du VWAP ({diff_pct:+.1f}%)")
        summary.signals.append(sig)

    def _calc_ichimoku(self, df: pd.DataFrame, summary: TechnicalSummary):
        if len(df) < 52:
            return
        ichi = ta.ichimoku(df["high"], df["low"], df["close"])
        if ichi is None or len(ichi) < 2:
            return
        ichi_df = ichi[0]
        if ichi_df is None or ichi_df.empty:
            return

        price = df["close"].iloc[-1]
        tenkan = ichi_df.iloc[-1].get("ITS_9", None)
        kijun = ichi_df.iloc[-1].get("IKS_26", None)
        span_a = ichi_df.iloc[-1].get("ISA_9", None)
        span_b = ichi_df.iloc[-1].get("ISB_26", None)

        if tenkan is None or kijun is None:
            return

        summary.indicators["ICHIMOKU_tenkan"] = tenkan
        summary.indicators["ICHIMOKU_kijun"] = kijun

        buy_signals = 0
        sell_signals = 0

        if price > tenkan > kijun:
            buy_signals += 2
        elif price < tenkan < kijun:
            sell_signals += 2

        if span_a is not None and span_b is not None:
            if price > max(span_a, span_b):
                buy_signals += 1
            elif price < min(span_a, span_b):
                sell_signals += 1

        if buy_signals > sell_signals:
            sig = TechnicalSignal("ICHIMOKU", "BUY", min(buy_signals / 3, 1.0), price,
                                  f"Signaux haussiers Ichimoku ({buy_signals}/3)")
        elif sell_signals > buy_signals:
            sig = TechnicalSignal("ICHIMOKU", "SELL", min(sell_signals / 3, 1.0), price,
                                  f"Signaux baissiers Ichimoku ({sell_signals}/3)")
        else:
            sig = TechnicalSignal("ICHIMOKU", "NEUTRAL", 0.2, price, "Ichimoku neutre")
        summary.signals.append(sig)

    def _calc_support_resistance(self, df: pd.DataFrame, summary: TechnicalSummary):
        """Détecte les niveaux de support et résistance."""
        highs = df["high"].rolling(window=20).max()
        lows = df["low"].rolling(window=20).min()

        if highs.empty or lows.empty:
            return

        price = df["close"].iloc[-1]
        resistance = highs.iloc[-1]
        support = lows.iloc[-1]

        summary.indicators["support"] = support
        summary.indicators["resistance"] = resistance

        range_size = resistance - support
        if range_size > 0:
            position_in_range = (price - support) / range_size
            summary.indicators["position_in_range"] = position_in_range

    def _compute_overall(self, summary: TechnicalSummary):
        """Calcule le signal global pondéré."""
        if not summary.signals:
            return

        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0

        for sig in summary.signals:
            weight = sig.strength
            total_weight += weight
            if sig.signal == "BUY":
                buy_score += weight
            elif sig.signal == "SELL":
                sell_score += weight

        if total_weight == 0:
            return

        buy_pct = buy_score / total_weight
        sell_pct = sell_score / total_weight

        if buy_pct > sell_pct and buy_pct > 0.4:
            summary.overall_signal = "BUY"
            summary.overall_strength = buy_pct
        elif sell_pct > buy_pct and sell_pct > 0.4:
            summary.overall_signal = "SELL"
            summary.overall_strength = sell_pct
        else:
            summary.overall_signal = "NEUTRAL"
            summary.overall_strength = 1.0 - abs(buy_pct - sell_pct)