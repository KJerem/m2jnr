"""Formats d'affichage côté API (messages d'erreur), alignés sur ceux de l'interface."""

from datetime import datetime
from zoneinfo import ZoneInfo

NBSP = " "


def formater_heure(instant: datetime, fuseau: str = "Europe/Paris") -> str:
    """« 15 h 02 » dans le fuseau du garage, espaces insécables comme dans l'interface."""
    local = instant.astimezone(ZoneInfo(fuseau))
    return f"{local.hour}{NBSP}h{NBSP}{local.minute:02d}"
