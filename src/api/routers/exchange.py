import asyncio
from datetime import datetime

import ccxt
from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_db
from ..schemas import ExchangeKeysDelete, ExchangeKeysRequest
from ..security import verify_sensitive_api_key
from ...utils.database import Database

router = APIRouter(
    prefix="/api/exchange",
    tags=["exchange"],
    dependencies=[Depends(verify_sensitive_api_key)],
)


@router.post("/keys")
async def save_exchange_keys(req: ExchangeKeysRequest, db: Database = Depends(get_db)):
    """Enregistre les clés API exchange et les valide via CCXT."""
    exchange_class = getattr(ccxt, req.exchange, None)
    if not exchange_class:
        raise HTTPException(400, f"Exchange '{req.exchange}' non supporté")

    try:
        ex = exchange_class(
            {
                "apiKey": req.api_key,
                "secret": req.api_secret,
                "enableRateLimit": True,
            }
        )
        balance = await asyncio.get_event_loop().run_in_executor(None, ex.fetch_balance)
        usdt_free = balance.get("USDT", {}).get("free", 0)
        usdt_total = balance.get("USDT", {}).get("total", 0)
    except ccxt.AuthenticationError:
        raise HTTPException(
            401, "Clés API invalides — vérifiez votre API key et secret"
        )
    except ccxt.ExchangeError as e:
        raise HTTPException(400, f"Erreur exchange: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de connexion: {str(e)}")

    await db.save_user_api_keys(req.email, req.exchange, req.api_key, req.api_secret)

    return {
        "status": "connected",
        "exchange": req.exchange,
        "balance_usdt": {
            "free": usdt_free,
            "total": usdt_total,
        },
    }


@router.get("/keys")
async def get_exchange_keys(
    email: str = Query(...),
    db: Database = Depends(get_db),
):
    keys = await db.get_user_api_keys(email)
    for k in keys:
        for field, v in k.items():
            if isinstance(v, datetime):
                k[field] = v.isoformat()
    return keys


@router.delete("/keys")
async def delete_exchange_keys(
    req: ExchangeKeysDelete,
    db: Database = Depends(get_db),
):
    await db.delete_user_api_keys(req.email, req.exchange)
    return {"status": "deleted", "exchange": req.exchange}
