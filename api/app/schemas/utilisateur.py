"""Schémas des comptes des employés (story S8.2). Le hash du mot de passe n'en sort jamais."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.schemas.commun import SansControle, TexteObligatoire100
from app.services.courriel import normaliser_courriel
from app.services.utilisateurs import LONGUEUR_MIN_MOT_DE_PASSE

LONGUEUR_MAX_MOT_DE_PASSE = 1024
MESSAGE_MOT_DE_PASSE_COURT = (
    f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères."
)


def _mot_de_passe(valeur: str) -> str:
    # Pas de strip : les espaces comptent dans un mot de passe.
    if len(valeur) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise ValueError(MESSAGE_MOT_DE_PASSE_COURT)
    if len(valeur) > LONGUEUR_MAX_MOT_DE_PASSE:
        raise ValueError(f"{LONGUEUR_MAX_MOT_DE_PASSE} caractères maximum.")
    if "\x00" in valeur:
        raise ValueError("Caractère non autorisé.")
    return valeur


MotDePasse = Annotated[str, AfterValidator(_mot_de_passe)]
# Nom de famille à la modification : peut rester vide pour un compte repris d'avant le sprint 5
# dont le nom n'avait qu'un mot (migration 0016, « Admin » → prénom « Admin », nom « »).
NomModifiable = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=100), SansControle
]
Email = Annotated[str, StringConstraints(max_length=254), AfterValidator(normaliser_courriel)]


class UtilisateurModification(BaseModel):
    """Modification d'un compte par le gérant (sans le mot de passe). Le nom peut être vide
    (revue du sprint 5) : un compte repris sans nom se modifie sans en inventer un."""

    prenom: TexteObligatoire100
    nom: NomModifiable
    email: Email
    role: Role


class UtilisateurEntree(UtilisateurModification):
    """Création d'un compte par le gérant : actif dès sa création, nom obligatoire."""

    nom: TexteObligatoire100
    mot_de_passe: MotDePasse


class MotDePasseEntree(BaseModel):
    """Nouveau mot de passe choisi par le gérant (réinitialisation)."""

    mot_de_passe: MotDePasse


class InscriptionEntree(BaseModel):
    """Inscription autonome (story S8.3) : le rôle n'est pas choisi par le demandeur."""

    prenom: TexteObligatoire100
    nom: TexteObligatoire100
    email: Email
    mot_de_passe: MotDePasse


class ValidationEntree(BaseModel):
    """Validation d'une inscription par un gérant : rôle définitif du compte."""

    role: Role


class UtilisateurSortie(BaseModel):
    id: int
    prenom: str
    nom: str
    # Prénom puis nom, tels qu'ils s'affichent partout (« Karim B. »).
    nom_affiche: str
    email: str
    role: Role
    statut: StatutCompte
    # Fin du blocage après 5 essais erronés ; null si le compte n'est pas bloqué.
    bloque_jusqu_a: datetime | None
    derniere_connexion: datetime | None
    cree_le: datetime
    valide_le: datetime | None
    desactive_le: datetime | None


def sortie_utilisateur(utilisateur: Utilisateur, maintenant: datetime) -> UtilisateurSortie:
    bloque = utilisateur.bloque_jusqu_a
    return UtilisateurSortie(
        id=utilisateur.id,
        prenom=utilisateur.prenom,
        nom=utilisateur.nom,
        nom_affiche=utilisateur.nom_affiche,
        email=utilisateur.email,
        role=utilisateur.role,
        statut=utilisateur.statut,
        bloque_jusqu_a=bloque if bloque is not None and bloque > maintenant else None,
        derniere_connexion=utilisateur.derniere_connexion,
        cree_le=utilisateur.cree_le,
        valide_le=utilisateur.valide_le,
        desactive_le=utilisateur.desactive_le,
    )
