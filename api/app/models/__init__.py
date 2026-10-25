"""Modèles SQLAlchemy. Chaque agrégat est importé ici pour qu'Alembic le détecte."""

from app.db import Base
from app.models.client import Client
from app.models.compteur import Compteur
from app.models.devis import Devis, LigneDevis, StatutDevis, TypeLigne
from app.models.facture import Facture, LigneFacture
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT, TacheOT
from app.models.paiement import ModePaiement, Paiement
from app.models.pont import Pont
from app.models.rendez_vous import RendezVous
from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.models.vehicule import Vehicule

__all__ = [
    "Base",
    "Client",
    "Compteur",
    "Devis",
    "Facture",
    "HistoriqueStatut",
    "LigneDevis",
    "LigneFacture",
    "ModePaiement",
    "OrdreTravail",
    "Paiement",
    "Pont",
    "RendezVous",
    "Role",
    "StatutCompte",
    "StatutDevis",
    "StatutOT",
    "TacheOT",
    "TypeLigne",
    "Utilisateur",
    "Vehicule",
]
