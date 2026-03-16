from fastapi import APIRouter, HTTPException, WebSocket
from typing import Dict
import structlog

router = APIRouter()
log = structlog.get_logger(__name__)

@router.post("/subscribe")
async def subscribe_to_live_feed(config: Dict):
    """Subscribe to live market data feed for a symbol."""
    symbol = config.get("symbol")
    log.info("live_subscription", symbol=symbol)
    return {"status": "subscribed", "symbol": symbol}

@router.get("/positions")
async def get_live_positions():
    """Get current live trading positions."""
    # TODO: Wire to order executor for live data
    return {"positions": [], "pnl": 0.0, "status": "live"}

@router.post("/orders/cancel/{order_id}")
async def cancel_order(order_id: str):
    """Cancel a live order via HITL gateway."""
    log.info("order_cancel_requested", order_id=order_id)
    return {"status": "cancelled", "order_id": order_id}
