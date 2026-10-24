"""Numéros de téléphone français : normalisation sur 10 chiffres « 0XXXXXXXXX »."""

import re

MESSAGE_TELEPHONE_INVALIDE = "Numéro de téléphone français invalide."

_SEPARATEURS = re.compile(r"[\s.\-()/]")
_NATIONAL = re.compile(r"^0[1-9]\d{8}$")


def normaliser_telephone(valeur: str) -> str:
    """« 06 12 34 56 78 », « 06.12.34.56.78 », « +33 6 12 34 56 78 », « 0033612345678 »
    → « 0612345678 ». Lève ValueError (message en français) pour tout autre format."""
    chiffres = _SEPARATEURS.sub("", valeur.strip())
    if chiffres.startswith("+33"):
        chiffres = "0" + chiffres[3:]
    elif chiffres.startswith("0033"):
        chiffres = "0" + chiffres[4:]
    if not _NATIONAL.fullmatch(chiffres):
        raise ValueError(MESSAGE_TELEPHONE_INVALIDE)
    return chiffres


def formater_telephone(telephone: str) -> str:
    """« 0612345678 » → « 06 12 34 56 78 » (affichage)."""
    return " ".join(telephone[i : i + 2] for i in range(0, len(telephone), 2))
