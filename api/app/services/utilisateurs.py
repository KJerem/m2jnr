"""Création et mise à jour des comptes employés (utilisé par la CLI et le jeu de démonstration)."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.utilisateur import Role, Utilisateur
from app.security.hachage import hacher, verifier
from app.services.auth import trouver_par_email
from app.services.courriel import normaliser_courriel

LONGUEUR_MIN_MOT_DE_PASSE = 12


class CompteInvalideError(ValueError):
    """Donnée de compte refusée ; le message est affiché tel quel."""


def valider_email(email: str) -> str:
    try:
        return normaliser_courriel(email)
    except ValueError as exc:
        raise CompteInvalideError(str(exc)) from exc


def valider_mot_de_passe(mot_de_passe: str) -> str:
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise CompteInvalideError(
            f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères."
        )
    return mot_de_passe


def creer_utilisateur(
    db: Session, *, email: str, nom: str, role: Role, mot_de_passe: str
) -> Utilisateur:
    email = valider_email(email)
    nom = nom.strip()
    if not nom:
        raise CompteInvalideError("Le nom est obligatoire.")
    valider_mot_de_passe(mot_de_passe)
    if trouver_par_email(db, email) is not None:
        raise CompteInvalideError(f"Un compte existe déjà pour {email}.")
    utilisateur = Utilisateur(
        email=email, nom=nom, role=role, mot_de_passe_hash=hacher(mot_de_passe), actif=True
    )
    db.add(utilisateur)
    db.flush()
    return utilisateur


@dataclass(frozen=True)
class CompteDemo:
    email: str
    nom: str
    role: Role


def enregistrer_compte(db: Session, compte: CompteDemo, mot_de_passe: str) -> bool:
    """Crée le compte ou le remet à jour (nom, rôle, mot de passe, déblocage).

    Renvoie True si le compte a été créé. Le hash n'est recalculé que si le mot de passe a
    changé : relancer le seed ne modifie rien.
    """
    utilisateur = trouver_par_email(db, compte.email)
    if utilisateur is None:
        db.add(
            Utilisateur(
                email=compte.email,
                nom=compte.nom,
                role=compte.role,
                mot_de_passe_hash=hacher(mot_de_passe),
                actif=True,
            )
        )
        db.flush()
        return True
    utilisateur.nom = compte.nom
    utilisateur.role = compte.role
    utilisateur.actif = True
    if not verifier(utilisateur.mot_de_passe_hash, mot_de_passe):
        utilisateur.mot_de_passe_hash = hacher(mot_de_passe)
    db.flush()
    return False
