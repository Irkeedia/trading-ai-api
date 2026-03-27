from fastapi import APIRouter, Depends

from ..deps import get_db
from ...utils.database import Database

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard")
async def get_dashboard(db: Database = Depends(get_db)):
    """Résumé complet pour la page principale du dashboard."""
    return await db.get_dashboard_summary()
