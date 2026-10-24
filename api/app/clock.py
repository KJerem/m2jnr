"""Horloge de l'application, injectée comme dépendance FastAPI.

Les tests remplacent `get_now` (dependency_overrides) pour avancer le temps, par exemple
pour vérifier la fin d'un blocage de compte sans attendre quinze minutes.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def get_now() -> datetime:
    """Instant présent, en UTC et avec fuseau."""
    return datetime.now(UTC)


def date_locale(instant: datetime, fuseau: str = "Europe/Paris") -> date:
    """Date du jour dans le fuseau du garage (et non en UTC, décalée la nuit)."""
    return instant.astimezone(ZoneInfo(fuseau)).date()


def debut_jour(jour: date, fuseau: str = "Europe/Paris") -> datetime:
    """Minuit du jour donné dans le fuseau du garage, exprimé en UTC."""
    return datetime.combine(jour, time(0, 0), tzinfo=ZoneInfo(fuseau)).astimezone(UTC)


def bornes_jour(jour: date, fuseau: str = "Europe/Paris") -> tuple[datetime, datetime]:
    """Intervalle [minuit, minuit du lendemain[ du jour local, en UTC.

    Un jour de changement d'heure dure 23 ou 25 heures : on calcule chaque minuit séparément
    plutôt que d'ajouter 24 heures.
    """
    return debut_jour(jour, fuseau), debut_jour(jour + timedelta(days=1), fuseau)


def instant_local(valeur: datetime, fuseau: str = "Europe/Paris") -> datetime:
    """Une date et heure sans fuseau est lue à l'heure du garage ; le résultat est en UTC."""
    if valeur.tzinfo is None:
        valeur = valeur.replace(tzinfo=ZoneInfo(fuseau))
    return valeur.astimezone(UTC)
