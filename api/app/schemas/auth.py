"""Schémas de la connexion et de la session."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.utilisateur import Role


class ConnexionEntree(BaseModel):
    # Pas de contrôle de format sur l'e-mail : toute erreur reste « Identifiants invalides. ».
    email: str = Field(min_length=1, max_length=254)
    mot_de_passe: str = Field(min_length=1, max_length=1024)


class UtilisateurSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nom: str
    role: Role


class SessionSortie(BaseModel):
    utilisateur: UtilisateurSortie


class CsrfSortie(BaseModel):
    jeton: str
