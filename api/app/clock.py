"""Horloge de l'application, injectée comme dépendance FastAPI.

Les tests remplacent `get_now` (dependency_overrides) pour avancer le temps, par exemple
pour vérifier la fin d'un blocage de compte sans attendre quinze minutes.
"""

from datetime import UTC, datetime


def get_now() -> datetime:
    """Instant présent, en UTC et avec fuseau."""
    return datetime.now(UTC)
