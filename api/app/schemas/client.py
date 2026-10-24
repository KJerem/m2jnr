"""Schémas de la fiche client."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.schemas.commun import EmailFacultatif, TexteFacultatif100, TexteObligatoire100
from app.schemas.vehicule import VehiculeResume
from app.services.telephone import normaliser_telephone

Telephone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=30),
    AfterValidator(normaliser_telephone),
]


class ClientEntree(BaseModel):
    """Création ou modification complète d'une fiche client."""

    nom: TexteObligatoire100
    prenom: TexteFacultatif100 = None
    telephone: Telephone
    email: EmailFacultatif = None
    # RGPD : consentement explicite, jamais coché par défaut.
    consentement_rappels: bool = False


class ClientResume(BaseModel):
    """Identité minimale d'un client (alerte de doublon, propriétaire d'un véhicule)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str | None


class ClientSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str | None
    telephone: str
    email: str | None
    consentement_rappels: bool
    nombre_vehicules: int
    cree_le: datetime
    modifie_le: datetime


class ClientDetail(ClientSortie):
    """Fiche complète : coordonnées et véhicules rattachés."""

    vehicules: list[VehiculeResume]
