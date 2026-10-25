"""Recette du sprint 5 — comptes du jeu de démonstration : prénoms des comptes de démo (affichage
inchangé), une inscription en attente de validation et un ancien mécanicien désactivé, remis
dans cet état à chaque seed ; les comptes de démo restent actifs et débloqués."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Role, StatutCompte, Utilisateur
from app.services.auth import trouver_par_email
from app.services.donnees_demo import semer

MAINTENANT = datetime(2027, 1, 11, 9, 0, tzinfo=UTC)
MDP_GERANT = "demo-gerant-2027"
MDP_MECANICIEN = "demo-meca-2027"


def _semer(db: Session, maintenant: datetime = MAINTENANT) -> list[str]:
    reglages = get_settings().model_copy(
        update={"demo_password_gerant": MDP_GERANT, "demo_password_mecanicien": MDP_MECANICIEN}
    )
    return semer(db, reglages, maintenant)


def _compte(db: Session, email: str) -> Utilisateur:
    utilisateur = trouver_par_email(db, email)
    assert utilisateur is not None, email
    return utilisateur


def test_prenoms_des_comptes_de_demo_et_affichage_inchange(db: Session) -> None:
    _semer(db)
    assert [
        (u.prenom, u.nom, u.nom_affiche, u.statut)
        for u in (_compte(db, f"{n}@garage.test") for n in ("nadia", "karim", "sophie", "lucas"))
    ] == [
        ("Nadia", "Benali", "Nadia Benali", StatutCompte.ACTIF),
        ("Karim", "B.", "Karim B.", StatutCompte.ACTIF),
        ("Sophie", "M.", "Sophie M.", StatutCompte.ACTIF),
        ("Lucas", "R.", "Lucas R.", StatutCompte.ACTIF),
    ]


def test_inscription_en_attente_et_ancien_employe_desactive(db: Session) -> None:
    rapport = _semer(db)
    nadia = _compte(db, "nadia@garage.test")

    ines = _compte(db, "ines.morel@exemple.test")
    assert (ines.prenom, ines.nom, ines.role, ines.statut) == (
        "Inès",
        "Morel",
        Role.GERANT,
        StatutCompte.EN_ATTENTE,
    )
    assert ines.valide_le is None and ines.desactive_le is None
    paul = _compte(db, "paul.girard@garage.test")
    assert (paul.prenom, paul.nom, paul.role, paul.statut) == (
        "Paul",
        "Girard",
        Role.MECANICIEN,
        StatutCompte.DESACTIVE,
    )
    assert paul.desactive_le == MAINTENANT - timedelta(days=30)
    assert paul.desactive_par == nadia.id
    assert "Créé : Inès Morel (ines.morel@exemple.test, en attente de validation)" in rapport
    assert "Créé : Paul Girard (paul.girard@garage.test, désactivé)" in rapport


def test_seed_rejouable_remet_les_comptes_dans_leur_etat(db: Session) -> None:
    _semer(db)
    nadia = _compte(db, "nadia@garage.test")
    karim = _compte(db, "karim@garage.test")
    ines = _compte(db, "ines.morel@exemple.test")
    paul = _compte(db, "paul.girard@garage.test")
    desactive_le = paul.desactive_le
    # Pendant une démonstration : Inès validée, Paul réactivé, Karim bloqué puis désactivé.
    ines.statut, ines.valide_le, ines.valide_par = StatutCompte.ACTIF, MAINTENANT, nadia.id
    paul.statut, paul.desactive_le, paul.desactive_par = StatutCompte.ACTIF, None, None
    karim.tentatives_echouees, karim.bloque_jusqu_a = 5, MAINTENANT + timedelta(minutes=15)
    karim.statut, karim.desactive_le = StatutCompte.DESACTIVE, MAINTENANT
    db.flush()

    rapport = _semer(db, MAINTENANT + timedelta(days=2))

    assert all(not ligne.startswith("Créé") for ligne in rapport if "@" in ligne)
    assert (ines.statut, ines.valide_le, ines.valide_par) == (StatutCompte.EN_ATTENTE, None, None)
    assert paul.statut == StatutCompte.DESACTIVE
    assert paul.desactive_le == MAINTENANT + timedelta(days=2) - timedelta(days=30)
    assert (karim.statut, karim.tentatives_echouees, karim.bloque_jusqu_a) == (
        StatutCompte.ACTIF,
        0,
        None,
    )
    assert karim.desactive_le is None
    # Un troisième seed ne change plus la date de désactivation de Paul.
    _semer(db, MAINTENANT + timedelta(days=5))
    assert paul.desactive_le == MAINTENANT + timedelta(days=2) - timedelta(days=30)
    assert desactive_le is not None


def test_comptes_hors_service_ne_se_connectent_pas(
    db: Session, nouveau_client: Callable[[], TestClient]
) -> None:
    _semer(db)
    c = nouveau_client()

    ines = c.post(
        "/auth/login", json={"email": "ines.morel@exemple.test", "mot_de_passe": MDP_GERANT}
    )
    assert ines.status_code == 401
    assert ines.json()["message"] == "Identifiants invalides."
    paul = c.post(
        "/auth/login", json={"email": "paul.girard@garage.test", "mot_de_passe": MDP_MECANICIEN}
    )
    assert paul.status_code == 401
    assert paul.json()["message"] == "Identifiants invalides."
    nadia = c.post("/auth/login", json={"email": "nadia@garage.test", "mot_de_passe": MDP_GERANT})
    assert nadia.status_code == 200


def test_compte_a_valider_au_tableau_de_bord_apres_le_seed(
    db: Session, nouveau_client: Callable[[], TestClient]
) -> None:
    _semer(db)
    c = nouveau_client()
    assert (
        c.post(
            "/auth/login", json={"email": "nadia@garage.test", "mot_de_passe": MDP_GERANT}
        ).status_code
        == 200
    )
    ines = _compte(db, "ines.morel@exemple.test")

    a_traiter = c.get("/tableau-de-bord").json()["a_traiter"]

    assert {
        "type": "compte_a_valider",
        "titre": "Compte à valider",
        "detail": "Inès Morel · ines.morel@exemple.test",
        "ordre_id": None,
        "numero": None,
        "utilisateur_id": ines.id,
    } in a_traiter
    assert "paul.girard" not in str(a_traiter)
