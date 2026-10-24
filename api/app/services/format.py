"""Formats d'affichage côté API (messages, PDF), alignés sur ceux de l'interface."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

NBSP = " "

JOURS_COURTS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
MOIS_COURTS = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)  # fmt: skip


def formater_heure(instant: datetime, fuseau: str = "Europe/Paris") -> str:
    """« 15 h 02 » dans le fuseau du garage, espaces insécables comme dans l'interface."""
    local = instant.astimezone(ZoneInfo(fuseau))
    return f"{local.hour}{NBSP}h{NBSP}{local.minute:02d}"


def formater_km(kilometres: int) -> str:
    """« 84 312 km » : milliers séparés par une espace insécable."""
    return f"{kilometres:,}".replace(",", NBSP) + f"{NBSP}km"


def formater_euros(centimes: int) -> str:
    """Centimes (entier) vers « 2 846,50 € » : virgule, milliers et symbole insécables."""
    signe = "-" if centimes < 0 else ""
    euros, reste = divmod(abs(centimes), 100)
    return f"{signe}{euros:,}".replace(",", NBSP) + f",{reste:02d}{NBSP}€"


def formater_date(jour: date) -> str:
    """« 24/10/2026 » (date d'une facture)."""
    return jour.strftime("%d/%m/%Y")


def formater_date_courte(jour: date) -> str:
    """« sam. 24 oct. » (jour de la semaine et mois abrégés, comme l'interface)."""
    return f"{JOURS_COURTS[jour.weekday()]} {jour.day} {MOIS_COURTS[jour.month - 1]}"


def formater_quantite(quantite: Decimal, main_oeuvre: bool) -> str:
    """« 0,5 h » pour la main-d'œuvre, « 1 » ou « 2,25 » pour une pièce."""
    texte = format(quantite.normalize(), "f").replace(".", ",")
    return f"{texte}{NBSP}h" if main_oeuvre else texte


def formater_duree(minutes: int) -> str:
    """« 40 min », « 2 h 40 », « 3 h »."""
    heures, reste = divmod(max(0, minutes), 60)
    if heures == 0:
        return f"{reste}{NBSP}min"
    return f"{heures}{NBSP}h" if reste == 0 else f"{heures}{NBSP}h{NBSP}{reste:02d}"
