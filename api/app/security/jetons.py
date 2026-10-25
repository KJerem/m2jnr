"""Jeton de session : JWT signé HS256, transporté dans un cookie httpOnly."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from fastapi import Response

from app.config import Settings
from app.models.utilisateur import Role, Utilisateur

ALGORITHME = "HS256"


@dataclass(frozen=True)
class SessionJeton:
    utilisateur_id: int
    role: Role
    emise_le: datetime
    expire_le: datetime


def creer_jeton_session(
    utilisateur_id: int, role: Role, maintenant: datetime, settings: Settings
) -> str:
    expire = maintenant + timedelta(minutes=settings.session_duration_minutes)
    charge = {
        "sub": str(utilisateur_id),
        "role": role.value,
        "iat": int(maintenant.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(charge, settings.secret_key, algorithm=ALGORITHME)


def lire_jeton_session(jeton: str, maintenant: datetime, settings: Settings) -> SessionJeton | None:
    """Décode et vérifie le jeton ; None s'il est falsifié, mal formé ou expiré.

    L'expiration est comparée à l'horloge injectée (et non à l'heure système) pour être testable.
    """
    try:
        charge = jwt.decode(
            jeton,
            settings.secret_key,
            algorithms=[ALGORITHME],
            options={
                "require": ["sub", "role", "iat", "exp"],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
        emise = datetime.fromtimestamp(int(charge["iat"]), tz=maintenant.tzinfo)
        expire = datetime.fromtimestamp(int(charge["exp"]), tz=maintenant.tzinfo)
        session = SessionJeton(int(charge["sub"]), Role(charge["role"]), emise, expire)
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        return None
    if session.expire_le <= maintenant:
        return None
    return session


def poser_cookie_session(
    response: Response, utilisateur: Utilisateur, maintenant: datetime, settings: Settings
) -> None:
    """Cookie de session httpOnly : connexion, premier compte du garage, et nouveau mot de
    passe que le gérant se donne à lui-même (sa session en cours reste ouverte)."""
    jeton = creer_jeton_session(utilisateur.id, utilisateur.role, maintenant, settings)
    response.set_cookie(
        settings.session_cookie_name,
        jeton,
        max_age=settings.session_duration_minutes * 60,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
