"""Schémas du devis (story S4.1) : lignes saisies par le gérant, devis calculé renvoyé."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, StringConstraints

from app.models.devis import Devis, LigneDevis, TypeLigne
from app.models.ordre_travail import StatutOT
from app.schemas.commun import FactureLien, SansControle, vide_vers_none
from app.schemas.ordre import VehiculeOrdre
from app.services.calcul_devis import (
    LIGNES_MAX,
    PRIX_UNITAIRE_MAX_CENTIMES,
    lire_quantite,
)

MESSAGE_LIGNES_VIDES = "Le devis doit contenir au moins une ligne."
MESSAGE_LIGNES_MAX = f"{LIGNES_MAX} lignes au plus par devis."

Reference = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=40), SansControle] | None,
    BeforeValidator(vide_vers_none),
]
Designation = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200), SansControle
]
# Texte (« 1,5 », « 1.50 ») ou entier JSON, converti en Decimal sans passer par un flottant
# arrondi : nombre JSON à virgule, exposant, plus de deux décimales, zéro ou négatif → 422.
Quantite = Annotated[Decimal, BeforeValidator(lire_quantite)]
PrixUnitaire = Annotated[int, Field(strict=True, ge=0, le=PRIX_UNITAIRE_MAX_CENTIMES)]


def _nombre_de_lignes(lignes: list["LigneEntree"]) -> list["LigneEntree"]:
    if not lignes:
        raise ValueError(MESSAGE_LIGNES_VIDES)
    if len(lignes) > LIGNES_MAX:
        raise ValueError(MESSAGE_LIGNES_MAX)
    return lignes


class LigneEntree(BaseModel):
    type: TypeLigne
    reference: Reference = None
    designation: Designation
    quantite: Quantite
    prix_unitaire_ht_centimes: PrixUnitaire


class DevisEntree(BaseModel):
    """Création (POST /ordres/{id}/devis) ou remplacement des lignes (PUT /devis/{id})."""

    lignes: Annotated[list[LigneEntree], AfterValidator(_nombre_de_lignes)]


# --- Sorties -------------------------------------------------------------------------------


class LigneSortie(BaseModel):
    id: int
    type: TypeLigne
    reference: str | None
    designation: str
    # Texte à deux décimales (« 0.50 ») : aucune perte de précision côté JavaScript.
    quantite: str
    prix_unitaire_ht_centimes: int
    total_ht_centimes: int
    position: int


class TotauxSortie(BaseModel):
    main_oeuvre_ht_centimes: int
    pieces_ht_centimes: int
    total_ht_centimes: int
    total_tva_centimes: int
    total_ttc_centimes: int


class OrdreDuDevis(BaseModel):
    id: int
    numero: str
    statut: StatutOT


class ClientDuDevis(BaseModel):
    id: int
    nom: str
    prenom: str | None


class DevisDetail(BaseModel):
    id: int
    ordre: OrdreDuDevis
    lignes: list[LigneSortie]
    taux_tva_bp: int
    totaux: TotauxSortie
    cree_le: datetime
    modifie_le: datetime
    facture: FactureLien | None = None


class DevisResume(BaseModel):
    """Ligne de la liste « Devis & factures »."""

    id: int
    ordre: OrdreDuDevis
    vehicule: VehiculeOrdre
    client: ClientDuDevis
    total_ht_centimes: int
    total_ttc_centimes: int
    cree_le: datetime
    modifie_le: datetime
    facture: FactureLien | None = None


def quantite_texte(quantite: Decimal) -> str:
    return format(quantite.quantize(Decimal("0.01")), "f")


def sortie_ligne(ligne: LigneDevis) -> LigneSortie:
    return LigneSortie(
        id=ligne.id,
        type=ligne.type,
        reference=ligne.reference,
        designation=ligne.designation,
        quantite=quantite_texte(ligne.quantite),
        prix_unitaire_ht_centimes=ligne.prix_unitaire_ht_centimes,
        total_ht_centimes=ligne.total_ht_centimes,
        position=ligne.position,
    )


def totaux_enregistres(devis: Devis) -> TotauxSortie:
    """Totaux tels qu'enregistrés ; répartition main-d'œuvre / pièces par somme des lignes."""
    main_oeuvre = sum(
        ligne.total_ht_centimes for ligne in devis.lignes if ligne.type == TypeLigne.MAIN_OEUVRE
    )
    return TotauxSortie(
        main_oeuvre_ht_centimes=main_oeuvre,
        pieces_ht_centimes=devis.total_ht_centimes - main_oeuvre,
        total_ht_centimes=devis.total_ht_centimes,
        total_tva_centimes=devis.total_tva_centimes,
        total_ttc_centimes=devis.total_ttc_centimes,
    )


def _ordre(devis: Devis) -> OrdreDuDevis:
    return OrdreDuDevis(id=devis.ordre.id, numero=devis.ordre.numero, statut=devis.ordre.statut)


def lien_facture(devis: Devis) -> FactureLien | None:
    facture = devis.facture
    return FactureLien(id=facture.id, numero=facture.numero) if facture else None


def detail_devis(devis: Devis) -> DevisDetail:
    return DevisDetail(
        id=devis.id,
        ordre=_ordre(devis),
        lignes=[sortie_ligne(ligne) for ligne in devis.lignes],
        taux_tva_bp=devis.taux_tva_bp,
        totaux=totaux_enregistres(devis),
        cree_le=devis.cree_le,
        modifie_le=devis.modifie_le,
        facture=lien_facture(devis),
    )


def resume_devis(devis: Devis) -> DevisResume:
    vehicule = devis.ordre.vehicule
    client = vehicule.client
    return DevisResume(
        id=devis.id,
        ordre=_ordre(devis),
        vehicule=VehiculeOrdre.model_validate(vehicule),
        client=ClientDuDevis(id=client.id, nom=client.nom, prenom=client.prenom),
        total_ht_centimes=devis.total_ht_centimes,
        total_ttc_centimes=devis.total_ttc_centimes,
        cree_le=devis.cree_le,
        modifie_le=devis.modifie_le,
        facture=lien_facture(devis),
    )
