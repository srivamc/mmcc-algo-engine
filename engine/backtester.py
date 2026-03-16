"""
MMCC Backtesting Engine
Patent-pending: Multi-Modal Cyclic Convergence (M2C2) Framework

Vectorized backtesting engine for high-performance strategy evaluation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
import structlog
from core.config import settings

log = structlog.get_logger(__name__)


@dataclass
class BacktestResult:
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    equity_curve: pd.Series
    trades: pd.DataFrame


class Backtester:
    """
    High-performance vectorized backtester.
    Supports multi-asset backtesting and M2C2 signal convergence evaluation.
    """

    def __init__(self, initial_capital: float = 1_000_000.0):
        self.initial_capital = initial_capital
        self.config = settings.backtest
        self.commission = self.config.commission_pct
        self.slippage = self.config.slippage_pct

    def run(self, data: pd.DataFrame, signals: pd.Series) -> BacktestResult:
        """
        Runs backtest on OHLCV data with pre-calculated signals.
        Expects 'close' column in data and -1, 0, 1 in signals.
        """
        log.info("backtest_started", rows=len(data))
        
        # Ensure data and signals are aligned
        df = data.copy()
        df['signal'] = signals
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        
        # Strategy returns (shifted signal as we enter at next bar open/close)
        # Using simple assumption: enter at close of signal bar
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        
        # Apply costs for signal changes (trades)
        trades = df['signal'].diff().abs().fillna(0)
        df['strategy_returns'] -= trades * (self.commission + self.slippage)
        
        # Calculate cumulative returns
        df['cum_returns'] = (1 + df['strategy_returns'].fillna(0)).cumprod()
        df['equity'] = df['cum_returns'] * self.initial_capital
        
        # Calculate performance metrics
        perf = self._calculate_metrics(df)
        
        log.info("backtest_completed", total_return=f"{perf.total_return_pct:.2%}", sharpe=f"{perf.sharpe_ratio:.2f}")
        return perf

    def _calculate_metrics(self, df: pd.DataFrame) -> BacktestResult:
        """Calculates standard risk/return metrics from equity curve."""
        
        equity = df['equity']
        returns = df['strategy_returns'].fillna(0)
        
        total_return = (equity.iloc[-1] / self.initial_capital) - 1
        
        # Annualization factor (assuming daily data)
        ann_factor = 252 
        
        ann_return = ((1 + total_return) ** (ann_factor / len(df))) - 1
        
        # Sharpe Ratio (assuming 0% risk free rate)
        sharpe = 0
        if returns.std() != 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(ann_factor)
            
        # Max Drawdown
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        max_dd = drawdown.min()
        
        # Trade Analysis
        trade_mask = df['signal'].diff() != 0
        total_trades = int(trade_mask.sum())
        
        # Simple win rate calculation
        # A 'win' is a trade where return was positive
        wins = (df.loc[trade_mask, 'strategy_returns'] > 0).sum()
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        return BacktestResult(
            total_return_pct=total_return,
            annualized_return_pct=ann_return,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            win_rate=win_rate,
            total_trades=total_trades,
            equity_curve=equity,
            trades=df[trade_mask]
        )

    async def run_monte_carlo(self, returns: pd.Series, iterations: int = 1000) -> Dict:
        """Runs Monte Carlo simulations on return distribution."""
        results = []
        for _ in range(iterations):
            sim_returns = np.random.choice(returns.dropna(), size=len(returns), replace=True)
            cum_returns = (1 + sim_returns).cumprod()
            results.append(cum_returns[-1])
            
        return {
            "p5": np.percentile(results, 5),
            "p50": np.percentile(results, 50),
            "p95": np.percentile(results, 95)
        }
