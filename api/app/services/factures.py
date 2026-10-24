"""Factures : émission à partir d'un devis, consultation, liste (story S4.3).

Règles :
- une facture s'établit sur un devis accepté par le client (story S4.2) qui a au moins une
  ligne, quand l'intervention est terminée (OT « Prêt » ou « Livré ») ; un devis n'est
  facturé qu'une fois (409 sinon, avec le numéro de la facture existante) ;
- ordre des contrôles, tous avant la réservation du numéro (le premier qui échoue répond) :
  1. devis déjà facturé → 409 `devis_deja_facture` (le cas le plus précis : la facture
     existe, on donne son numéro) ;
  2. devis non accepté → 409 `devis_non_accepte` ;
  3. devis sans ligne → 409 `devis_vide` ;
  4. intervention ni « Prêt » ni « Livré » → 409 `ordre_non_termine` ;
- le numéro « F-AAAA-nnn » (année du jour à Paris) est réservé dans la MÊME transaction que
  la facture : une émission annulée annule aussi l'incrément, aucun numéro ne manque ;
- le client, le véhicule, les mentions du garage, les lignes et les montants sont recopiés ;
  les totaux sont recalculés à partir des lignes figées et doivent égaler ceux du devis ;
- échéance = jour d'émission à Paris + délai de paiement (GARAGE_DELAI_PAIEMENT_JOURS) ;
- mentions de l'art. 242 nonies A du CGI (sprint 4) : l'adresse du client est recopiée avec
  son identité, et la date de la prestation est figée : jour de Paris du dernier passage de
  l'OT à « Prêt » (fin des travaux), à défaut de sa clôture ; les factures émises avant
  gardent leur copie sans adresse ni date de prestation ;
- une fois facturé, le devis n'est plus modifiable (409 « devis_facture »).

Verrous, toujours dans cet ordre : le devis (SELECT … FOR UPDATE, posé par l'appelant), puis
le compteur des factures. Deux émissions simultanées d'un même devis s'attendent : la seconde
voit la facture de la première et répond 409.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from psycopg import errors as erreurs_pg
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.clock import date_locale
from app.config import Settings
from app.db import id_possible
from app.errors import conflict, not_found
from app.models.devis import Devis
from app.models.facture import Facture, LigneFacture
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT
from app.models.paiement import Paiement
from app.models.utilisateur import Utilisateur
from app.services import calcul_devis
from app.services.numerotation import PREFIXE_FACTURE, TYPE_FACTURE, prochain_numero
from app.services.paiements import StatutPaiement, condition_statut
from app.services.statut_devis import verifier_accepte

MESSAGE_FACTURE_INTROUVABLE = "Facture introuvable."
MESSAGE_DEJA_FACTURE = "Ce devis est déjà facturé."
MESSAGE_DEVIS_VIDE = "Le devis ne contient aucune ligne : il n'y a rien à facturer."
MESSAGE_ORDRE_NON_TERMINE = "La facture s'établit quand l'intervention est terminée."
MESSAGE_DEVIS_FACTURE = "Ce devis est facturé : il ne peut plus être modifié."

STATUTS_FACTURABLES = frozenset({StatutOT.TERMINE, StatutOT.LIVRE})
NOM_CONTRAINTE_DEVIS_UNIQUE = "uq_facture_devis_id"


class TotauxIncoherentsError(RuntimeError):
    """Les totaux recalculés à partir des lignes figées diffèrent de ceux du devis."""


def facture_du_devis(db: Session, devis_id: int) -> Facture | None:
    """Facture du devis, relue en base (et non dans la session) : après le verrou du devis,
    une facture validée entre-temps par une autre transaction est vue."""
    return db.scalars(
        select(Facture)
        .where(Facture.devis_id == devis_id)
        .execution_options(populate_existing=True)
    ).one_or_none()


def facture_de_l_ordre(db: Session, ordre_id: int) -> Facture | None:
    """Facture la plus récente de l'OT, ou None."""
    return db.scalars(
        select(Facture)
        .where(Facture.ordre_travail_id == ordre_id)
        .order_by(Facture.id.desc())
        .limit(1)
    ).first()


def verifier_devis_modifiable(db: Session, devis: Devis) -> None:
    """409 si le devis (verrouillé par l'appelant) a été facturé."""
    facture = facture_du_devis(db, devis.id)
    if facture is not None:
        raise conflict(
            "devis_facture", MESSAGE_DEVIS_FACTURE, facture_id=facture.id, numero=facture.numero
        )


def garage_fige(settings: Settings) -> dict[str, Any]:
    """Mentions légales du garage à la date d'émission."""
    return {
        "raison_sociale": settings.garage_raison_sociale,
        "adresse": settings.garage_adresse,
        "siret": settings.garage_siret,
        "tva_intracommunautaire": settings.garage_tva_intra,
        "capital": settings.garage_capital,
        "rcs": settings.garage_rcs,
        "telephone": settings.garage_telephone,
        "email": settings.garage_email,
    }


def client_fige(ordre: OrdreTravail) -> dict[str, Any]:
    client = ordre.vehicule.client
    return {
        "nom": client.nom,
        "prenom": client.prenom,
        "telephone": client.telephone,
        "email": client.email,
        "adresse": client.adresse,
        "code_postal": client.code_postal,
        "ville": client.ville,
    }


def date_de_prestation(db: Session, ordre: OrdreTravail, fuseau: str) -> date | None:
    """Jour de Paris de la fin de la prestation : dernier passage à « Prêt », à défaut la
    clôture de l'OT (livraison), à défaut None."""
    pret = db.scalar(
        select(func.max(HistoriqueStatut.change_le)).where(
            HistoriqueStatut.ordre_travail_id == ordre.id,
            HistoriqueStatut.nouveau == StatutOT.TERMINE,
        )
    )
    fin = pret or ordre.cloture_le
    return date_locale(fin, fuseau) if fin is not None else None


def vehicule_fige(ordre: OrdreTravail) -> dict[str, Any]:
    """Le kilométrage est celui relevé à l'entrée de l'OT, sinon celui de la fiche."""
    vehicule = ordre.vehicule
    kilometrage = (
        ordre.kilometrage_entree if ordre.kilometrage_entree is not None else vehicule.kilometrage
    )
    return {
        "immatriculation": vehicule.immatriculation,
        "marque": vehicule.marque,
        "modele": vehicule.modele,
        "kilometrage": kilometrage,
    }


def _verifier_totaux(devis: Devis, lignes: list[LigneFacture]) -> calcul_devis.Totaux:
    totaux = calcul_devis.totaux(lignes, devis.taux_tva_bp)
    attendus = (devis.total_ht_centimes, devis.total_tva_centimes, devis.total_ttc_centimes)
    obtenus = (totaux.total_ht_centimes, totaux.total_tva_centimes, totaux.total_ttc_centimes)
    lignes_justes = all(
        ligne.total_ht_centimes
        == calcul_devis.total_ligne(ligne.quantite, ligne.prix_unitaire_ht_centimes)
        for ligne in lignes
    )
    if obtenus != attendus or not lignes_justes:
        raise TotauxIncoherentsError(f"Devis {devis.id} : {obtenus} au lieu de {attendus}.")
    return totaux


def etablir_facture(
    db: Session, devis: Devis, auteur: Utilisateur, maintenant: datetime, settings: Settings
) -> Facture:
    """Émet la facture du devis, verrouillé par l'appelant. Toutes les vérifications passent
    AVANT la réservation du numéro."""
    existante = facture_du_devis(db, devis.id)
    if existante is not None:
        raise conflict(
            "devis_deja_facture",
            MESSAGE_DEJA_FACTURE,
            facture_id=existante.id,
            numero=existante.numero,
        )
    verifier_accepte(devis)
    if not devis.lignes:
        raise conflict("devis_vide", MESSAGE_DEVIS_VIDE)
    ordre = devis.ordre
    if ordre.statut not in STATUTS_FACTURABLES:
        raise conflict("ordre_non_termine", MESSAGE_ORDRE_NON_TERMINE, statut=ordre.statut.value)

    lignes = [
        LigneFacture(
            type=ligne.type,
            reference=ligne.reference,
            designation=ligne.designation,
            quantite=ligne.quantite,
            prix_unitaire_ht_centimes=ligne.prix_unitaire_ht_centimes,
            total_ht_centimes=ligne.total_ht_centimes,
            position=i,
        )
        for i, ligne in enumerate(devis.lignes)
    ]
    totaux = _verifier_totaux(devis, lignes)
    jour = date_locale(maintenant, settings.timezone)
    facture = Facture(
        numero=prochain_numero(db, TYPE_FACTURE, jour.year, PREFIXE_FACTURE),
        devis_id=devis.id,
        ordre_travail_id=ordre.id,
        emise_le=maintenant,
        echeance=jour + timedelta(days=settings.garage_delai_paiement_jours),
        date_prestation=date_de_prestation(db, ordre, settings.timezone),
        client_fige=client_fige(ordre),
        vehicule_fige=vehicule_fige(ordre),
        garage_fige=garage_fige(settings),
        taux_tva_bp=devis.taux_tva_bp,
        total_ht_centimes=totaux.total_ht_centimes,
        total_tva_centimes=totaux.total_tva_centimes,
        total_ttc_centimes=totaux.total_ttc_centimes,
        cree_par=auteur.id,
        cree_le=maintenant,
        lignes=lignes,
    )
    try:
        # Point de sauvegarde : si une émission simultanée a déjà facturé ce devis (malgré le
        # verrou, par exemple hors de l'API), la contrainte unique refuse la ligne et la
        # réponse reste un 409 clair. L'appelant annule toute la transaction, compteur compris.
        with db.begin_nested():
            db.add(facture)
            db.flush()
    except IntegrityError as exc:
        diag = getattr(exc.orig, "diag", None)
        if not (
            isinstance(exc.orig, erreurs_pg.UniqueViolation)
            and getattr(diag, "constraint_name", None) == NOM_CONTRAINTE_DEVIS_UNIQUE
        ):
            raise
        autre = facture_du_devis(db, devis.id)
        raise conflict(
            "devis_deja_facture",
            MESSAGE_DEJA_FACTURE,
            facture_id=autre.id if autre else None,
            numero=autre.numero if autre else None,
        ) from exc
    return facture


def obtenir_facture(db: Session, facture_id: int, *, verrouiller: bool = False) -> Facture:
    """Facture avec ses lignes, son OT et ses paiements (et leur auteur).

    `verrouiller` pose SELECT … FOR UPDATE sur la ligne de la facture (encaissement, story
    S4.4) : un verrou de ligne ne déclenche pas le trigger d'immuabilité (qui ne vise que
    UPDATE et DELETE). Les données sont alors relues en base."""
    facture = None
    if id_possible(facture_id):
        requete = (
            select(Facture)
            .where(Facture.id == facture_id)
            .options(
                selectinload(Facture.lignes),
                selectinload(Facture.ordre),
                selectinload(Facture.paiements).selectinload(Paiement.createur),
            )
        )
        if verrouiller:
            requete = requete.with_for_update(of=Facture).execution_options(populate_existing=True)
        facture = db.scalars(requete).one_or_none()
    if facture is None:
        raise not_found(MESSAGE_FACTURE_INTROUVABLE)
    return facture


@dataclass(frozen=True)
class PageFactures:
    elements: list[Facture]
    total: int


def _filtrer(
    requete: Select[Facture], depuis: datetime | None, avant: datetime | None
) -> Select[Facture]:
    if depuis is not None:
        requete = requete.where(Facture.emise_le >= depuis)
    if avant is not None:
        requete = requete.where(Facture.emise_le < avant)
    return requete


def lister_factures(
    db: Session,
    depuis: datetime | None,
    avant: datetime | None,
    page: int,
    taille: int,
    statut_paiement: StatutPaiement | None = None,
) -> PageFactures:
    """Factures de la plus récente à la plus ancienne, émises dans [depuis, avant[, d'un
    statut de paiement donné (story S4.4) si demandé."""
    base = _filtrer(select(Facture), depuis, avant)
    if statut_paiement is not None:
        base = base.where(condition_statut(statut_paiement))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    elements = list(
        db.scalars(
            base.options(
                selectinload(Facture.ordre),
                selectinload(Facture.paiements).selectinload(Paiement.createur),
            )
            .order_by(Facture.emise_le.desc(), Facture.id.desc())
            .offset((page - 1) * taille)
            .limit(taille)
        )
    )
    return PageFactures(elements=elements, total=total)
