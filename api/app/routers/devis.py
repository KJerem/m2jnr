"""Devis : réservés au gérant.

Le contenu (lignes, calcul HT/TVA/TTC) arrive au sprint 3 (story S4.1) ; le contrat d'accès
est posé dès le sprint 1 pour que la matrice des rôles soit testée tôt.
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.models.utilisateur import Role
from app.security.dependances import require_role

router = APIRouter(
    prefix="/devis", tags=["devis"], dependencies=[Depends(require_role(Role.GERANT))]
)


@router.get("")
def lister_devis() -> list[dict[str, Any]]:
    # Sprint 3 : liste des devis.
    return []
