"""Fiches clients et véhicules rattachés : réservés au gérant (le mécanicien reçoit un 403)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.clock import date_locale, get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role
from app.schemas.client import ClientDetail, ClientEntree, ClientSortie
from app.schemas.commun import Page
from app.schemas.vehicule import VehiculeEntree, VehiculeSortie
from app.security.dependances import require_role
from app.services import clients as service
from app.services import vehicules as service_vehicules

router = APIRouter(
    prefix="/clients", tags=["clients"], dependencies=[Depends(require_role(Role.GERANT))]
)


@router.get("")
def lister(
    db: DbSession,
    page: int = Query(1, ge=1),
    taille: int = Query(20, ge=1, le=100),
) -> Page[ClientSortie]:
    resultat = service.lister_clients(db, page, taille)
    return Page[ClientSortie](
        elements=[ClientSortie.model_validate(c) for c in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


ConfirmerDoublon = Query(
    False, description="Vrai pour enregistrer malgré un téléphone déjà connu (409 sinon)."
)


@router.post("", status_code=status.HTTP_201_CREATED)
def creer(
    entree: ClientEntree,
    db: DbSession,
    confirmer_doublon: bool = ConfirmerDoublon,
) -> ClientSortie:
    client = service.creer_client(db, entree, confirmer_doublon=confirmer_doublon)
    return ClientSortie.model_validate(client)


@router.get("/{client_id}")
def consulter(client_id: int, db: DbSession) -> ClientDetail:
    return ClientDetail.model_validate(service.obtenir_client(db, client_id))


@router.put("/{client_id}")
def modifier(
    client_id: int,
    entree: ClientEntree,
    db: DbSession,
    confirmer_doublon: bool = ConfirmerDoublon,
) -> ClientSortie:
    client = service.obtenir_client(db, client_id)
    client = service.modifier_client(db, client, entree, confirmer_doublon=confirmer_doublon)
    return ClientSortie.model_validate(client)


@router.get("/{client_id}/vehicules")
def lister_vehicules(client_id: int, db: DbSession) -> list[VehiculeSortie]:
    client = service.obtenir_client(db, client_id)
    return [
        VehiculeSortie.model_validate(v)
        for v in service_vehicules.lister_vehicules_client(db, client)
    ]


@router.post("/{client_id}/vehicules", status_code=status.HTTP_201_CREATED)
def ajouter_vehicule(
    client_id: int,
    entree: VehiculeEntree,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> VehiculeSortie:
    client = service.obtenir_client(db, client_id)
    aujourd_hui = date_locale(maintenant, settings.timezone)
    vehicule = service_vehicules.creer_vehicule(db, client, entree, aujourd_hui)
    return VehiculeSortie.model_validate(vehicule)
