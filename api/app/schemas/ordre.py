"""Schémas de l'ordre de travail (OT) et de ses tâches."""

from datetime import date, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.models.ordre_travail import OrdreTravail, StatutOT, TacheOT
from app.schemas.commun import Identifiant, InstantFacultatif, vide_vers_none
from app.schemas.vehicule import Kilometrage
from app.services.delais import est_en_retard

MESSAGE_VEHICULE_OBLIGATOIRE = "Un ordre de travail doit être rattaché à un véhicule."

# Une tâche dure au plus 10 heures (même borne qu'un rendez-vous sur un pont).
DUREE_TACHE_MAX = 600
TACHES_MAX = 50


def _vehicule_obligatoire(valeur: int | None) -> int:
    if valeur is None:
        raise ValueError(MESSAGE_VEHICULE_OBLIGATOIRE)
    return valeur


Libelle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
DemandeClient = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
Diagnostic = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] | None,
    BeforeValidator(vide_vers_none),
]
DureeTache = Annotated[int, Field(strict=True, ge=1, le=DUREE_TACHE_MAX)]


class TacheEntree(BaseModel):
    libelle: Libelle
    duree_prevue_minutes: DureeTache


class TacheModification(TacheEntree):
    """Tâche envoyée à la modification : avec `id` pour une tâche existante, sans pour une
    nouvelle. Les tâches absentes de la liste sont supprimées ; l'ordre de la liste fait foi."""

    id: Identifiant | None = None


class OrdreEntree(BaseModel):
    """Ouverture d'un ordre de travail (gérant)."""

    # Facultatif pour le schéma afin de renvoyer le message métier, et non « Champ obligatoire. ».
    vehicule_id: Annotated[Identifiant | None, AfterValidator(_vehicule_obligatoire)] = Field(
        default=None, validate_default=True
    )
    demande_client: DemandeClient
    diagnostic: Diagnostic = None
    prioritaire: bool = False
    kilometrage_entree: Kilometrage | None = None
    restitution_prevue: InstantFacultatif = None
    mecanicien_id: Identifiant | None = None
    taches: list[TacheEntree] = Field(default_factory=list, max_length=TACHES_MAX)


class OrdreModification(BaseModel):
    """Modification d'un ordre de travail non livré (gérant).

    `taches` absent (ou null) : les tâches restent telles quelles ; sinon la liste remplace
    les tâches de l'OT (ajout, modification, suppression, ordre)."""

    demande_client: DemandeClient
    diagnostic: Diagnostic = None
    prioritaire: bool = False
    restitution_prevue: InstantFacultatif = None
    mecanicien_id: Identifiant | None = None
    taches: list[TacheModification] | None = Field(default=None, max_length=TACHES_MAX)


# --- Sorties -------------------------------------------------------------------------------


class UtilisateurResume(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str


class VehiculeOrdre(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    immatriculation: str
    marque: str
    modele: str
    kilometrage: int


class VehiculeOrdreDetail(VehiculeOrdre):
    vin: str | None
    date_mise_en_circulation: date | None


class ContactClient(BaseModel):
    """Coordonnées du client : envoyées au gérant seulement (RGPD, données minimales)."""

    model_config = ConfigDict(from_attributes=True)

    telephone: str
    email: str | None


class ClientOrdre(BaseModel):
    id: int
    nom: str
    prenom: str | None
    # null pour le mécanicien : il ne reçoit ni le téléphone ni l'e-mail du client.
    contact: ContactClient | None = None


class TacheSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    libelle: str
    duree_prevue_minutes: int
    position: int
    terminee: bool
    terminee_le: datetime | None
    terminee_par: UtilisateurResume | None = Field(validation_alias="terminee_par_utilisateur")


class PontSortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str


class RendezVousOrdre(BaseModel):
    """Rendez-vous d'origine d'un OT : le pont où il est traité et son créneau."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    debut: datetime
    fin: datetime
    duree_minutes: int
    pont: PontSortie


class HistoriqueSortie(BaseModel):
    """Ligne du suivi : `ancien` vaut null pour l'ouverture de l'OT."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ancien: StatutOT | None
    nouveau: StatutOT
    change_le: datetime
    utilisateur: UtilisateurResume


class ChangementStatutEntree(BaseModel):
    nouveau: StatutOT


class OrdreResume(BaseModel):
    """Carte d'un OT (listes, kanban, planning)."""

    id: int
    numero: str
    statut: StatutOT
    prioritaire: bool
    vehicule: VehiculeOrdre
    client: ClientOrdre
    mecanicien: UtilisateurResume | None
    restitution_prevue: datetime | None
    ouvert_le: datetime
    cloture_le: datetime | None
    taches_terminees: int
    taches_total: int
    duree_prevue_minutes: int
    en_retard: bool
    rendez_vous: RendezVousOrdre | None


class OrdreDetail(OrdreResume):
    vehicule: VehiculeOrdreDetail
    demande_client: str
    diagnostic: str | None
    kilometrage_entree: int | None
    cree_par: UtilisateurResume
    taches: list[TacheSortie]
    # Suivi chronologique des statuts (le plus ancien d'abord).
    historique: list[HistoriqueSortie]


def _client(ordre: OrdreTravail, voir_contact: bool) -> ClientOrdre:
    client = ordre.vehicule.client
    return ClientOrdre(
        id=client.id,
        nom=client.nom,
        prenom=client.prenom,
        contact=ContactClient.model_validate(client) if voir_contact else None,
    )


def _duree_prevue(taches: list[TacheOT]) -> int:
    return sum(t.duree_prevue_minutes for t in taches)


def _champs_resume(
    ordre: OrdreTravail, maintenant: datetime, voir_contact: bool
) -> dict[str, object]:
    return {
        "id": ordre.id,
        "numero": ordre.numero,
        "statut": ordre.statut,
        "prioritaire": ordre.prioritaire,
        "client": _client(ordre, voir_contact),
        "mecanicien": (
            UtilisateurResume.model_validate(ordre.mecanicien) if ordre.mecanicien else None
        ),
        "restitution_prevue": ordre.restitution_prevue,
        "ouvert_le": ordre.ouvert_le,
        "cloture_le": ordre.cloture_le,
        "taches_terminees": ordre.taches_terminees,
        "taches_total": ordre.taches_total,
        "duree_prevue_minutes": _duree_prevue(ordre.taches),
        "en_retard": est_en_retard(ordre.statut, ordre.restitution_prevue, maintenant),
        "rendez_vous": (
            RendezVousOrdre.model_validate(ordre.rendez_vous) if ordre.rendez_vous else None
        ),
    }


def resume_ordre(ordre: OrdreTravail, maintenant: datetime, *, voir_contact: bool) -> OrdreResume:
    return OrdreResume.model_validate(
        {
            **_champs_resume(ordre, maintenant, voir_contact),
            "vehicule": VehiculeOrdre.model_validate(ordre.vehicule),
        }
    )


def detail_ordre(ordre: OrdreTravail, maintenant: datetime, *, voir_contact: bool) -> OrdreDetail:
    return OrdreDetail.model_validate(
        {
            **_champs_resume(ordre, maintenant, voir_contact),
            "vehicule": VehiculeOrdreDetail.model_validate(ordre.vehicule),
            "demande_client": ordre.demande_client,
            "diagnostic": ordre.diagnostic,
            "kilometrage_entree": ordre.kilometrage_entree,
            "cree_par": UtilisateurResume.model_validate(ordre.createur),
            "taches": [TacheSortie.model_validate(t) for t in ordre.taches],
            "historique": [HistoriqueSortie.model_validate(h) for h in ordre.historique],
        }
    )


class MecanicienSortie(UtilisateurResume):
    """Mécanicien actif, proposé à l'affectation d'un OT."""


class TacheHistorique(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    libelle: str
    terminee: bool


class InterventionHistorique(BaseModel):
    """Intervention passée ou en cours d'un véhicule (story S1.4).

    Lisible par le mécanicien : aucune donnée du client. Les liens vers le devis et la
    facture arriveront au sprint 3."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    statut: StatutOT
    demande_client: str
    diagnostic: str | None
    kilometrage_entree: int | None
    ouvert_le: datetime
    cloture_le: datetime | None
    mecanicien: UtilisateurResume | None
    taches: list[TacheHistorique]
