"""Équipe de l'atelier : mécaniciens actifs (affectation des OT, filtres)."""

from fastapi import APIRouter, Depends

from app.db import DbSession
from app.models.utilisateur import Role
from app.schemas.ordre import MecanicienSortie
from app.security.dependances import require_role
from app.services import ordres as service

router = APIRouter(
    tags=["équipe"], dependencies=[Depends(require_role(Role.GERANT, Role.MECANICIEN))]
)


@router.get("/mecaniciens")
def lister_mecaniciens(db: DbSession) -> list[MecanicienSortie]:
    return [MecanicienSortie.model_validate(u) for u in service.lister_mecaniciens(db)]
