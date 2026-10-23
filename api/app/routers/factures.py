"""Factures : réservées au gérant.

Le contenu (numérotation F-AAAA-nnn, PDF) arrive au sprint 3 (story S4.3) ; le contrat d'accès
est posé dès le sprint 1 pour que la matrice des rôles soit testée tôt.
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.models.utilisateur import Role
from app.security.dependances import require_role

router = APIRouter(
    prefix="/factures", tags=["factures"], dependencies=[Depends(require_role(Role.GERANT))]
)


@router.get("")
def lister_factures() -> list[dict[str, Any]]:
    # Sprint 3 : liste des factures.
    return []
