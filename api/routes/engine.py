from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
import structlog
from engine.strategy_engine import strategy_engine

router = APIRouter()
log = structlog.get_logger(__name__)

@router.post("/start")
async def start_engine():
    """Start the M2C2 Algo Engine."""
    try:
        await strategy_engine.start()
        return {"status": "success", "message": "Engine started"}
    except Exception as e:
        log.error("engine_start_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_engine():
    """Stop the M2C2 Algo Engine."""
    try:
        await strategy_engine.stop()
        return {"status": "success", "message": "Engine stopped"}
    except Exception as e:
        log.error("engine_stop_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Get current engine and strategy status."""
    return {
        "engine_active": strategy_engine.is_running,
        "active_strategies": list(strategy_engine.active_strategies.keys()),
        "uptime": "TODO"
    }

@router.post("/strategies/deploy")
async def deploy_strategy(strategy_config: Dict):
    """Deploy a new strategy instance to the engine."""
    # Logic to load and initialize strategy from config
    return {"status": "deployed", "strategy_id": strategy_config.get("id")}
