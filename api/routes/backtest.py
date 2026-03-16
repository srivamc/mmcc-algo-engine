from fastapi import APIRouter, HTTPException
from typing import Dict
import structlog
from engine.backtester import backtester

router = APIRouter()
log = structlog.get_logger(__name__)

@router.post("/run")
async def run_backtest(config: Dict):
    """Trigger a vectorized backtest job."""
    log.info("backtest_requested", strategy=config.get("strategy"))
    return {"job_id": "bt_12345", "status": "queued"}

@router.get("/results/{job_id}")
async def get_backtest_results(job_id: str):
    """Retrieve results for a completed backtest job."""
    return {
        "job_id": job_id,
        "status": "completed",
        "metrics": {"sharpe": 2.1, "max_drawdown": -0.05, "total_return": 0.15}
    }
