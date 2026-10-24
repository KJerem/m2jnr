"""Fiches clients : réservées au gérant (le mécanicien reçoit un 403)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.utilisateur import Role
from app.schemas.client import ClientEntree, ClientSortie
from app.schemas.commun import Page
from app.security.dependances import require_role
from app.services import clients as service

router = APIRouter(
    prefix="/clients", tags=["clients"], dependencies=[Depends(require_role(Role.GERANT))]
)


@router.get("")
def lister(
    page: int = Query(1, ge=1),
    taille: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Page[ClientSortie]:
    resultat = service.lister_clients(db, page, taille)
    return Page[ClientSortie](
        elements=[ClientSortie.model_validate(c) for c in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def creer(entree: ClientEntree, db: Session = Depends(get_db)) -> ClientSortie:
    return ClientSortie.model_validate(service.creer_client(db, entree))


@router.get("/{client_id}")
def consulter(client_id: int, db: Session = Depends(get_db)) -> ClientSortie:
    return ClientSortie.model_validate(service.obtenir_client(db, client_id))


@router.put("/{client_id}")
def modifier(client_id: int, entree: ClientEntree, db: Session = Depends(get_db)) -> ClientSortie:
    client = service.obtenir_client(db, client_id)
    return ClientSortie.model_validate(service.modifier_client(db, client, entree))
