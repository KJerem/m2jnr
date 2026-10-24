"""Fiche véhicule : lecture pour les deux rôles, modification réservée au gérant.

Le mécanicien a besoin des données du véhicule (et, au sprint 2, de son historique) ; le
propriétaire ne lui est montré que par son nom.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.clock import date_locale, get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role
from app.schemas.vehicule import VehiculeEntree, VehiculeSortie
from app.security.dependances import require_role
from app.services import vehicules as service

router = APIRouter(prefix="/vehicules", tags=["véhicules"])


@router.get("", dependencies=[Depends(require_role(Role.GERANT, Role.MECANICIEN))])
def lister(db: DbSession, taille: int = Query(500, ge=1, le=1000)) -> list[VehiculeSortie]:
    """Véhicules groupés par propriétaire (sélection du véhicule d'un OT ou d'un rendez-vous)."""
    return [VehiculeSortie.model_validate(v) for v in service.lister_vehicules(db, taille)]


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
