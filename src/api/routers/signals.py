from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..deps import get_db
from ...utils.database import Database

router = APIRouter(tags=["signals"])


@router.get("/api/signals")
async def get_signals(
    db: Database = Depends(get_db),
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
):
    signals = await db.get_recent_signals(symbol, limit)
    for s in signals:
        for k, v in s.items():
            if isinstance(v, datetime):
                s[k] = v.isoformat()
    return signals
