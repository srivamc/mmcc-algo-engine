"""
MMCC Algo Engine - Core Configuration
Patent-pending: Multi-Modal Cyclic Convergence (M2C2) Framework

Centralized settings and feature flags for the algo trading engine.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import structlog

log = structlog.get_logger(__name__)


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class HITLMode(str, Enum):
    DISABLED = "disabled"
    DAILY_SUMMARY = "daily_summary"
    PER_BASKET = "per_basket"
    PER_ORDER = "per_order"


@dataclass
class BrokerConfig:
    """Broker connection configuration."""
    zerodha_api_key: str = field(default_factory=lambda: os.getenv("ZERODHA_API_KEY", ""))
    zerodha_api_secret: str = field(default_factory=lambda: os.getenv("ZERODHA_API_SECRET", ""))
    zerodha_access_token: str = field(default_factory=lambda: os.getenv("ZERODHA_ACCESS_TOKEN", ""))
    angel_api_key: str = field(default_factory=lambda: os.getenv("ANGEL_API_KEY", ""))
    angel_client_id: str = field(default_factory=lambda: os.getenv("ANGEL_CLIENT_ID", ""))
    angel_mpin: str = field(default_factory=lambda: os.getenv("ANGEL_MPIN", ""))
    angel_totp_secret: str = field(default_factory=lambda: os.getenv("ANGEL_TOTP_SECRET", ""))
    upstox_api_key: str = field(default_factory=lambda: os.getenv("UPSTOX_API_KEY", ""))
    upstox_api_secret: str = field(default_factory=lambda: os.getenv("UPSTOX_API_SECRET", ""))
    upstox_redirect_uri: str = field(default_factory=lambda: os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8000/callback"))
    fyers_app_id: str = field(default_factory=lambda: os.getenv("FYERS_APP_ID", ""))
    fyers_secret_key: str = field(default_factory=lambda: os.getenv("FYERS_SECRET_KEY", ""))
    icici_api_key: str = field(default_factory=lambda: os.getenv("ICICI_API_KEY", ""))
    icici_api_secret: str = field(default_factory=lambda: os.getenv("ICICI_API_SECRET", ""))


@dataclass
class MLConfig:
    """Machine Learning model configuration."""
    xgboost_n_estimators: int = 200
    xgboost_max_depth: int = 6
    xgboost_learning_rate: float = 0.05
    xgboost_subsample: float = 0.8
    xgboost_colsample_bytree: float = 0.8
    finbert_model_name: str = "ProsusAI/finbert"
    finbert_max_length: int = 512
    finbert_batch_size: int = 16
    lstm_sequence_length: int = 60
    lstm_hidden_size: int = 128
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.2
    signal_cache_ttl_seconds: int = 300
    model_retrain_interval_hours: int = 24
    min_training_samples: int = 1000


@dataclass
class RiskConfig:
    """Risk management parameters."""
    max_position_size_pct: float = 0.05       # 5% per position
    max_portfolio_drawdown_pct: float = 0.15   # 15% max drawdown
    max_daily_loss_pct: float = 0.03           # 3% daily loss limit
    max_open_orders: int = 10
    min_signal_quorum: int = 3                 # M2C2 convergence quorum
    min_signal_confidence: float = 0.65
    stop_loss_multiplier: float = 2.0          # ATR multiplier
    take_profit_multiplier: float = 3.0        # ATR multiplier
    max_leverage: float = 1.0                  # No leverage by default
    basket_max_correlation: float = 0.70       # Max inter-basket correlation
    vix_halt_threshold: float = 35.0           # Halt trading above VIX 35
    circuit_breaker_loss_pct: float = 0.05     # 5% intraday loss halt


@dataclass
class BacktestConfig:
    """Backtesting engine configuration."""
    default_start_date: str = "2020-01-01"
    default_end_date: str = "2024-12-31"
    default_initial_capital: float = 1_000_000.0
    commission_pct: float = 0.0003       # 0.03% per trade
    slippage_pct: float = 0.0001         # 0.01% slippage
    margin_rate: float = 0.0             # No margin
    benchmark_symbol: str = "NIFTY50"
    walk_forward_train_months: int = 12
    walk_forward_test_months: int = 3
    monte_carlo_simulations: int = 1000
    result_store_path: str = "./backtest_results"


@dataclass
class DataConfig:
    """Market data configuration."""
    data_provider: str = os.getenv("DATA_PROVIDER", "zerodha")  # zerodha, yahoo, alpha_vantage
    alpha_vantage_api_key: str = field(default_factory=lambda: os.getenv("ALPHA_VANTAGE_KEY", ""))
    news_api_key: str = field(default_factory=lambda: os.getenv("NEWS_API_KEY", ""))
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_channel_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHANNEL_ID", ""))
    websocket_reconnect_interval: int = 5
    ohlcv_cache_size: int = 10000
    tick_buffer_size: int = 50000
    supported_timeframes: List[str] = field(default_factory=lambda: ["1m", "5m", "15m", "1h", "1d"])
    default_symbols: List[str] = field(default_factory=lambda: [
        "RELIANCE", "TCS", "INFY", "HDFC", "ICICIBANK",
        "SBIN", "BAJFINANCE", "HINDUNILVR", "ITC", "KOTAKBANK"
    ])


@dataclass
class ServerConfig:
    """API server configuration."""
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8001"))
    workers: int = int(os.getenv("WORKERS", "4"))
    reload: bool = os.getenv("RELOAD", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "info")
    cors_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000",  # mmcc-edge-console
        "http://localhost:3001",
        os.getenv("CONSOLE_ORIGIN", "")
    ])
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "change-me-in-production"))
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    prometheus_enabled: bool = True


@dataclass
class FeatureFlags:
    """Runtime feature toggles for M2C2 platform."""
    enable_ml_signals: bool = os.getenv("ENABLE_ML_SIGNALS", "true").lower() == "true"
    enable_sentiment_signals: bool = os.getenv("ENABLE_SENTIMENT", "true").lower() == "true"
    enable_orderflow_signals: bool = os.getenv("ENABLE_ORDERFLOW", "false").lower() == "true"
    enable_hitl_gate: bool = os.getenv("ENABLE_HITL", "true").lower() == "true"
    hitl_mode: HITLMode = HITLMode(os.getenv("HITL_MODE", HITLMode.DAILY_SUMMARY))
    enable_live_trading: bool = os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true"
    enable_paper_trading: bool = os.getenv("ENABLE_PAPER_TRADING", "true").lower() == "true"
    enable_backtesting: bool = True
    enable_walk_forward: bool = os.getenv("ENABLE_WALK_FORWARD", "false").lower() == "true"
    enable_circuit_breaker: bool = True
    enable_auto_rebalance: bool = os.getenv("ENABLE_AUTO_REBALANCE", "false").lower() == "true"
    enable_multi_broker: bool = os.getenv("ENABLE_MULTI_BROKER", "false").lower() == "true"


@dataclass
class Settings:
    """Top-level aggregated settings for the MMCC Algo Engine."""
    environment: Environment = Environment(os.getenv("ENVIRONMENT", Environment.DEVELOPMENT))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    service_name: str = "mmcc-algo-engine"
    version: str = "1.0.0"

    server: ServerConfig = field(default_factory=ServerConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    data: DataConfig = field(default_factory=DataConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)

    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    def is_live_trading_safe(self) -> bool:
        """Production safety check - require explicit live trading flag."""
        return (
            self.features.enable_live_trading
            and bool(self.broker.zerodha_api_key or self.broker.angel_api_key)
        )


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        log.info(
            "settings_loaded",
            environment=_settings.environment,
            live_trading=_settings.features.enable_live_trading,
            hitl_enabled=_settings.features.enable_hitl_gate,
        )
    return _settings


# Convenience alias
settings = get_settings()
