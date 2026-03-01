"""
MMCC Strategy Engine
Patent-pending: Multi-Modal Cyclic Convergence (M2C2) Framework

Core innovation: Strategies emit signals that cycle through a convergence layer
where multiple independent signals must achieve quorum before order generation.
This prevents single-point signal failures that plague traditional algo systems.

Architecture:
  DataPipeline -> SignalGenerators (N) -> ConvergenceLayer -> RiskGate -> OrderRouter
                                             |
                                          HITLGate (configurable threshold)
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from engine.signal_generator import SignalGenerator, Signal, SignalDirection
from core.events import EventBus

log = structlog.get_logger(__name__)


class StrategyState(str, Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class HITLMode(str, Enum):
    """Human-in-the-Loop approval modes."""
    DISABLED = "DISABLED"        # Fully automated
    DAILY_SUMMARY = "DAILY"      # Daily digest approval
    PER_BASKET = "PER_BASKET"    # Approve each order basket
    PER_ORDER = "PER_ORDER"      # Approve every single order
    THRESHOLD_BASED = "THRESHOLD" # Only for trades above value threshold


@dataclass
class StrategyConfig:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    symbols: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=lambda: ["1m", "5m", "15m"])
    signal_generators: list[str] = field(default_factory=list)  # generator class names
    convergence_quorum: float = 0.6   # 60% of signals must agree
    convergence_window_ms: int = 5000  # 5-second window for signal aggregation
    hitl_mode: HITLMode = HITLMode.DAILY_SUMMARY
    hitl_threshold_inr: float = 50_000  # Auto-execute below this; HITL above
    max_position_pct: float = 0.05   # Max 5% of portfolio in single position
    target_broker: str | None = None  # None = auto-route via ABLAR
    enabled: bool = True


@dataclass
class StrategyMetrics:
    strategy_id: str
    total_signals: int = 0
    approved_signals: int = 0
    rejected_signals: int = 0
    hitl_pending: int = 0
    orders_placed: int = 0
    pnl_today: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    last_signal_at: datetime | None = None


class StrategyEngine:
    """
    Core M2C2 Strategy Orchestration Engine.
    Manages multiple concurrent strategies with shared infrastructure.
    """

    def __init__(self, event_bus: EventBus, settings: Any):
        self.event_bus = event_bus
        self.settings = settings
        self.strategies: dict[str, tuple[StrategyConfig, StrategyState]] = {}
        self.metrics: dict[str, StrategyMetrics] = {}
        self.signal_generators: dict[str, SignalGenerator] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        self._running = True
        log.info("Strategy engine started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        log.info("Strategy engine stopped")

    async def register_strategy(self, config: StrategyConfig) -> str:
        """Register a new strategy. Returns strategy ID."""
        self.strategies[config.id] = (config, StrategyState.DRAFT)
        self.metrics[config.id] = StrategyMetrics(strategy_id=config.id)
        log.info("Strategy registered", id=config.id, name=config.name)
        await self.event_bus.publish("strategy", {
            "event": "registered", "strategy_id": config.id, "name": config.name
        })
        return config.id

    async def start_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")
        config, _ = self.strategies[strategy_id]
        self.strategies[strategy_id] = (config, StrategyState.RUNNING)
        task = asyncio.create_task(
            self._run_strategy_loop(strategy_id),
            name=f"strategy_{strategy_id}"
        )
        self._tasks.append(task)
        log.info("Strategy started", id=strategy_id)
        await self.event_bus.publish("strategy", {"event": "started", "strategy_id": strategy_id})

    async def pause_strategy(self, strategy_id: str) -> None:
        if strategy_id not in self.strategies:
            raise ValueError(f"Strategy {strategy_id} not found")
        config, _ = self.strategies[strategy_id]
        self.strategies[strategy_id] = (config, StrategyState.PAUSED)
        await self.event_bus.publish("strategy", {"event": "paused", "strategy_id": strategy_id})

    async def _run_strategy_loop(self, strategy_id: str) -> None:
        """Main M2C2 loop: collect signals -> converge -> HITL gate -> execute."""
        config, _ = self.strategies[strategy_id]
        while self._running:
            _, state = self.strategies[strategy_id]
            if state != StrategyState.RUNNING:
                await asyncio.sleep(1)
                continue
            try:
                # 1. Gather signals from all generators within convergence window
                signals = await self._gather_signals(config)
                if not signals:
                    await asyncio.sleep(0.1)
                    continue

                # 2. M2C2 Convergence: require quorum agreement
                converged = self._compute_convergence(signals, config.convergence_quorum)
                if not converged:
                    await asyncio.sleep(0.1)
                    continue

                # 3. HITL gate check
                requires_approval = self._requires_hitl(converged, config)
                self.metrics[strategy_id].total_signals += 1

                if requires_approval:
                    self.metrics[strategy_id].hitl_pending += 1
                    await self.event_bus.publish("hitl_request", {
                        "strategy_id": strategy_id,
                        "signal": converged,
                        "hitl_mode": config.hitl_mode,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                else:
                    # Auto-execute: publish to order router
                    self.metrics[strategy_id].approved_signals += 1
                    await self.event_bus.publish("signal", converged)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Strategy loop error", strategy_id=strategy_id, error=str(e))
                await asyncio.sleep(1)

    async def _gather_signals(
        self, config: StrategyConfig
    ) -> list[Signal]:
        """Collect signals from all configured generators in parallel."""
        tasks = [
            self.signal_generators[gen].generate(config.symbols)
            for gen in config.signal_generators
            if gen in self.signal_generators
        ]
        if not tasks:
            return []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Signal)]

    def _compute_convergence(
        self, signals: list[Signal], quorum: float
    ) -> dict | None:
        """M2C2 convergence: signals must agree above quorum threshold."""
        if not signals:
            return None
        buys = sum(1 for s in signals if s.direction == SignalDirection.BUY)
        sells = sum(1 for s in signals if s.direction == SignalDirection.SELL)
        total = len(signals)
        buy_ratio = buys / total
        sell_ratio = sells / total
        if buy_ratio >= quorum:
            return {"direction": "BUY", "confidence": buy_ratio, "signals": [s.__dict__ for s in signals]}
        if sell_ratio >= quorum:
            return {"direction": "SELL", "confidence": sell_ratio, "signals": [s.__dict__ for s in signals]}
        return None

    def _requires_hitl(self, signal: dict, config: StrategyConfig) -> bool:
        if config.hitl_mode == HITLMode.DISABLED:
            return False
        if config.hitl_mode == HITLMode.PER_ORDER:
            return True
        if config.hitl_mode == HITLMode.THRESHOLD_BASED:
            est_value = signal.get("estimated_value", 0)
            return est_value >= config.hitl_threshold_inr
        return config.hitl_mode == HITLMode.PER_BASKET

    def get_all_metrics(self) -> list[StrategyMetrics]:
        return list(self.metrics.values())

    def get_strategy_state(self, strategy_id: str) -> StrategyState | None:
        if strategy_id not in self.strategies:
            return None
        _, state = self.strategies[strategy_id]
        return state
