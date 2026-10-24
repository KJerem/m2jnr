"""Facture émise avant les mentions d'adresse et de date de prestation (sprints 3 et 4) :
copie figée sans adresse du client, sans date de prestation.

Son PDF de référence (`donnees/facture_sprint3.pdf`) a été produit par le code du sprint 3,
avant l'ajout des mentions : une facture déjà émise doit toujours donner les mêmes octets.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models import Facture, LigneFacture, OrdreTravail, TypeLigne


def facture_sprint3() -> Facture:
    """Facture en mémoire (jamais enregistrée), comme une facture émise au sprint 3."""
    facture = Facture(
        id=1,
        numero="F-2026-001",
        emise_le=datetime(2026, 12, 4, 9, 40, tzinfo=UTC),
        echeance=date(2027, 1, 3),
        client_fige={
            "nom": "Laurent",
            "prenom": "Claire",
            "telephone": "0612483075",
            "email": "claire.laurent@exemple.test",
        },
        vehicule_fige={
            "immatriculation": "GH-482-KL",
            "marque": "Peugeot",
            "modele": "308 SW",
            "kilometrage": 84_312,
        },
        garage_fige={
            "raison_sociale": "Garage Établi SARL",
            "adresse": "12 rue des Ateliers, 69007 Lyon",
            "siret": "000 000 000 00000",
            "tva_intracommunautaire": "FR00000000000",
            "capital": "10 000 €",
            "rcs": "RCS Lyon 000 000 000",
            "telephone": "04 00 00 00 00",
            "email": "contact@garage.test",
        },
        taux_tva_bp=2000,
        total_ht_centimes=14_000,
        total_tva_centimes=2_800,
        total_ttc_centimes=16_800,
    )
    facture.ordre = OrdreTravail(numero="OT-2026-001")
    facture.lignes = [
        LigneFacture(
            type=TypeLigne.PIECE,
            reference="PLQ-308-AV",
            designation="Jeu de plaquettes avant",
            quantite=Decimal("2.00"),
            prix_unitaire_ht_centimes=4_000,
            total_ht_centimes=8_000,
            position=0,
        ),
        LigneFacture(
            type=TypeLigne.MAIN_OEUVRE,
            reference="MO-FREIN-AV",
            designation="Remplacement plaquettes avant",
            quantite=Decimal("1.00"),
            prix_unitaire_ht_centimes=6_000,
            total_ht_centimes=6_000,
            position=1,
        ),
    ]
    return facture
