"""Dépendances FastAPI d'authentification et de contrôle des rôles."""

from collections.abc import Callable
from datetime import datetime

from fastapi import Depends, Request, status

from app.clock import get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.errors import AppError, forbidden
from app.models.utilisateur import Role, Utilisateur
from app.security.jetons import lire_jeton_session


def non_authentifie() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "non_authentifie", "Veuillez vous connecter.")


def get_current_user(
    request: Request,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> Utilisateur:
    """Utilisateur de la session ; 401 si le cookie manque, est invalide ou expiré, ou si le
    compte a été désactivé depuis. Le rôle est relu en base, pas dans le jeton."""
    jeton = request.cookies.get(settings.session_cookie_name)
    if not jeton:
        raise non_authentifie()
    session = lire_jeton_session(jeton, maintenant, settings)
    if session is None:
        raise non_authentifie()
    utilisateur = db.get(Utilisateur, session.utilisateur_id)
    if utilisateur is None or not utilisateur.actif:
        raise non_authentifie()
    return utilisateur


def require_role(*roles: Role) -> Callable[..., Utilisateur]:
    """Dépendance qui exige l'un des rôles donnés : 401 sans session, 403 pour un autre rôle.

    S'emploie au niveau d'un routeur (`dependencies=[Depends(require_role(Role.GERANT))]`)
    ou d'une route, en paramètre, pour récupérer l'utilisateur courant.
    """
    autorises = frozenset(roles)

    def _verifier(utilisateur: Utilisateur = Depends(get_current_user)) -> Utilisateur:
        if utilisateur.role not in autorises:
            raise forbidden("Accès refusé pour votre rôle.")
        return utilisateur

    return _verifier
