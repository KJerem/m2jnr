"""Journée de démonstration : datée par rapport au jour de Paris, cohérente et rejouable."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Devis,
    Facture,
    HistoriqueStatut,
    OrdreTravail,
    RendezVous,
    StatutOT,
    Vehicule,
)
from app.services.donnees_demo import semer
from app.services.format import formater_euros
from tests.conftest import Horloge, connecter

# Lundi 16 novembre 2026, 15 h 00 à Paris.
MAINTENANT = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)


def _semer(db: Session, maintenant: datetime = MAINTENANT) -> list[str]:
    reglages = get_settings().model_copy(
        update={
            "demo_password_gerant": "demo-gerant-2026",
            "demo_password_mecanicien": "demo-meca-2026",
        }
    )
    return semer(db, reglages, maintenant)


def _ordre(db: Session, plaque: str, demande_debut: str) -> OrdreTravail:
    return db.scalars(
        select(OrdreTravail)
        .join(OrdreTravail.vehicule)
        .where(
            Vehicule.immatriculation == plaque,
            OrdreTravail.demande_client.startswith(demande_debut),
        )
    ).one()


def test_journee_rejouable_sans_doublon(db: Session) -> None:
    _semer(db)
    rapport = _semer(db)

    assert db.scalar(select(func.count()).select_from(OrdreTravail)) == 10
    assert db.scalar(select(func.count()).select_from(RendezVous)) == 9
    assert all(not ligne.startswith("Créé") for ligne in rapport)


def test_ordres_de_la_maquette(db: Session) -> None:
    _semer(db)

    peugeot = _ordre(db, "GH-482-KL", "Bruit au freinage")
    assert peugeot.statut == StatutOT.EN_COURS
    assert peugeot.mecanicien is not None and peugeot.mecanicien.nom == "Karim B."
    assert [(t.libelle, t.duree_prevue_minutes, t.terminee) for t in peugeot.taches] == [
        ("Diagnostic bruit de freinage", 30, True),
        ("Remplacement plaquettes et disques avant", 90, False),
        ("Vidange moteur et filtre à huile", 30, False),
    ]
    # 17 h 30 à Paris = 16 h 30 UTC ; rendez-vous de 8 h 00 sur le Pont 1.
    assert peugeot.restitution_prevue == datetime(2026, 11, 16, 16, 30, tzinfo=UTC)
    assert peugeot.rendez_vous is not None and peugeot.rendez_vous.pont.nom == "Pont 1"
    assert [h.nouveau for h in peugeot.historique] == [StatutOT.A_FAIRE, StatutOT.EN_COURS]

    dacia = _ordre(db, "GA-664-SN", "Révision")
    assert dacia.prioritaire is True
    assert (dacia.taches_terminees, dacia.taches_total) == (3, 4)

    bmw = _ordre(db, "FS-341-RD", "Vidange")
    assert bmw.statut == StatutOT.LIVRE
    assert bmw.cloture_le == datetime(2026, 11, 16, 9, 45, tzinfo=UTC)
    assert [h.nouveau for h in bmw.historique] == list(StatutOT)

    a_planifier = db.scalars(
        select(OrdreTravail).where(
            OrdreTravail.rendez_vous_id.is_(None), OrdreTravail.statut != StatutOT.LIVRE
        )
    ).all()
    assert sorted(o.vehicule.immatriculation for o in a_planifier) == ["CZ-918-LE", "DL-552-VK"]
    assert all(o.mecanicien is None for o in a_planifier)


def test_numeros_chronologiques_par_annee_de_paris(db: Session) -> None:
    _semer(db)

    numeros = [o.numero for o in db.scalars(select(OrdreTravail).order_by(OrdreTravail.ouvert_le))]

    assert numeros[0] == "OT-2025-001"  # révision d'il y a un an
    assert numeros[1:] == [f"OT-2026-{n:03d}" for n in range(1, 10)]


def test_aucun_fait_accompli_dans_le_futur(db: Session) -> None:
    # Seed lancé à 7 h 00 à Paris : rien n'est déjà terminé « à 9 h 15 ».
    matin = datetime(2026, 11, 16, 6, 0, tzinfo=UTC)
    _semer(db, matin)

    assert db.scalar(select(func.max(OrdreTravail.ouvert_le))) <= matin
    assert db.scalar(select(func.max(HistoriqueStatut.change_le))) <= matin


def test_planning_et_kanban_de_la_journee(
    db: Session, horloge: Horloge, client_gerant: TestClient, gerant: object
) -> None:
    _semer(db)
    horloge.maintenant = MAINTENANT
    connecter(client_gerant, "gerant@garage.test")

    planning = client_gerant.get("/planning").json()

    charges = {p["nom"]: (p["charge_minutes"], len(p["elements"])) for p in planning["ponts"]}
    assert charges == {"Pont 1": (390, 2), "Pont 2": (300, 2), "Pont 3": (210, 2)}
    assert len(planning["a_planifier"]) == 2
    dacia = next(e["ordre"] for e in planning["ponts"][1]["elements"] if e["ordre"]["prioritaire"])
    assert dacia["en_retard"] is True  # promise à 12 h 00, il est 15 h 00
    atelier = client_gerant.get("/ordres?atelier=true").json()["elements"]
    assert len(atelier) == 8  # les deux révisions de la Peugeot sont livrées d'autres jours


# --- Devis et factures de démonstration (story S4.3) ----------------------------------------


def test_devis_et_factures_de_demonstration(db: Session) -> None:
    _semer(db)

    peugeot = _ordre(db, "GH-482-KL", "Bruit au freinage")
    devis = db.scalars(select(Devis).where(Devis.ordre_travail_id == peugeot.id)).one()
    assert [(ligne.reference, str(ligne.quantite)) for ligne in devis.lignes] == [
        ("MO-DIAG", "0.50"),
        ("MO-FREIN-AV", "1.50"),
        ("MO-VIDANGE", "0.50"),
        ("PLQ-308-AV", "1.00"),
        ("DSQ-308-283", "1.00"),
        ("HUI-5W30-5L", "1.00"),
        ("FLT-H-12PT", "1.00"),
    ]
    assert (devis.total_ht_centimes, devis.total_tva_centimes, devis.total_ttc_centimes) == (
        37_900,
        7_580,
        45_480,
    )
    assert devis.facture is None
    toyota = _ordre(db, "HB-205-MZ", "Démarrage")
    assert toyota.statut == StatutOT.TERMINE
    devis_toyota = db.scalars(select(Devis).where(Devis.ordre_travail_id == toyota.id)).one()
    assert devis_toyota.facture is None

    factures = db.scalars(select(Facture).order_by(Facture.emise_le)).all()
    assert [f.numero for f in factures] == ["F-2025-001", "F-2026-001", "F-2026-002"]
    assert [f.ordre.vehicule.immatriculation for f in factures] == [
        "GH-482-KL",
        "GH-482-KL",
        "FS-341-RD",
    ]
    bmw = _ordre(db, "FS-341-RD", "Vidange")
    assert factures[-1].emise_le == bmw.cloture_le  # facturée à la livraison, aujourd'hui
    assert all(f.total_ttc_centimes == f.devis.total_ttc_centimes for f in factures)


def test_facturation_de_demonstration_rejouable(db: Session) -> None:
    _semer(db)
    rapport = _semer(db)

    assert db.scalar(select(func.count()).select_from(Devis)) == 6  # dont la Clio (sprint 4)
    assert db.scalar(select(func.count()).select_from(Facture)) == 3
    assert [ligne for ligne in rapport if "facture" in ligne] == [
        f"À jour : facture F-2025-001 OT-2025-001 ({formater_euros(17_112)} TTC)",
        f"À jour : facture F-2026-001 OT-2026-001 ({formater_euros(29_820)} TTC)",
        f"À jour : facture F-2026-002 OT-2026-002 ({formater_euros(15_492)} TTC)",
    ]
