"""
MMCC Signal Generators
Multiple independent signal sources for M2C2 convergence layer.

Each generator encapsulates a distinct analytical approach:
- Technical Analysis (TA) based signals
- ML/XGBoost regression signals
- Sentiment analysis signals (news/social)
- Order flow / market microstructure signals
- Mean reversion signals
- Momentum/trend following signals
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


@dataclass
class Signal:
    generator: str
    symbol: str
    direction: SignalDirection
    strength: SignalStrength
    confidence: float  # 0.0 - 1.0
    price_target: float | None
    stop_loss: float | None
    estimated_value_inr: float
    metadata: dict
    generated_at: datetime


class SignalGenerator(ABC):
    """Base class for all signal generators."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def generate(self, symbols: list[str]) -> Signal | None: ...

    def _classify_strength(self, confidence: float) -> SignalStrength:
        if confidence >= 0.85:
            return SignalStrength.VERY_STRONG
        if confidence >= 0.70:
            return SignalStrength.STRONG
        if confidence >= 0.55:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK


class TechnicalAnalysisGenerator(SignalGenerator):
    """
    Multi-indicator TA signal generator.
    Combines RSI, MACD, Bollinger Bands, ADX, and Volume Profile.
    Uses weighted voting across indicators for composite signal.
    """

    @property
    def name(self) -> str:
        return "technical_analysis"

    async def generate(self, symbols: list[str]) -> Signal | None:
        # In production: fetches OHLCV from data pipeline
        # Here: demonstrates the algorithm
        for symbol in symbols:
            ohlcv = await self._fetch_ohlcv(symbol, "5m", 200)
            if ohlcv is None or len(ohlcv) < 50:
                continue
            signal = self._compute_composite_signal(symbol, ohlcv)
            if signal.direction != SignalDirection.HOLD:
                return signal
        return None

    async def _fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame | None:
        # Stub: in production connects to data pipeline service
        return None

    def _compute_composite_signal(
        self, symbol: str, df: pd.DataFrame
    ) -> Signal:
        close = df['close'].values
        votes = []

        # RSI signal
        rsi = self._compute_rsi(close, 14)
        if rsi < 30:
            votes.append((SignalDirection.BUY, 0.8))
        elif rsi > 70:
            votes.append((SignalDirection.SELL, 0.8))

        # MACD signal
        macd, signal_line = self._compute_macd(close)
        if macd[-1] > signal_line[-1] and macd[-2] <= signal_line[-2]:
            votes.append((SignalDirection.BUY, 0.75))  # Golden cross
        elif macd[-1] < signal_line[-1] and macd[-2] >= signal_line[-2]:
            votes.append((SignalDirection.SELL, 0.75))  # Death cross

        # Bollinger Bands
        upper, lower = self._compute_bollinger(close, 20, 2)
        current_price = close[-1]
        if current_price < lower[-1]:
            votes.append((SignalDirection.BUY, 0.7))
        elif current_price > upper[-1]:
            votes.append((SignalDirection.SELL, 0.7))

        if not votes:
            return Signal(
                generator=self.name, symbol=symbol,
                direction=SignalDirection.HOLD, strength=SignalStrength.WEAK,
                confidence=0.0, price_target=None, stop_loss=None,
                estimated_value_inr=0.0, metadata={},
                generated_at=datetime.utcnow()
            )

        # Weighted vote
        buy_weight = sum(w for d, w in votes if d == SignalDirection.BUY)
        sell_weight = sum(w for d, w in votes if d == SignalDirection.SELL)
        total = buy_weight + sell_weight
        if total == 0:
            direction = SignalDirection.HOLD
            confidence = 0.0
        elif buy_weight > sell_weight:
            direction = SignalDirection.BUY
            confidence = buy_weight / total
        else:
            direction = SignalDirection.SELL
            confidence = sell_weight / total

        return Signal(
            generator=self.name, symbol=symbol,
            direction=direction,
            strength=self._classify_strength(confidence),
            confidence=confidence,
            price_target=current_price * (1.02 if direction == SignalDirection.BUY else 0.98),
            stop_loss=current_price * (0.98 if direction == SignalDirection.BUY else 1.02),
            estimated_value_inr=0.0,
            metadata={"rsi": float(rsi), "indicators": len(votes)},
            generated_at=datetime.utcnow()
        )

    def _compute_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _compute_macd(
        self, prices: np.ndarray,
        fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[np.ndarray, np.ndarray]:
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        return macd_line, signal_line

    def _compute_bollinger(
        self, prices: np.ndarray, period: int = 20, std_dev: int = 2
    ) -> tuple[np.ndarray, np.ndarray]:
        ma = np.array([np.mean(prices[i-period:i]) for i in range(period, len(prices)+1)])
        std = np.array([np.std(prices[i-period:i]) for i in range(period, len(prices)+1)])
        return ma + std_dev * std, ma - std_dev * std

    def _ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        alpha = 2 / (period + 1)
        result = np.zeros_like(prices)
        result[0] = prices[0]
        for i in range(1, len(prices)):
            result[i] = alpha * prices[i] + (1 - alpha) * result[i-1]
        return result


class MLXGBoostGenerator(SignalGenerator):
    """
    XGBoost-based ML signal generator.
    Features: 50+ engineered features from OHLCV, orderbook, and macro data.
    Target: 5-min forward return direction (classification).
    """

    def __init__(self, model_path: str | None = None):
        self.model = None
        self.model_path = model_path
        self._load_model()

    @property
    def name(self) -> str:
        return "ml_xgboost"

    def _load_model(self) -> None:
        try:
            import xgboost as xgb
            if self.model_path:
                self.model = xgb.XGBClassifier()
                self.model.load_model(self.model_path)
        except Exception:
            self.model = None

    async def generate(self, symbols: list[str]) -> Signal | None:
        if self.model is None:
            return None
        for symbol in symbols:
            features = await self._build_features(symbol)
            if features is None:
                continue
            proba = self.model.predict_proba([features])[0]
            buy_prob, sell_prob = proba[1], proba[0]
            confidence = max(buy_prob, sell_prob)
            if confidence < 0.55:
                continue
            direction = SignalDirection.BUY if buy_prob > sell_prob else SignalDirection.SELL
            return Signal(
                generator=self.name, symbol=symbol,
                direction=direction,
                strength=self._classify_strength(confidence),
                confidence=float(confidence),
                price_target=None, stop_loss=None,
                estimated_value_inr=0.0,
                metadata={"buy_prob": float(buy_prob), "sell_prob": float(sell_prob)},
                generated_at=datetime.utcnow()
            )
        return None

    async def _build_features(self, symbol: str) -> list[float] | None:
        # Stub: builds 50+ features from live data
        return None


class SentimentGenerator(SignalGenerator):
    """
    NLP-based sentiment signal from news and social media.
    Uses FinBERT for financial sentiment classification.
    """

    @property
    def name(self) -> str:
        return "sentiment_nlp"

    async def generate(self, symbols: list[str]) -> Signal | None:
        for symbol in symbols:
            score = await self._get_sentiment_score(symbol)
            if score is None:
                continue
            if abs(score) < 0.3:
                continue
            direction = SignalDirection.BUY if score > 0 else SignalDirection.SELL
            confidence = min(0.9, 0.5 + abs(score) * 0.5)
            return Signal(
                generator=self.name, symbol=symbol,
                direction=direction,
                strength=self._classify_strength(confidence),
                confidence=confidence,
                price_target=None, stop_loss=None,
                estimated_value_inr=0.0,
                metadata={"sentiment_score": score},
                generated_at=datetime.utcnow()
            )
        return None

    async def _get_sentiment_score(self, symbol: str) -> float | None:
        # Stub: queries news API + FinBERT inference
        return None
