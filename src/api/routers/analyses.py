from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..deps import get_db
from ...utils.database import Database

router = APIRouter(tags=["analyses"])


@router.get("/api/analyses")
async def get_analyses(
    db: Database = Depends(get_db),
    symbol: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
):
    analyses = await db.get_recent_analyses(symbol, limit)
    for a in analyses:
        for k, v in a.items():
            if isinstance(v, datetime):
                a[k] = v.isoformat()
    return analyses
