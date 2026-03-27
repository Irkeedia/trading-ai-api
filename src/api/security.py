"""
Protection des routes sensibles (moteur, clés exchange) via X-API-Key.

Si API_SECRET_KEY vaut vide ou « change-me-in-production », la vérification
est désactivée (pratique en local). Dès qu'une vraie clé est configurée,
le header X-API-Key doit correspondre.
"""
from fastapi import Header, HTTPException, Request


async def verify_sensitive_api_key(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    cfg = getattr(request.app.state, "config", None)
    if not cfg:
        raise HTTPException(503, "Config not ready")
    secret = (cfg.env.api_secret_key or "").strip()
    if not secret or secret == "change-me-in-production":
        return
    if not x_api_key or x_api_key != secret:
        raise HTTPException(
            401,
            "Clé API manquante ou invalide. Envoyez le header X-API-Key identique à API_SECRET_KEY.",
        )
