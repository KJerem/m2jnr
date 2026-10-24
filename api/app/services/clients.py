"""Fiches clients : création, modification, consultation et liste paginée."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.models.client import Client
from app.schemas.client import ClientEntree


@dataclass(frozen=True)
class PageClients:
    elements: list[Client]
    total: int


def obtenir_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise not_found("Client introuvable.")
    return client


def _appliquer(client: Client, donnees: ClientEntree) -> None:
    client.nom = donnees.nom
    client.prenom = donnees.prenom
    client.telephone = donnees.telephone
    client.email = donnees.email
    client.consentement_rappels = donnees.consentement_rappels


def creer_client(db: Session, donnees: ClientEntree) -> Client:
    client = Client()
    _appliquer(client, donnees)
    db.add(client)
    db.flush()
    db.refresh(client)
    return client


def modifier_client(db: Session, client: Client, donnees: ClientEntree) -> Client:
    _appliquer(client, donnees)
    db.flush()
    db.refresh(client)
    return client


def lister_clients(db: Session, page: int, taille: int) -> PageClients:
    """Clients triés par nom puis prénom (sans tenir compte de la casse)."""
    total = db.scalar(select(func.count()).select_from(Client)) or 0
    requete = (
        select(Client)
        .order_by(func.lower(Client.nom), func.lower(func.coalesce(Client.prenom, "")), Client.id)
        .offset((page - 1) * taille)
        .limit(taille)
    )
    return PageClients(elements=list(db.scalars(requete)), total=total)
