"""Horloge de l'application, injectée comme dépendance FastAPI.

Les tests remplacent `get_now` (dependency_overrides) pour avancer le temps, par exemple
pour vérifier la fin d'un blocage de compte sans attendre quinze minutes.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def get_now() -> datetime:
    """Instant présent, en UTC et avec fuseau."""
    return datetime.now(UTC)


def date_locale(instant: datetime, fuseau: str = "Europe/Paris") -> date:
    """Date du jour dans le fuseau du garage (et non en UTC, décalée la nuit)."""
    return instant.astimezone(ZoneInfo(fuseau)).date()
