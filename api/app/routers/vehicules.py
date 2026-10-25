"""Fiche véhicule : lecture pour les deux rôles, modification réservée au gérant.

Le mécanicien a besoin des données du véhicule et de son historique d'interventions ; le
propriétaire ne lui est montré que par son nom.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.clock import date_locale, get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role
from app.schemas.commun import PAGE_MAX, Page
from app.schemas.ordre import InterventionHistorique
from app.schemas.vehicule import VehiculeEntree, VehiculeSortie
from app.security.dependances import require_role
from app.services import ordres as service_ordres
from app.services import vehicules as service
from app.services.recherche import recherche_de_liste

router = APIRouter(prefix="/vehicules", tags=["véhicules"])


@router.get("", dependencies=[Depends(require_role(Role.GERANT, Role.MECANICIEN))])
def lister(
    db: DbSession,
    q: str | None = Query(
        None,
        description=(
            "Recherche (2 à 100 caractères) : plaque avec ou sans tirets, marque, modèle, VIN"
            " ou nom du propriétaire (jamais ses coordonnées), sans accents ni casse."
        ),
    ),
    page: int = Query(1, ge=1, le=PAGE_MAX),
    taille: int = Query(20, ge=1, le=1000),
) -> Page[VehiculeSortie]:
    """Véhicules groupés par propriétaire, page par page (story S1.5). Les listes de choix
    (véhicule d'un OT ou d'un rendez-vous) demandent une grande page (`taille=1000`)."""
    resultat = service.lister_vehicules(db, page, taille, recherche_de_liste(q))
    return Page[VehiculeSortie](
        elements=[VehiculeSortie.model_validate(v) for v in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.get("/{vehicule_id}", dependencies=[Depends(require_role(Role.GERANT, Role.MECANICIEN))])
def consulter(vehicule_id: int, db: DbSession) -> VehiculeSortie:
    return VehiculeSortie.model_validate(service.obtenir_vehicule(db, vehicule_id))


@router.put("/{vehicule_id}", dependencies=[Depends(require_role(Role.GERANT))])
def modifier(
    vehicule_id: int,
    entree: VehiculeEntree,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> VehiculeSortie:
    vehicule = service.obtenir_vehicule(db, vehicule_id)
    aujourd_hui = date_locale(maintenant, settings.timezone)
    vehicule = service.modifier_vehicule(db, vehicule, entree, aujourd_hui)
    return VehiculeSortie.model_validate(vehicule)


@router.get(
    "/{vehicule_id}/historique",
    dependencies=[Depends(require_role(Role.GERANT, Role.MECANICIEN))],
)
def historique(vehicule_id: int, db: DbSession) -> list[InterventionHistorique]:
    """Interventions du véhicule, de la plus récente à la plus ancienne."""
    vehicule = service.obtenir_vehicule(db, vehicule_id)
    return [
        InterventionHistorique.model_validate(o)
        for o in service_ordres.historique_vehicule(db, vehicule)
    ]
