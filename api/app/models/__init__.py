"""Modèles SQLAlchemy. Chaque agrégat est importé ici pour qu'Alembic le détecte."""

from app.db import Base
from app.models.client import Client
from app.models.compteur import Compteur
from app.models.devis import Devis, LigneDevis, TypeLigne
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT, TacheOT
from app.models.pont import Pont
from app.models.rendez_vous import RendezVous
from app.models.utilisateur import Role, Utilisateur
from app.models.vehicule import Vehicule

__all__ = [
    "Base",
    "Client",
    "Compteur",
    "Devis",
    "HistoriqueStatut",
    "LigneDevis",
    "OrdreTravail",
    "Pont",
    "RendezVous",
    "Role",
    "StatutOT",
    "TacheOT",
    "TypeLigne",
    "Utilisateur",
    "Vehicule",
]
