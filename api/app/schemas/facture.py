"""Schémas de la facture (story S4.3) : uniquement des données figées à l'émission."""

from datetime import date, datetime

from pydantic import BaseModel

from app.models.devis import TypeLigne
from app.models.facture import Facture, LigneFacture
from app.schemas.devis import LigneSortie, TotauxSortie, quantite_texte


class OrdreDeLaFacture(BaseModel):
    id: int
    numero: str


class ClientFige(BaseModel):
    nom: str
    prenom: str | None
    telephone: str | None
    email: str | None


class ClientFigeResume(BaseModel):
    nom: str
    prenom: str | None


class VehiculeFige(BaseModel):
    immatriculation: str
    marque: str
    modele: str
    kilometrage: int


class VehiculeFigeResume(BaseModel):
    immatriculation: str
    marque: str
    modele: str


class GarageFige(BaseModel):
    raison_sociale: str
    adresse: str
    siret: str
    tva_intracommunautaire: str
    capital: str
    rcs: str
    telephone: str
    email: str


class FactureResume(BaseModel):
    """Ligne de l'onglet « Factures »."""

    id: int
    numero: str
    emise_le: datetime
    echeance: date
    ordre: OrdreDeLaFacture
    client: ClientFigeResume
    vehicule: VehiculeFigeResume
    total_ht_centimes: int
    total_ttc_centimes: int


class FactureDetail(BaseModel):
    id: int
    numero: str
    emise_le: datetime
    echeance: date
    devis_id: int
    ordre: OrdreDeLaFacture
    client: ClientFige
    vehicule: VehiculeFige
    garage: GarageFige
    lignes: list[LigneSortie]
    taux_tva_bp: int
    totaux: TotauxSortie


def sortie_ligne_facture(ligne: LigneFacture) -> LigneSortie:
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


def totaux_facture(facture: Facture) -> TotauxSortie:
    main_oeuvre = sum(
        ligne.total_ht_centimes for ligne in facture.lignes if ligne.type == TypeLigne.MAIN_OEUVRE
    )
    return TotauxSortie(
        main_oeuvre_ht_centimes=main_oeuvre,
        pieces_ht_centimes=facture.total_ht_centimes - main_oeuvre,
        total_ht_centimes=facture.total_ht_centimes,
        total_tva_centimes=facture.total_tva_centimes,
        total_ttc_centimes=facture.total_ttc_centimes,
    )


def _ordre(facture: Facture) -> OrdreDeLaFacture:
    return OrdreDeLaFacture(id=facture.ordre.id, numero=facture.ordre.numero)


def resume_facture(facture: Facture) -> FactureResume:
    return FactureResume(
        id=facture.id,
        numero=facture.numero,
        emise_le=facture.emise_le,
        echeance=facture.echeance,
        ordre=_ordre(facture),
        client=ClientFigeResume.model_validate(facture.client_fige),
        vehicule=VehiculeFigeResume.model_validate(facture.vehicule_fige),
        total_ht_centimes=facture.total_ht_centimes,
        total_ttc_centimes=facture.total_ttc_centimes,
    )


def detail_facture(facture: Facture) -> FactureDetail:
    return FactureDetail(
        id=facture.id,
        numero=facture.numero,
        emise_le=facture.emise_le,
        echeance=facture.echeance,
        devis_id=facture.devis_id,
        ordre=_ordre(facture),
        client=ClientFige.model_validate(facture.client_fige),
        vehicule=VehiculeFige.model_validate(facture.vehicule_fige),
        garage=GarageFige.model_validate(facture.garage_fige),
        lignes=[sortie_ligne_facture(ligne) for ligne in facture.lignes],
        taux_tva_bp=facture.taux_tva_bp,
        totaux=totaux_facture(facture),
    )
