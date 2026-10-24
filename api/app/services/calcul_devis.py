"""Calcul d'un devis en centimes, sans erreur d'arrondi (story S4.1).

Fonctions pures, sans base de données :
- total d'une ligne = quantité × prix unitaire HT, arrondi au centime (ROUND_HALF_UP :
  0,5 centime monte au centime supérieur) ;
- total HT = somme des totaux des lignes (déjà arrondis : le client retrouve le total en
  additionnant les lignes qu'il lit) ;
- TVA = total HT × taux, arrondie au centime ; TTC = HT + TVA.

Tous les calculs passent par `Decimal` à partir d'entiers et de quantités décimales : aucun
nombre à virgule flottante. Exemple du backlog : 2 pièces à 40,00 € + 1 h à 60,00 € =
140,00 € HT, 28,00 € de TVA, 168,00 € TTC.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol

from app.models.devis import TypeLigne

QUANTITE_MAX = Decimal("9999.99")
PRIX_UNITAIRE_MAX_CENTIMES = 10_000_000  # 100 000,00 € HT
LIGNES_MAX = 100
CENTIEME = Decimal("0.01")
# Au-delà, le texte ne peut pas être une quantité valide : refusé sans le convertir.
LONGUEUR_SAISIE_MAX = 32

MESSAGE_QUANTITE_INVALIDE = "Quantité invalide : nombre attendu, par exemple 1 ou 0,5."
MESSAGE_QUANTITE_POSITIVE = "La quantité doit être supérieure à 0."
MESSAGE_QUANTITE_MAX = "La quantité ne peut pas dépasser 9 999,99."
MESSAGE_QUANTITE_DECIMALES = "Deux décimales au plus pour la quantité."


class LigneACalculer(Protocol):
    @property
    def type(self) -> TypeLigne: ...

    @property
    def quantite(self) -> Decimal: ...

    @property
    def prix_unitaire_ht_centimes(self) -> int: ...


@dataclass(frozen=True)
class Totaux:
    main_oeuvre_ht_centimes: int
    pieces_ht_centimes: int
    total_ht_centimes: int
    total_tva_centimes: int
    total_ttc_centimes: int


def arrondi_centime(valeur: Decimal) -> int:
    """Arrondi à l'entier le plus proche, 0,5 vers le haut (valeurs positives)."""
    return int(valeur.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def lire_quantite(valeur: object) -> Decimal:
    """Quantité saisie (texte « 1,5 » ou « 1.50 », entier ou décimal JSON) vers Decimal.

    Lève ValueError (message en français, 422 sur le champ) si elle n'est pas un nombre fini,
    si elle est nulle ou négative, dépasse 9 999,99 ou a plus de deux décimales : une
    quantité n'est jamais arrondie en silence."""
    if isinstance(valeur, bool) or not isinstance(valeur, str | int | float | Decimal):
        raise ValueError(MESSAGE_QUANTITE_INVALIDE)
    texte = str(valeur).strip().replace(",", ".")
    if len(texte) > LONGUEUR_SAISIE_MAX:
        raise ValueError(MESSAGE_QUANTITE_INVALIDE)
    try:
        quantite = Decimal(texte)
    except InvalidOperation:
        raise ValueError(MESSAGE_QUANTITE_INVALIDE) from None
    if not quantite.is_finite():
        raise ValueError(MESSAGE_QUANTITE_INVALIDE)
    if quantite <= 0:
        raise ValueError(MESSAGE_QUANTITE_POSITIVE)
    if quantite > QUANTITE_MAX:
        raise ValueError(MESSAGE_QUANTITE_MAX)
    if quantite != quantite.quantize(CENTIEME):
        raise ValueError(MESSAGE_QUANTITE_DECIMALES)
    return quantite.quantize(CENTIEME)


def total_ligne(quantite: Decimal, prix_unitaire_ht_centimes: int) -> int:
    """Quantité × prix unitaire HT, arrondi au centime : 1,25 × 9,99 € = 12,4875 € → 12,49 €."""
    return arrondi_centime(quantite * Decimal(prix_unitaire_ht_centimes))


def tva(total_ht_centimes: int, taux_bp: int) -> int:
    """TVA arrondie au centime : taux en points de base (2000 = 20 %)."""
    return arrondi_centime(Decimal(total_ht_centimes) * Decimal(taux_bp) / Decimal(10_000))


def totaux(lignes: Iterable[LigneACalculer], taux_bp: int) -> Totaux:
    main_oeuvre = 0
    pieces = 0
    for ligne in lignes:
        montant = total_ligne(ligne.quantite, ligne.prix_unitaire_ht_centimes)
        if ligne.type == TypeLigne.MAIN_OEUVRE:
            main_oeuvre += montant
        else:
            pieces += montant
    total_ht = main_oeuvre + pieces
    montant_tva = tva(total_ht, taux_bp)
    return Totaux(
        main_oeuvre_ht_centimes=main_oeuvre,
        pieces_ht_centimes=pieces,
        total_ht_centimes=total_ht,
        total_tva_centimes=montant_tva,
        total_ttc_centimes=total_ht + montant_tva,
    )
