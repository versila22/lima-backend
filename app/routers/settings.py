"""Settings router — association configuration (admin only)."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.app_setting import AppSetting
from app.models.member import Member
from app.utils.deps import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

SETTINGS_KEY = "association"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "association_name": "LIMA — Ligue d'Improvisation du Maine-et-Loire",
    "association_email": "contact@lima-impro.fr",
    "association_website": "https://lima-impro.fr",
    "membership_fee_default": 20.0,
    "player_fee_match": 160.0,
    "player_fee_cabaret": 75.0,
    "player_fee_loisir": 40.0,
    "activation_token_validity_days": 7,
    "reset_token_validity_hours": 2,
}


async def _load_settings(db: AsyncSession) -> Dict[str, Any]:
    result = await db.execute(select(AppSetting).where(AppSetting.key == SETTINGS_KEY))
    setting = result.scalar_one_or_none()
    data = dict(DEFAULT_SETTINGS)
    if setting and isinstance(setting.data, dict):
        data.update(setting.data)
    return data


class SettingsUpdate(BaseModel):
    data: Dict[str, Any]


@router.get("")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """Retrieve current association settings (admin only)."""
    return await _load_settings(db)


@router.put("")
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: Member = Depends(require_admin),
):
    """
    Update association settings (admin only).

    Merges provided keys with existing settings.
    """
    current = await _load_settings(db)
    current.update(body.data)
    try:
        result = await db.execute(select(AppSetting).where(AppSetting.key == SETTINGS_KEY))
        setting = result.scalar_one_or_none()
        if setting is None:
            setting = AppSetting(key=SETTINGS_KEY, data=current)
            db.add(setting)
        else:
            setting.data = current
        await db.flush()
    except Exception as exc:
        logger.exception("Erreur sauvegarde settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de sauvegarder les paramètres: {exc}",
        )
    return current
