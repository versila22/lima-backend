"""Settings router — association configuration (admin only).

V0: Simple key-value store persisted in a JSON file.
Can be migrated to a DB table in V1.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.models.member import Member
from app.utils.deps import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

SETTINGS_FILE = Path("/tmp/lima_settings.json")

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


def _load_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def _save_settings(data: Dict[str, Any]) -> None:
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class SettingsUpdate(BaseModel):
    data: Dict[str, Any]


@router.get("")
async def get_settings(
    _: Member = Depends(require_admin),
):
    """Retrieve current association settings (admin only)."""
    return _load_settings()


@router.put("")
async def update_settings(
    body: SettingsUpdate,
    _: Member = Depends(require_admin),
):
    """
    Update association settings (admin only).

    Merges provided keys with existing settings.
    """
    current = _load_settings()
    current.update(body.data)
    try:
        _save_settings(current)
    except Exception as exc:
        logger.exception("Erreur sauvegarde settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de sauvegarder les paramètres: {exc}",
        )
    return current
