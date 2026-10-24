"""Schémas de la fiche client.

Adresse postale (mentions de la facture, art. 242 nonies A du CGI) : facultative, comme tout
ce qui n'est pas nécessaire au suivi du véhicule (minimisation des données) ; réservée au
gérant, comme le téléphone et l'e-mail (le mécanicien ne lit jamais ces schémas).
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints

from app.schemas.commun import (
    EmailFacultatif,
    TexteFacultatif100,
    TexteFacultatif200,
    TexteObligatoire100,
    vide_vers_none,
)
from app.schemas.vehicule import VehiculeResume
from app.services.telephone import normaliser_telephone

Telephone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=30),
    AfterValidator(normaliser_telephone),
]


MESSAGE_CODE_POSTAL = "Code postal à 5 chiffres."


def _code_postal(valeur: str) -> str:
    # Chiffres ASCII seulement (« ６９００３ » refusé), comme le téléphone.
    if not re.fullmatch(r"[0-9]{5}", valeur):
        raise ValueError(MESSAGE_CODE_POSTAL)
    return valeur


CodePostal = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(_code_postal)] | None,
    BeforeValidator(vide_vers_none),
]


class ClientEntree(BaseModel):
    """Création ou modification complète d'une fiche client."""

    nom: TexteObligatoire100
    prenom: TexteFacultatif100 = None
    telephone: Telephone
    email: EmailFacultatif = None
    adresse: TexteFacultatif200 = None
    code_postal: CodePostal = None
    ville: TexteFacultatif100 = None
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
    adresse: str | None
    code_postal: str | None
    ville: str | None
    consentement_rappels: bool
    nombre_vehicules: int
    cree_le: datetime
    modifie_le: datetime


class ClientDetail(ClientSortie):
    """Fiche complète : coordonnées et véhicules rattachés."""

    vehicules: list[VehiculeResume]
