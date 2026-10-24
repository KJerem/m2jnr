"""Fiches clients : création, modification, consultation et liste paginée.

Alerte de doublon : un téléphone déjà connu chez un autre client bloque l'enregistrement
(409 `doublon_telephone`, avec la liste des clients concernés) tant que le gérant ne l'a pas
confirmé (`confirmer_doublon=True`). Ce n'est pas une interdiction : un couple ou une
entreprise peut partager un numéro.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import id_possible
from app.errors import conflict, not_found
from app.models.client import Client
from app.schemas.client import ClientEntree


@dataclass(frozen=True)
class PageClients:
    elements: list[Client]
    total: int


def obtenir_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id) if id_possible(client_id) else None
    if client is None:
        raise not_found("Client introuvable.")
    return client


def _appliquer(client: Client, donnees: ClientEntree) -> None:
    client.nom = donnees.nom
    client.prenom = donnees.prenom
    client.telephone = donnees.telephone
    client.email = donnees.email
    client.adresse = donnees.adresse
    client.code_postal = donnees.code_postal
    client.ville = donnees.ville
    client.consentement_rappels = donnees.consentement_rappels


MESSAGE_DOUBLON = "Un client avec ce téléphone existe déjà."


def clients_avec_telephone(
    db: Session, telephone: str, *, sauf_id: int | None = None
) -> list[Client]:
    requete = select(Client).where(Client.telephone == telephone).order_by(Client.id)
    if sauf_id is not None:
        requete = requete.where(Client.id != sauf_id)
    return list(db.scalars(requete))


def verifier_doublon_telephone(
    db: Session, telephone: str, *, sauf_id: int | None = None, confirmer_doublon: bool = False
) -> None:
    if confirmer_doublon:
        return
    existants = clients_avec_telephone(db, telephone, sauf_id=sauf_id)
    if existants:
        raise conflict(
            "doublon_telephone",
            MESSAGE_DOUBLON,
            clients=[{"id": c.id, "nom": c.nom, "prenom": c.prenom} for c in existants],
        )


def creer_client(db: Session, donnees: ClientEntree, *, confirmer_doublon: bool = False) -> Client:
    verifier_doublon_telephone(db, donnees.telephone, confirmer_doublon=confirmer_doublon)
    client = Client()
    _appliquer(client, donnees)
    db.add(client)
    db.flush()
    db.refresh(client)
    return client


def modifier_client(
    db: Session, client: Client, donnees: ClientEntree, *, confirmer_doublon: bool = False
) -> Client:
    verifier_doublon_telephone(
        db, donnees.telephone, sauf_id=client.id, confirmer_doublon=confirmer_doublon
    )
    _appliquer(client, donnees)
    db.flush()
    db.refresh(client)
    return client


def lister_clients(db: Session, page: int, taille: int) -> PageClients:
    """Clients triés par nom puis prénom (sans tenir compte de la casse)."""
    total = db.scalar(select(func.count()).select_from(Client)) or 0
    requete = (
        select(Client)
        .options(selectinload(Client.vehicules))
        .order_by(func.lower(Client.nom), func.lower(func.coalesce(Client.prenom, "")), Client.id)
        .offset((page - 1) * taille)
        .limit(taille)
    )
    return PageClients(elements=list(db.scalars(requete)), total=total)
