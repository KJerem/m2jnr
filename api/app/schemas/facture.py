"""Schémas de la facture (story S4.3) : données figées à l'émission ; paiements et solde
(story S4.4), calculés à chaque lecture."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

from app.models.devis import TypeLigne
from app.models.facture import Facture, LigneFacture
from app.models.paiement import ModePaiement, Paiement
from app.schemas.commun import InstantFacultatif, SansControle, vide_vers_none
from app.schemas.devis import LigneSortie, TotauxSortie, quantite_texte
from app.schemas.ordre import UtilisateurResume
from app.services.paiements import StatutPaiement, en_retard, solde_facture

# Plafond d'un montant saisi (10 millions d'euros) : bien au-delà d'une facture de garage,
# loin des limites d'un BIGINT.
MONTANT_MAX_CENTIMES = 1_000_000_000

ReferencePaiement = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=60), SansControle] | None,
    BeforeValidator(vide_vers_none),
]


class PaiementEntree(BaseModel):
    """POST /factures/{id}/paiements. `recu_le` vaut l'instant présent s'il est omis ; une
    date et heure sans fuseau est lue à l'heure du garage."""

    montant_centimes: Annotated[int, Field(strict=True, gt=0, le=MONTANT_MAX_CENTIMES)]
    mode: ModePaiement
    recu_le: InstantFacultatif = None
    reference: ReferencePaiement = None


class PaiementSortie(BaseModel):
    id: int
    montant_centimes: int
    mode: ModePaiement
    recu_le: datetime
    reference: str | None
    cree_par: UtilisateurResume


class SuiviPaiement(BaseModel):
    """Champs de paiement communs à la liste et au détail (story S4.4)."""

    paiements: list[PaiementSortie]
    deja_paye_centimes: int
    reste_centimes: int
    statut_paiement: StatutPaiement
    # Non payée et échéance dépassée (jour de Paris).
    en_retard: bool


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


class FactureResume(SuiviPaiement):
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


class FactureDetail(SuiviPaiement):
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


def sortie_paiement(paiement: Paiement) -> PaiementSortie:
    return PaiementSortie(
        id=paiement.id,
        montant_centimes=paiement.montant_centimes,
        mode=paiement.mode,
        recu_le=paiement.recu_le,
        reference=paiement.reference,
        cree_par=UtilisateurResume(id=paiement.createur.id, nom=paiement.createur.nom),
    )


def suivi_paiement(facture: Facture, aujourd_hui: date) -> SuiviPaiement:
    s = solde_facture(facture)
    return SuiviPaiement(
        paiements=[sortie_paiement(p) for p in facture.paiements],
        deja_paye_centimes=s.deja_paye_centimes,
        reste_centimes=s.reste_centimes,
        statut_paiement=s.statut,
        en_retard=en_retard(s.statut, facture.echeance, aujourd_hui),
    )


def resume_facture(facture: Facture, aujourd_hui: date) -> FactureResume:
    return FactureResume(
        **dict(suivi_paiement(facture, aujourd_hui)),
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


def detail_facture(facture: Facture, aujourd_hui: date) -> FactureDetail:
    return FactureDetail(
        **dict(suivi_paiement(facture, aujourd_hui)),
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
