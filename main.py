"""
MMCC Algo Engine - FastAPI entry point
Patent-pending: Multi-Modal Cyclic Convergence (M2C2) Trading Framework

This service exposes REST + WebSocket APIs for:
- Strategy lifecycle management (create/start/pause/stop)
- Real-time signal streaming via WebSocket
- Backtesting execution with vectorized computation
- HITL (Human-in-the-Loop) approval workflow integration
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog

from engine.strategy_engine import StrategyEngine
from engine.signal_generator import SignalGenerator
from api.routes import strategies, backtests, signals, health
from core.config import settings
from core.events import EventBus

log = structlog.get_logger(__name__)

# Global instances
strategy_engine: StrategyEngine | None = None
event_bus: EventBus | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global strategy_engine, event_bus
    log.info("MMCC Algo Engine starting", version="1.0.0")
    event_bus = EventBus()
    strategy_engine = StrategyEngine(event_bus=event_bus, settings=settings)
    await strategy_engine.start()
    yield
    log.info("MMCC Algo Engine shutting down")
    await strategy_engine.stop()


app = FastAPI(
    title="MMCC Algo Engine",
    description="Patent-pending M2C2 algorithmic trading engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["strategies"])
app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])


@app.websocket("/ws/signals")
async def websocket_signals(ws: WebSocket):
    """Real-time signal streaming via WebSocket."""
    await ws.accept()
    queue = asyncio.Queue()
    if event_bus:
        event_bus.subscribe("signal", queue)
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            await ws.send_json(event)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if event_bus:
            event_bus.unsubscribe("signal", queue)


@app.websocket("/ws/portfolio")
async def websocket_portfolio(ws: WebSocket):
    """Real-time portfolio P&L streaming."""
    await ws.accept()
    queue = asyncio.Queue()
    if event_bus:
        event_bus.subscribe("portfolio", queue)
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            await ws.send_json(event)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if event_bus:
            event_bus.unsubscribe("portfolio", queue)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
