"""Schémas de la fiche véhicule."""

from datetime import date, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.schemas.commun import SansControle, vide_vers_none
from app.services.immatriculation import normaliser_immatriculation, normaliser_vin

KILOMETRAGE_MAX = 2_000_000

Immatriculation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
    AfterValidator(normaliser_immatriculation),
]
Vin = Annotated[
    Annotated[str, StringConstraints(max_length=30), AfterValidator(normaliser_vin)] | None,
    BeforeValidator(vide_vers_none),
]
# Strict : « 12,5 », « abc » ou true sont refusés plutôt que convertis.
Kilometrage = Annotated[int, Field(strict=True, ge=0, le=KILOMETRAGE_MAX)]


class VehiculeEntree(BaseModel):
    """Création ou modification complète d'un véhicule."""

    immatriculation: Immatriculation
    marque: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50), SansControle
    ]
    modele: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80), SansControle
    ]
    kilometrage: Kilometrage
    vin: Vin = None
    date_mise_en_circulation: Annotated[date | None, BeforeValidator(vide_vers_none)] = None


class ProprietaireResume(BaseModel):
    """Identité du propriétaire, sans coordonnées (le mécanicien lit aussi la fiche)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str | None


class VehiculeResume(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    immatriculation: str
    marque: str
    modele: str
    kilometrage: int


class VehiculeSortie(VehiculeResume):
    client_id: int
    vin: str | None
    date_mise_en_circulation: date | None
    proprietaire: ProprietaireResume = Field(validation_alias="client")
    cree_le: datetime
    modifie_le: datetime
