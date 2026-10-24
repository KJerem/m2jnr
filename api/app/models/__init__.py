"""Modèles SQLAlchemy. Chaque agrégat est importé ici pour qu'Alembic le détecte."""

from app.db import Base
from app.models.client import Client
from app.models.compteur import Compteur
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT, TacheOT
from app.models.utilisateur import Role, Utilisateur
from app.models.vehicule import Vehicule

__all__ = [
    "Base",
    "Client",
    "Compteur",
    "HistoriqueStatut",
    "OrdreTravail",
    "Role",
    "StatutOT",
    "TacheOT",
    "Utilisateur",
    "Vehicule",
]
