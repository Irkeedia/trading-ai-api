from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..deps import get_db
from ...utils.database import Database

router = APIRouter(tags=["trades"])


@router.get("/api/trades")
async def get_trades(
    db: Database = Depends(get_db),
    symbol: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    trades = await db.get_recent_trades(symbol, limit)
    for t in trades:
        for k, v in t.items():
            if isinstance(v, datetime):
                t[k] = v.isoformat()
    return trades


@router.get("/api/trades/stats")
async def get_trades_stats(db: Database = Depends(get_db)):
    return await db.get_trades_stats()
