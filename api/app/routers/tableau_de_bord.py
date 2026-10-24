"""Tableau de bord du gérant : réservé au gérant (403 pour le mécanicien, qui ne reçoit ni
montant facturé ni coordonnées de client)."""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.clock import get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role
from app.schemas.tableau_de_bord import TableauDeBordSortie, sortie_tableau_de_bord
from app.security.dependances import require_role
from app.services.tableau_de_bord import tableau_de_bord

router = APIRouter(tags=["tableau de bord"], dependencies=[Depends(require_role(Role.GERANT))])


@router.get("/tableau-de-bord")
def consulter(
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> TableauDeBordSortie:
    return sortie_tableau_de_bord(tableau_de_bord(db, maintenant, settings.timezone), maintenant)
