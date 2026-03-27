from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ..deps import get_db
from ...utils.database import Database

router = APIRouter(tags=["news"])


@router.get("/api/news")
async def get_news(
    db: Database = Depends(get_db),
    limit: int = Query(30, ge=1, le=100),
):
    news = await db.get_recent_news(limit)
    for n in news:
        for k, v in n.items():
            if isinstance(v, datetime):
                n[k] = v.isoformat()
    return news
