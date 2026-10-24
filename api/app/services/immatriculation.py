"""Immatriculations françaises (SIV) et numéros VIN : normalisation et contrôle de format."""

import re

MESSAGE_IMMATRICULATION_INVALIDE = "Immatriculation invalide (format AA-123-AA)."
MESSAGE_VIN_INVALIDE = "VIN invalide (17 caractères, sans I, O ni Q)."

# Lettres autorisées par le SIV : A à Z sauf I, O et U (confusion avec 1, 0 et V).
_LETTRES = "[A-HJ-NP-TV-Z]"
_SIV = re.compile(rf"^({_LETTRES}{{2}})(\d{{3}})({_LETTRES}{{2}})$")
_VIN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_SEPARATEURS = re.compile(r"[\s\-]")


def normaliser_immatriculation(valeur: str) -> str:
    """« gh 482 kl », « GH482KL », « gh-482-kl » → « GH-482-KL ».

    Majuscules, espaces et tirets retirés, puis contrôle du format SIV AA123AA (bloc central
    000 interdit). Lève ValueError avec un message en français sinon.
    """
    compacte = _SEPARATEURS.sub("", valeur).upper()
    correspondance = _SIV.fullmatch(compacte)
    if correspondance is None or correspondance.group(2) == "000":
        raise ValueError(MESSAGE_IMMATRICULATION_INVALIDE)
    return "-".join(correspondance.groups())


def normaliser_vin(valeur: str) -> str:
    """VIN en majuscules sans espaces ; 17 caractères, ni I, ni O, ni Q."""
    vin = re.sub(r"\s", "", valeur).upper()
    if not _VIN.fullmatch(vin):
        raise ValueError(MESSAGE_VIN_INVALIDE)
    return vin
