"""Véhicules : rattachement à un client, immatriculation unique, contrôles de cohérence."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import id_possible
from app.errors import AppError, conflict, invalid, not_found
from app.models.client import Client
from app.models.vehicule import Vehicule
from app.schemas.vehicule import VehiculeEntree

MESSAGE_IMMATRICULATION_EXISTANTE = "Cette immatriculation est déjà enregistrée."
MESSAGE_DATE_FUTURE = "La date de mise en circulation ne peut pas être dans le futur."
DATE_MIN = date(1900, 1, 1)


def obtenir_vehicule(db: Session, vehicule_id: int) -> Vehicule:
    vehicule = db.get(Vehicule, vehicule_id) if id_possible(vehicule_id) else None
    if vehicule is None:
        raise not_found("Véhicule introuvable.")
    return vehicule


def lister_vehicules_client(db: Session, client: Client) -> list[Vehicule]:
    return list(
        db.scalars(select(Vehicule).where(Vehicule.client_id == client.id).order_by(Vehicule.id))
    )


def _immatriculation_existante(immatriculation: str, vehicule_id: int) -> AppError:
    return conflict(
        "immatriculation_existante", MESSAGE_IMMATRICULATION_EXISTANTE, vehicule_id=vehicule_id
    )


def verifier_immatriculation_libre(
    db: Session, immatriculation: str, *, sauf_id: int | None = None
) -> None:
    """409 si la plaque (déjà normalisée, donc casse et tirets ignorés) est prise."""
    requete = select(Vehicule.id).where(Vehicule.immatriculation == immatriculation)
    if sauf_id is not None:
        requete = requete.where(Vehicule.id != sauf_id)
    existant = db.scalar(requete)
    if existant is not None:
        raise _immatriculation_existante(immatriculation, existant)


def verifier_date_mise_en_circulation(valeur: date | None, aujourd_hui: date) -> None:
    if valeur is None:
        return
    if valeur > aujourd_hui:
        raise invalid("date_mise_en_circulation", MESSAGE_DATE_FUTURE)
    if valeur < DATE_MIN:
        raise invalid("date_mise_en_circulation", "Date invalide.")


def _appliquer(vehicule: Vehicule, donnees: VehiculeEntree) -> None:
    vehicule.immatriculation = donnees.immatriculation
    vehicule.marque = donnees.marque
    vehicule.modele = donnees.modele
    vehicule.kilometrage = donnees.kilometrage
    vehicule.vin = donnees.vin
    vehicule.date_mise_en_circulation = donnees.date_mise_en_circulation


def _enregistrer(db: Session, vehicule: Vehicule) -> Vehicule:
    """Écrit en base ; une plaque prise entre-temps (requête concurrente) donne aussi un 409."""
    try:
        with db.begin_nested():
            db.add(vehicule)
            db.flush()
    except IntegrityError as exc:
        if "uq_vehicule_immatriculation" not in str(exc.orig):
            raise
        existant = db.scalar(
            select(Vehicule.id).where(Vehicule.immatriculation == vehicule.immatriculation)
        )
        raise _immatriculation_existante(vehicule.immatriculation, existant or 0) from exc
    db.refresh(vehicule)
    return vehicule


def creer_vehicule(
    db: Session, client: Client, donnees: VehiculeEntree, aujourd_hui: date
) -> Vehicule:
    verifier_date_mise_en_circulation(donnees.date_mise_en_circulation, aujourd_hui)
    verifier_immatriculation_libre(db, donnees.immatriculation)
    vehicule = Vehicule(client_id=client.id)
    _appliquer(vehicule, donnees)
    return _enregistrer(db, vehicule)


def modifier_vehicule(
    db: Session, vehicule: Vehicule, donnees: VehiculeEntree, aujourd_hui: date
) -> Vehicule:
    verifier_date_mise_en_circulation(donnees.date_mise_en_circulation, aujourd_hui)
    verifier_immatriculation_libre(db, donnees.immatriculation, sauf_id=vehicule.id)
    _appliquer(vehicule, donnees)
    return _enregistrer(db, vehicule)
