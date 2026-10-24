"""Story S3.2 — statut de l'OT : une étape à la fois, historique horodaté, tâches, kanban."""

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Client, HistoriqueStatut, OrdreTravail, StatutOT, Utilisateur, Vehicule
from app.services.transitions import statut_suivant, verifier_transition
from tests.conftest import Horloge

A_FAIRE, EN_COURS, TERMINE, LIVRE = (
    StatutOT.A_FAIRE,
    StatutOT.EN_COURS,
    StatutOT.TERMINE,
    StatutOT.LIVRE,
)


@pytest.fixture(autouse=True)
def _horloge_d_abord(horloge: Horloge) -> Horloge:
    """L'horloge est posée avant toute connexion : les sessions sont datées du 2 novembre."""
    return horloge


@pytest.fixture
def vehicule(db: Session) -> Vehicule:
    client = Client(nom="Laurent", prenom="Claire", telephone="0612483075")
    db.add(client)
    db.flush()
    vehicule = Vehicule(
        client_id=client.id,
        immatriculation="GH-482-KL",
        marque="Peugeot",
        modele="308 SW",
        kilometrage=84312,
    )
    db.add(vehicule)
    db.flush()
    return vehicule


@pytest.fixture
def ordre(horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule) -> dict[str, Any]:
    reponse = client_gerant.post(
        "/ordres",
        json={
            "vehicule_id": vehicule.id,
            "demande_client": "Bruit au freinage.",
            "taches": [
                {"libelle": "Diagnostic bruit de freinage", "duree_prevue_minutes": 30},
                {"libelle": "Remplacement plaquettes", "duree_prevue_minutes": 90},
            ],
        },
    )
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


def _statut(c: TestClient, ordre_id: int, nouveau: str) -> Any:
    return c.post(f"/ordres/{ordre_id}/statut", json={"nouveau": nouveau})


def _terminer(c: TestClient, ordre: dict[str, Any], indice: int) -> Any:
    tache = ordre["taches"][indice]
    return c.post(f"/ordres/{ordre['id']}/taches/{tache['id']}/terminer")


def _tout_terminer(c: TestClient, ordre: dict[str, Any]) -> None:
    for indice in range(len(ordre["taches"])):
        assert _terminer(c, ordre, indice).status_code == 200


# --- Règle pure ----------------------------------------------------------------------------


def test_statut_suivant() -> None:
    assert [statut_suivant(s) for s in (A_FAIRE, EN_COURS, TERMINE, LIVRE)] == [
        EN_COURS,
        TERMINE,
        LIVRE,
        None,
    ]


@pytest.mark.parametrize(
    ("ancien", "nouveau"), [(A_FAIRE, EN_COURS), (EN_COURS, TERMINE), (TERMINE, LIVRE)]
)
def test_transitions_autorisees(ancien: StatutOT, nouveau: StatutOT) -> None:
    verifier_transition(ancien, nouveau)


@pytest.mark.parametrize(
    ("ancien", "nouveau", "message"),
    [
        (A_FAIRE, LIVRE, "Passage de « En attente » à « Livré » impossible : une étape à la fois."),
        (
            A_FAIRE,
            TERMINE,
            "Passage de « En attente » à « Prêt » impossible : une étape à la fois.",
        ),
        (EN_COURS, LIVRE, "Passage de « En cours » à « Livré » impossible : une étape à la fois."),
        (
            TERMINE,
            EN_COURS,
            "Passage de « Prêt » à « En cours » impossible : pas de retour en arrière.",
        ),
        (
            LIVRE,
            A_FAIRE,
            "Passage de « Livré » à « En attente » impossible : pas de retour en arrière.",
        ),
        (EN_COURS, EN_COURS, "L'ordre de travail est déjà « En cours »."),
        (LIVRE, LIVRE, "L'ordre de travail est déjà « Livré »."),
    ],
)
def test_transitions_interdites(ancien: StatutOT, nouveau: StatutOT, message: str) -> None:
    with pytest.raises(AppError) as erreur:
        verifier_transition(ancien, nouveau)
    assert erreur.value.status_code == 409
    assert erreur.value.code == "transition_interdite"
    assert erreur.value.message == message


# --- Parcours par l'API --------------------------------------------------------------------


def test_creation_tracee_dans_l_historique(ordre: dict[str, Any], gerant: Utilisateur) -> None:
    assert ordre["historique"] == [
        {
            "id": ordre["historique"][0]["id"],
            "ancien": None,
            "nouveau": "a_faire",
            "change_le": "2026-11-02T13:47:00Z",
            "utilisateur": {"id": gerant.id, "nom": "Nadia Benali"},
        }
    ]


def test_chaine_complete_avec_historique_horodate_et_auteurs(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    ordre: dict[str, Any],
    gerant: Utilisateur,
    mecanicien: Utilisateur,
) -> None:
    horloge.avancer(minutes=13)  # 15 h 00 à Paris
    demarre = _statut(client_mecanicien, ordre["id"], "en_cours")
    assert demarre.status_code == 200, demarre.text
    _tout_terminer(client_mecanicien, ordre)
    horloge.avancer(hours=2)
    pret = _statut(client_mecanicien, ordre["id"], "termine")
    assert pret.status_code == 200, pret.text
    assert pret.json()["cloture_le"] is None
    horloge.avancer(minutes=30)
    livre = _statut(client_gerant, ordre["id"], "livre")

    assert livre.status_code == 200, livre.text
    corps = livre.json()
    assert corps["statut"] == "livre"
    assert corps["cloture_le"] == "2026-11-02T16:30:00Z"
    assert [
        (h["ancien"], h["nouveau"], h["change_le"], h["utilisateur"]["id"])
        for h in corps["historique"]
    ] == [
        (None, "a_faire", "2026-11-02T13:47:00Z", gerant.id),
        ("a_faire", "en_cours", "2026-11-02T14:00:00Z", mecanicien.id),
        ("en_cours", "termine", "2026-11-02T16:00:00Z", mecanicien.id),
        ("termine", "livre", "2026-11-02T16:30:00Z", gerant.id),
    ]
    # Le suivi est aussi rendu par la consultation.
    detail = client_mecanicien.get(f"/ordres/{ordre['id']}").json()
    assert len(detail["historique"]) == 4


@pytest.mark.parametrize(
    ("chemin", "nouveau", "message"),
    [
        ([], "livre", "Passage de « En attente » à « Livré » impossible : une étape à la fois."),
        ([], "termine", "Passage de « En attente » à « Prêt » impossible : une étape à la fois."),
        ([], "a_faire", "L'ordre de travail est déjà « En attente »."),
        (
            ["en_cours"],
            "a_faire",
            "Passage de « En cours » à « En attente » impossible : pas de retour en arrière.",
        ),
        (["en_cours"], "en_cours", "L'ordre de travail est déjà « En cours »."),
    ],
)
def test_saut_retour_ou_meme_statut_refuses_par_l_api(
    client_mecanicien: TestClient,
    ordre: dict[str, Any],
    db: Session,
    chemin: list[str],
    nouveau: str,
    message: str,
) -> None:
    for etape in chemin:
        assert _statut(client_mecanicien, ordre["id"], etape).status_code == 200
    avant = db.scalar(
        select(HistoriqueStatut.id)
        .where(HistoriqueStatut.ordre_travail_id == ordre["id"])
        .order_by(HistoriqueStatut.id.desc())
    )

    reponse = _statut(client_mecanicien, ordre["id"], nouveau)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "transition_interdite"
    assert reponse.json()["message"] == message
    apres = db.scalar(
        select(HistoriqueStatut.id)
        .where(HistoriqueStatut.ordre_travail_id == ordre["id"])
        .order_by(HistoriqueStatut.id.desc())
    )
    assert apres == avant


def test_pret_refuse_tant_qu_une_tache_est_ouverte(
    client_mecanicien: TestClient, ordre: dict[str, Any]
) -> None:
    _statut(client_mecanicien, ordre["id"], "en_cours")
    _terminer(client_mecanicien, ordre, 0)

    reponse = _statut(client_mecanicien, ordre["id"], "termine")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "taches_non_terminees"
    assert reponse.json()["message"] == "Toutes les tâches doivent être terminées."
    _terminer(client_mecanicien, ordre, 1)
    assert _statut(client_mecanicien, ordre["id"], "termine").status_code == 200


def test_statut_inconnu_ou_ordre_inconnu(
    client_mecanicien: TestClient, ordre: dict[str, Any]
) -> None:
    assert _statut(client_mecanicien, ordre["id"], "urgent").status_code == 422
    assert _statut(client_mecanicien, 999999, "en_cours").status_code == 404
    assert _statut(client_mecanicien, 2147483648, "en_cours").status_code == 404


# --- Tâches --------------------------------------------------------------------------------


def test_terminer_puis_rouvrir_une_tache(
    horloge: Horloge,
    client_mecanicien: TestClient,
    ordre: dict[str, Any],
    mecanicien: Utilisateur,
) -> None:
    horloge.avancer(minutes=28)  # 15 h 15 à Paris
    terminee = _terminer(client_mecanicien, ordre, 0)

    assert terminee.status_code == 200
    tache = terminee.json()["taches"][0]
    assert tache["terminee"] is True
    assert tache["terminee_le"] == "2026-11-02T14:15:00Z"
    assert tache["terminee_par"] == {"id": mecanicien.id, "nom": "Karim B."}
    assert terminee.json()["taches_terminees"] == 1

    # Cocher de nouveau ne change pas l'heure de fin.
    horloge.avancer(minutes=5)
    assert _terminer(client_mecanicien, ordre, 0).json()["taches"][0]["terminee_le"] == (
        "2026-11-02T14:15:00Z"
    )

    rouverte = client_mecanicien.post(f"/ordres/{ordre['id']}/taches/{tache['id']}/rouvrir")
    assert rouverte.status_code == 200
    assert rouverte.json()["taches"][0] | {"id": 0} == {
        "id": 0,
        "libelle": "Diagnostic bruit de freinage",
        "duree_prevue_minutes": 30,
        "position": 0,
        "terminee": False,
        "terminee_le": None,
        "terminee_par": None,
    }


def test_tache_d_un_autre_ordre_introuvable(
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    ordre: dict[str, Any],
    vehicule: Vehicule,
) -> None:
    autre = client_gerant.post(
        "/ordres",
        json={
            "vehicule_id": vehicule.id,
            "demande_client": "Vidange",
            "taches": [{"libelle": "Vidange", "duree_prevue_minutes": 30}],
        },
    ).json()

    reponse = client_mecanicien.post(
        f"/ordres/{ordre['id']}/taches/{autre['taches'][0]['id']}/terminer"
    )

    assert reponse.status_code == 404
    assert reponse.json()["message"] == "Tâche introuvable pour cet ordre de travail."


def test_un_ordre_livre_verrouille_les_taches(
    client_mecanicien: TestClient, client_gerant: TestClient, ordre: dict[str, Any]
) -> None:
    _statut(client_mecanicien, ordre["id"], "en_cours")
    _tout_terminer(client_mecanicien, ordre)
    _statut(client_mecanicien, ordre["id"], "termine")
    _statut(client_gerant, ordre["id"], "livre")
    tache = ordre["taches"][0]

    for action in ("terminer", "rouvrir"):
        reponse = client_mecanicien.post(f"/ordres/{ordre['id']}/taches/{tache['id']}/{action}")
        assert reponse.status_code == 409
        assert reponse.json()["code"] == "ordre_livre"


def test_un_vehicule_pret_ne_rouvre_pas_de_tache(
    client_mecanicien: TestClient, ordre: dict[str, Any]
) -> None:
    _statut(client_mecanicien, ordre["id"], "en_cours")
    _tout_terminer(client_mecanicien, ordre)
    _statut(client_mecanicien, ordre["id"], "termine")
    tache = ordre["taches"][0]

    reponse = client_mecanicien.post(f"/ordres/{ordre['id']}/taches/{tache['id']}/rouvrir")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "ordre_pret"


# --- Accès ---------------------------------------------------------------------------------


def test_le_mecanicien_fait_avancer_un_ordre_qui_ne_lui_est_pas_affecte(
    client_mecanicien: TestClient, ordre: dict[str, Any]
) -> None:
    assert ordre["mecanicien"] is None

    reponse = _statut(client_mecanicien, ordre["id"], "en_cours")

    assert reponse.status_code == 200
    assert reponse.json()["client"]["contact"] is None


def test_sans_session_ni_jeton_csrf(client: TestClient, client_anonyme: TestClient) -> None:
    assert _statut(client_anonyme, 1, "en_cours").status_code == 401
    assert client_anonyme.post("/ordres/1/taches/1/terminer").status_code == 401
    # Sans jeton CSRF, refus avant même l'authentification.
    reponse = client.post("/ordres/1/statut", json={"nouveau": "en_cours"})
    assert reponse.status_code == 403
    assert reponse.json()["code"] == "csrf_invalide"


# --- Vue atelier (kanban) ------------------------------------------------------------------


def test_vue_atelier_sans_les_livraisons_des_jours_precedents(
    horloge: Horloge,
    client_gerant: TestClient,
    ordre: dict[str, Any],
    vehicule: Vehicule,
    db: Session,
) -> None:
    ancien = db.get_one(OrdreTravail, ordre["id"])
    ancien.statut = LIVRE
    ancien.ouvert_le = horloge.maintenant.replace(day=1, hour=7)
    ancien.cloture_le = horloge.maintenant.replace(day=1)  # livré hier
    du_jour = client_gerant.post(
        "/ordres", json={"vehicule_id": vehicule.id, "demande_client": "Pneus"}
    ).json()
    en_attente = client_gerant.post(
        "/ordres", json={"vehicule_id": vehicule.id, "demande_client": "Vidange"}
    ).json()
    livre_aujourd_hui = db.get_one(OrdreTravail, du_jour["id"])
    livre_aujourd_hui.statut = LIVRE
    livre_aujourd_hui.cloture_le = horloge.maintenant
    db.flush()

    atelier = client_gerant.get("/ordres?atelier=true").json()["elements"]

    assert sorted(o["numero"] for o in atelier) == sorted([du_jour["numero"], en_attente["numero"]])
    assert len(client_gerant.get("/ordres").json()["elements"]) == 3


# --- Base de données -----------------------------------------------------------------------


def test_migration_ajoute_la_ligne_de_creation_et_la_base_refuse_un_faux_changement(
    ordre: dict[str, Any], db: Session, engine: Engine
) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO historique_statut (ordre_travail_id, ancien, nouveau, change_le,"
                " utilisateur_id) SELECT :id, 'en_cours', 'en_cours', now(), cree_par"
                " FROM ordre_travail WHERE id = :id"
            ),
            {"id": ordre["id"]},
        )
    migration = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "alembic/versions/20261118_0007_historique_statut.py"
    ).read_text(encoding="utf-8")
    assert re.search(
        r"SELECT id, NULL, 'a_faire', ouvert_le, cree_par FROM ordre_travail", migration
    )
