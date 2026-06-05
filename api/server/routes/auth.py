"""GET /auth/me — validate API key and return org identity."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_org

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me")
async def me(org_id: str = Depends(require_org)) -> dict:
    """Validate the API key and return the org it belongs to."""
    return {"org_id": org_id}
