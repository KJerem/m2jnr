"""Schémas de la connexion et de la session."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.utilisateur import Role


class ConnexionEntree(BaseModel):
    # Pas de contrôle de format sur l'e-mail : toute erreur reste « Identifiants invalides. ».
    email: str = Field(min_length=1, max_length=254)
    mot_de_passe: str = Field(min_length=1, max_length=1024)


class UtilisateurSession(BaseModel):
    """Employé connecté : prénom et nom séparés (sprint 5) et nom affiché (« Karim B. »)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    prenom: str
    nom: str
    nom_affiche: str
    role: Role


class SessionSortie(BaseModel):
    utilisateur: UtilisateurSession


class CsrfSortie(BaseModel):
    jeton: str
