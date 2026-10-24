"""Journée de démonstration des maquettes : ordres de travail, rendez-vous et historique.

Tout est daté par rapport au jour courant à Paris : le planning, le kanban et la vue tablette
montrent une journée d'atelier crédible le jour de la démo. Une heure prévue plus tard que
l'instant présent est ramenée à maintenant (pas de tâche « terminée » dans le futur).

Rejouable : un OT est reconnu par son véhicule et la demande du client, un rendez-vous par
son véhicule et son motif ; rien n'est créé deux fois. Les numéros d'OT passent par le
compteur habituel (année de Paris de l'ouverture), dans l'ordre chronologique.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import date_locale
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT, TacheOT
from app.models.pont import Pont
from app.models.rendez_vous import RendezVous
from app.models.utilisateur import Utilisateur
from app.models.vehicule import Vehicule
from app.services.numerotation import TYPE_ORDRE_TRAVAIL, prochain_numero
from app.services.transitions import LIBELLES_STATUT, ORDRE_DES_STATUTS

GERANT = "nadia@garage.test"
KARIM = "karim@garage.test"
SOPHIE = "sophie@garage.test"
LUCAS = "lucas@garage.test"


@dataclass(frozen=True)
class Moment:
    """Jour relatif (0 = aujourd'hui) et heure de Paris."""

    jour: int
    heure: int
    minute: int = 0


@dataclass(frozen=True)
class TacheDemo:
    libelle: str
    minutes: int
    faite: Moment | None = None


@dataclass(frozen=True)
class RendezVousDemo:
    pont: str
    debut: Moment
    duree: int
    motif: str


@dataclass(frozen=True)
class OrdreDemo:
    plaque: str
    ouvert: Moment
    demande: str
    statut: StatutOT
    # Heure de chaque étape franchie après l'ouverture (en_cours, termine, livre).
    etapes: tuple[Moment, ...] = ()
    mecanicien: str | None = None
    diagnostic: str | None = None
    prioritaire: bool = False
    kilometrage: int | None = None
    restitution: Moment | None = None
    taches: tuple[TacheDemo, ...] = ()
    rendez_vous: RendezVousDemo | None = None


ORDRES_DEMO: tuple[OrdreDemo, ...] = (
    # Historique de la Peugeot (fiche véhicule, onglet « Historique »).
    OrdreDemo(
        plaque="GH-482-KL",
        ouvert=Moment(-365, 8, 30),
        demande="Révision des 75 000 km.",
        diagnostic="Rien à signaler. Pneus avant à surveiller.",
        statut=StatutOT.LIVRE,
        etapes=(Moment(-365, 9, 0), Moment(-365, 11, 40), Moment(-365, 17, 0)),
        mecanicien=KARIM,
        kilometrage=75_120,
        taches=(
            TacheDemo("Vidange moteur et filtre à huile", 30, Moment(-365, 9, 45)),
            TacheDemo("Remplacement du filtre à air", 15, Moment(-365, 11, 30)),
        ),
    ),
    OrdreDemo(
        plaque="GH-482-KL",
        ouvert=Moment(-182, 9, 0),
        demande="Remplacement des pneus avant.",
        statut=StatutOT.LIVRE,
        etapes=(Moment(-182, 9, 15), Moment(-182, 10, 20), Moment(-182, 12, 0)),
        mecanicien=LUCAS,
        kilometrage=80_450,
        taches=(
            TacheDemo("Remplacement des pneus avant", 45, Moment(-182, 10, 0)),
            TacheDemo("Équilibrage des roues", 15, Moment(-182, 10, 15)),
        ),
    ),
    # Journée du jour.
    OrdreDemo(
        plaque="FS-341-RD",
        ouvert=Moment(0, 7, 35),
        demande="Vidange et contrôle avant un long trajet.",
        diagnostic="Niveaux faits, freins et pneus en bon état.",
        statut=StatutOT.LIVRE,
        etapes=(Moment(0, 7, 45), Moment(0, 9, 0), Moment(0, 10, 45)),
        mecanicien=LUCAS,
        kilometrage=52_600,
        restitution=Moment(0, 11, 0),
        taches=(
            TacheDemo("Vidange moteur et filtre à huile", 30, Moment(0, 8, 20)),
            TacheDemo("Contrôle des freins et des pneus", 30, Moment(0, 8, 55)),
        ),
        rendez_vous=RendezVousDemo(
            "Pont 3", Moment(0, 7, 30), 90, "Vidange et contrôle avant départ"
        ),
    ),
    OrdreDemo(
        plaque="GH-482-KL",
        ouvert=Moment(0, 8, 10),
        demande="Bruit au freinage côté avant gauche, surtout à basse vitesse.",
        diagnostic="Plaquettes avant usées, disques rayés : remplacement nécessaire.",
        statut=StatutOT.EN_COURS,
        etapes=(Moment(0, 8, 20),),
        mecanicien=KARIM,
        kilometrage=84_312,
        restitution=Moment(0, 17, 30),
        taches=(
            TacheDemo("Diagnostic bruit de freinage", 30, Moment(0, 9, 15)),
            TacheDemo("Remplacement plaquettes et disques avant", 90),
            TacheDemo("Vidange moteur et filtre à huile", 30),
        ),
        rendez_vous=RendezVousDemo(
            "Pont 1", Moment(0, 8, 0), 150, "Bruit au freinage avant gauche"
        ),
    ),
    OrdreDemo(
        plaque="GA-664-SN",
        ouvert=Moment(0, 8, 25),
        demande="Révision des 45 000 km et pneus avant. Cliente sur place.",
        diagnostic="Pneus avant usés à la limite légale.",
        statut=StatutOT.EN_COURS,
        etapes=(Moment(0, 8, 35),),
        mecanicien=SOPHIE,
        prioritaire=True,
        kilometrage=45_210,
        restitution=Moment(0, 12, 0),
        taches=(
            TacheDemo("Vidange et remplacement des filtres", 45, Moment(0, 9, 20)),
            TacheDemo("Remplacement des pneus avant", 45, Moment(0, 10, 10)),
            TacheDemo("Réglage de la géométrie", 30, Moment(0, 10, 50)),
            TacheDemo("Contrôle des freins", 30),
        ),
        rendez_vous=RendezVousDemo("Pont 2", Moment(0, 8, 30), 180, "Révision et pneus avant"),
    ),
    OrdreDemo(
        plaque="HB-205-MZ",
        ouvert=Moment(0, 9, 25),
        demande="Démarrage difficile le matin, révision annuelle.",
        diagnostic="Batterie en fin de vie (test de charge à 40 %).",
        statut=StatutOT.TERMINE,
        etapes=(Moment(0, 9, 35), Moment(0, 11, 20)),
        mecanicien=LUCAS,
        kilometrage=15_800,
        restitution=Moment(0, 16, 0),
        taches=(
            TacheDemo("Test de la batterie et du circuit de charge", 15, Moment(0, 9, 55)),
            TacheDemo("Remplacement de la batterie", 30, Moment(0, 10, 30)),
            TacheDemo("Révision annuelle", 45, Moment(0, 11, 15)),
        ),
        rendez_vous=RendezVousDemo(
            "Pont 3", Moment(0, 9, 30), 120, "Batterie et révision annuelle"
        ),
    ),
    OrdreDemo(
        plaque="EK-730-PA",
        ouvert=Moment(0, 10, 25),
        demande="Embrayage qui patine en montée, odeur de brûlé.",
        diagnostic="Kit d'embrayage usé, volant moteur à contrôler.",
        statut=StatutOT.EN_COURS,
        etapes=(Moment(0, 10, 40),),
        mecanicien=KARIM,
        kilometrage=112_450,
        restitution=Moment(1, 12, 0),
        taches=(
            TacheDemo("Diagnostic de l'embrayage", 30, Moment(0, 11, 10)),
            TacheDemo("Dépose de la boîte de vitesses", 90, Moment(0, 12, 45)),
            TacheDemo("Remplacement du kit d'embrayage", 90),
            TacheDemo("Repose et essai routier", 60),
        ),
        rendez_vous=RendezVousDemo("Pont 1", Moment(0, 10, 30), 240, "Remplacement de l'embrayage"),
    ),
    OrdreDemo(
        plaque="FD-119-RT",
        ouvert=Moment(0, 11, 50),
        demande="Voyant moteur allumé depuis hier, perte de puissance.",
        statut=StatutOT.A_FAIRE,
        mecanicien=SOPHIE,
        kilometrage=38_900,
        restitution=Moment(0, 18, 0),
        taches=(
            TacheDemo("Lecture des codes défaut", 30),
            TacheDemo("Remplacement de la bobine d'allumage", 60),
        ),
        rendez_vous=RendezVousDemo("Pont 2", Moment(0, 14, 0), 120, "Voyant moteur allumé"),
    ),
    # À planifier : ni rendez-vous ni mécanicien.
    OrdreDemo(
        plaque="CZ-918-LE",
        ouvert=Moment(0, 9, 5),
        demande="Bruit de roulement à l'arrière droit au-delà de 80 km/h.",
        statut=StatutOT.A_FAIRE,
        kilometrage=97_340,
        taches=(TacheDemo("Diagnostic bruit de roulement", 30),),
    ),
    OrdreDemo(
        plaque="DL-552-VK",
        ouvert=Moment(0, 11, 15),
        demande="Climatisation qui ne refroidit plus.",
        statut=StatutOT.A_FAIRE,
        kilometrage=76_120,
        taches=(
            TacheDemo("Contrôle d'étanchéité du circuit", 30),
            TacheDemo("Recharge de climatisation", 45),
        ),
    ),
)

# Rendez-vous des jours suivants, sans ordre de travail ouvert.
RENDEZ_VOUS_A_VENIR: tuple[tuple[str, RendezVousDemo], ...] = (
    (
        "GH-482-KL",
        RendezVousDemo("Pont 2", Moment(1, 8, 30), 30, "Contrôle des freins après remplacement"),
    ),
    ("FS-341-RD", RendezVousDemo("Pont 3", Moment(2, 9, 0), 60, "Montage des pneus hiver")),
    ("GA-664-SN", RendezVousDemo("Pont 1", Moment(3, 14, 0), 45, "Contrôle de la géométrie")),
)


class JourneeDemo:
    """Contexte de la journée : jour de Paris, instant présent, comptes et véhicules."""

    def __init__(self, db: Session, maintenant: datetime, fuseau: str) -> None:
        self.db = db
        self.maintenant = maintenant
        self.fuseau = ZoneInfo(fuseau)
        self.jour: date = date_locale(maintenant, fuseau)

    def instant(self, moment: Moment) -> datetime:
        local = datetime.combine(
            self.jour + timedelta(days=moment.jour), time(moment.heure, moment.minute), self.fuseau
        )
        return local.astimezone(self.maintenant.tzinfo)

    def passe(self, moment: Moment) -> datetime:
        """Heure d'un fait accompli : jamais après l'instant présent."""
        return min(self.instant(moment), self.maintenant)

    def utilisateur(self, email: str) -> Utilisateur:
        return self.db.scalars(select(Utilisateur).where(Utilisateur.email == email)).one()

    def vehicule(self, plaque: str) -> Vehicule:
        return self.db.scalars(select(Vehicule).where(Vehicule.immatriculation == plaque)).one()

    def rendez_vous(self, vehicule: Vehicule, demo: RendezVousDemo) -> tuple[RendezVous, bool]:
        existant = self.db.scalars(
            select(RendezVous).where(
                RendezVous.vehicule_id == vehicule.id, RendezVous.motif == demo.motif
            )
        ).first()
        if existant is not None:
            return existant, False
        pont = self.db.scalars(select(Pont).where(Pont.nom == demo.pont)).one()
        rdv = RendezVous(
            vehicule=vehicule,
            pont=pont,
            debut=self.instant(demo.debut),
            duree_minutes=demo.duree,
            motif=demo.motif,
            createur=self.utilisateur(GERANT),
        )
        self.db.add(rdv)
        self.db.flush()
        return rdv, True

    def ordre(self, demo: OrdreDemo) -> tuple[OrdreTravail, bool]:
        vehicule = self.vehicule(demo.plaque)
        existant = self.db.scalars(
            select(OrdreTravail).where(
                OrdreTravail.vehicule_id == vehicule.id,
                OrdreTravail.demande_client == demo.demande,
            )
        ).first()
        if existant is not None:
            return existant, False

        gerant = self.utilisateur(GERANT)
        mecanicien = self.utilisateur(demo.mecanicien) if demo.mecanicien else None
        ouvert_le = self.passe(demo.ouvert)
        rdv = self.rendez_vous(vehicule, demo.rendez_vous)[0] if demo.rendez_vous else None
        ordre = OrdreTravail(
            numero=prochain_numero(
                self.db, TYPE_ORDRE_TRAVAIL, date_locale(ouvert_le, self.fuseau.key).year
            ),
            vehicule=vehicule,
            mecanicien=mecanicien,
            demande_client=demo.demande,
            diagnostic=demo.diagnostic,
            statut=demo.statut,
            prioritaire=demo.prioritaire,
            kilometrage_entree=demo.kilometrage,
            restitution_prevue=self.instant(demo.restitution) if demo.restitution else None,
            ouvert_le=ouvert_le,
            createur=gerant,
            rendez_vous=rdv,
        )
        ordre.taches = [
            TacheOT(
                libelle=t.libelle,
                duree_prevue_minutes=t.minutes,
                position=i,
                terminee=t.faite is not None,
                terminee_le=max(self.passe(t.faite), ouvert_le) if t.faite else None,
                terminee_par_utilisateur=(mecanicien or gerant) if t.faite else None,
            )
            for i, t in enumerate(demo.taches)
        ]
        historique = [
            HistoriqueStatut(
                ancien=None, nouveau=StatutOT.A_FAIRE, change_le=ouvert_le, utilisateur=gerant
            )
        ]
        precedent = ouvert_le
        for rang, moment in enumerate(demo.etapes, start=1):
            ancien, nouveau = ORDRE_DES_STATUTS[rang - 1], ORDRE_DES_STATUTS[rang]
            precedent = max(self.passe(moment), precedent)
            auteur = gerant if nouveau == StatutOT.LIVRE or mecanicien is None else mecanicien
            historique.append(
                HistoriqueStatut(
                    ancien=ancien, nouveau=nouveau, change_le=precedent, utilisateur=auteur
                )
            )
            if nouveau == StatutOT.LIVRE:
                ordre.cloture_le = precedent
        ordre.historique = historique
        self.db.add(ordre)
        self.db.flush()
        return ordre, True


def semer_journee(db: Session, maintenant: datetime, fuseau: str) -> list[str]:
    """Crée la journée de démonstration (une seule fois) ; renvoie un compte rendu."""
    journee = JourneeDemo(db, maintenant, fuseau)
    rapport: list[str] = []
    for demo in sorted(ORDRES_DEMO, key=lambda d: (d.ouvert.jour, d.ouvert.heure, d.ouvert.minute)):
        ordre, cree = journee.ordre(demo)
        rapport.append(
            f"{'Créé' if cree else 'À jour'} : {ordre.numero} {ordre.vehicule.marque}"
            f" {ordre.vehicule.modele} ({LIBELLES_STATUT[ordre.statut]})"
        )
    for plaque, demo_rdv in RENDEZ_VOUS_A_VENIR:
        rdv, cree = journee.rendez_vous(journee.vehicule(plaque), demo_rdv)
        rapport.append(
            f"{'Créé' if cree else 'À jour'} : rendez-vous {rdv.motif} ({demo_rdv.pont})"
        )
    return rapport
