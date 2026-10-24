"""Devis d'un ordre de travail : création, remplacement des lignes, consultation, liste.

Règles (story S4.1) :
- réservé au gérant (garde du routeur) ;
- au moins une ligne, au plus 100 ; quantité > 0 à deux décimales, prix unitaire ≥ 0 ;
- les totaux (lignes, HT, TVA, TTC) sont toujours recalculés par app/services/calcul_devis.py
  et enregistrés : le front affiche ceux renvoyés par l'API ;
- un OT porte un devis courant (le plus récent) : en créer un second est refusé (409) tant
  que le statut du devis (story S4.2) ne permet pas de remplacer un devis refusé ;
- deux enregistrements simultanés s'appliquent l'un après l'autre : la création verrouille
  l'OT, la modification verrouille le devis (SELECT … FOR UPDATE).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.db import id_possible
from app.errors import conflict, not_found
from app.models.devis import TAUX_TVA_NORMAL_BP, Devis, LigneDevis
from app.models.ordre_travail import OrdreTravail
from app.models.utilisateur import Utilisateur
from app.models.vehicule import Vehicule
from app.schemas.devis import LigneEntree
from app.services import calcul_devis

MESSAGE_DEVIS_INTROUVABLE = "Devis introuvable."
MESSAGE_AUCUN_DEVIS = "Aucun devis pour cet ordre de travail."
MESSAGE_DEVIS_EXISTANT = "Cet ordre de travail a déjà un devis : modifiez-le."

CHARGEMENT_DEVIS: tuple[ExecutableOption, ...] = (
    selectinload(Devis.lignes),
    selectinload(Devis.ordre).selectinload(OrdreTravail.vehicule).selectinload(Vehicule.client),
)


def devis_courant(db: Session, ordre_id: int) -> Devis | None:
    """Devis le plus récent de l'OT, ou None."""
    return db.scalars(
        select(Devis)
        .where(Devis.ordre_travail_id == ordre_id)
        .options(*CHARGEMENT_DEVIS)
        .order_by(Devis.id.desc())
        .limit(1)
    ).first()


def obtenir_devis(db: Session, devis_id: int, *, verrouiller: bool = False) -> Devis:
    """Devis et ses lignes ; `verrouiller` pose SELECT … FOR UPDATE et relit la ligne validée."""
    devis = None
    if id_possible(devis_id):
        requete = select(Devis).where(Devis.id == devis_id)
        if verrouiller:
            requete = requete.with_for_update().execution_options(populate_existing=True)
        devis = db.scalars(requete.options(*CHARGEMENT_DEVIS)).one_or_none()
    if devis is None:
        raise not_found(MESSAGE_DEVIS_INTROUVABLE)
    return devis


def _appliquer_lignes(devis: Devis, lignes: Sequence[LigneEntree]) -> None:
    """Remplace les lignes et enregistre les totaux recalculés."""
    devis.lignes = [
        LigneDevis(
            type=ligne.type,
            reference=ligne.reference,
            designation=ligne.designation,
            quantite=ligne.quantite,
            prix_unitaire_ht_centimes=ligne.prix_unitaire_ht_centimes,
            total_ht_centimes=calcul_devis.total_ligne(
                ligne.quantite, ligne.prix_unitaire_ht_centimes
            ),
            position=i,
        )
        for i, ligne in enumerate(lignes)
    ]
    totaux = calcul_devis.totaux(lignes, devis.taux_tva_bp)
    devis.total_ht_centimes = totaux.total_ht_centimes
    devis.total_tva_centimes = totaux.total_tva_centimes
    devis.total_ttc_centimes = totaux.total_ttc_centimes


def creer_devis(
    db: Session,
    ordre: OrdreTravail,
    lignes: Sequence[LigneEntree],
    auteur: Utilisateur,
    maintenant: datetime,
) -> Devis:
    """Chiffre l'OT (verrouillé par l'appelant : deux créations simultanées ne font pas deux
    devis)."""
    existant = devis_courant(db, ordre.id)
    if existant is not None:
        raise conflict("devis_existant", MESSAGE_DEVIS_EXISTANT, devis_id=existant.id)
    devis = Devis(
        ordre=ordre,
        taux_tva_bp=TAUX_TVA_NORMAL_BP,
        createur=auteur,
        cree_le=maintenant,
        modifie_le=maintenant,
    )
    _appliquer_lignes(devis, lignes)
    db.add(devis)
    db.flush()
    return devis


def modifier_devis(
    db: Session, devis: Devis, lignes: Sequence[LigneEntree], maintenant: datetime
) -> Devis:
    """Remplace les lignes du devis (verrouillé par l'appelant) et recalcule les totaux."""
    _appliquer_lignes(devis, lignes)
    devis.modifie_le = maintenant
    db.flush()
    return devis


@dataclass(frozen=True)
class PageDevis:
    elements: list[Devis]
    total: int


def lister_devis(db: Session, page: int, taille: int) -> PageDevis:
    """Devis du plus récent au plus ancien."""
    total = db.scalar(select(func.count()).select_from(Devis)) or 0
    elements = list(
        db.scalars(
            select(Devis)
            .options(*CHARGEMENT_DEVIS)
            .order_by(Devis.cree_le.desc(), Devis.id.desc())
            .offset((page - 1) * taille)
            .limit(taille)
        )
    )
    return PageDevis(elements=elements, total=total)
