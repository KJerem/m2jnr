"""Recherche (story S1.3) : réservée au gérant (« En tant que gérant, je recherche un client
ou un véhicule »). Le mécanicien reçoit un 403 : la recherche renvoie des téléphones de
clients et des montants de factures."""

from fastapi import APIRouter, Depends, Query

from app.db import DbSession
from app.models.utilisateur import Role
from app.schemas.recherche import RechercheSortie, sortie_recherche
from app.security.dependances import require_role
from app.services import recherche as service

router = APIRouter(tags=["recherche"], dependencies=[Depends(require_role(Role.GERANT))])


@router.get("/recherche")
def rechercher(
    db: DbSession,
    q: str | None = Query(
        None,
        description=(
            "Nom, téléphone, immatriculation, numéro d'OT ou de facture (2 à 100 caractères)."
        ),
    ),
) -> RechercheSortie:
    texte = service.lire_requete(q)
    return sortie_recherche(texte, service.rechercher(db, service.analyser_requete(texte)))
