from fastapi import APIRouter, Depends, Query

from ..deps import get_db
from ...utils.database import Database

router = APIRouter(tags=["portfolio"])


@router.get("/api/portfolio")
async def get_portfolio(db: Database = Depends(get_db)):
    """Dernier snapshot du portfolio."""
    snapshot = await db.get_latest_snapshot()
    return snapshot or {}


@router.get("/api/portfolio/history")
async def get_portfolio_history(
    db: Database = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Historique des valeurs du portfolio."""
    return await db.get_performance_chart(days)
