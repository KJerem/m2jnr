"""Story S4.2 — statut du devis : brouillon → envoyé → accepté ou refusé ; seul un devis
accepté se facture ; un devis refusé se remplace par un nouveau."""

import importlib.util
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    Client,
    OrdreTravail,
    Role,
    StatutDevis,
    StatutOT,
    Utilisateur,
    Vehicule,
)
from app.services.statut_devis import (
    MESSAGE_DEVIS_NON_ACCEPTE,
    MESSAGE_DEVIS_VERROUILLE,
    TRANSITIONS_DEVIS,
    verifier_transition_devis,
)
from tests.conftest import Horloge
from tests.test_s4_1_devis import LIGNES_BACKLOG, LIGNES_MAQUETTE

NBSP = " "
B, E, A, R = (StatutDevis.BROUILLON, StatutDevis.ENVOYE, StatutDevis.ACCEPTE, StatutDevis.REFUSE)


def _ordre(db: Session, gerant: Utilisateur, statut: StatutOT = StatutOT.TERMINE) -> OrdreTravail:
    rang = db.scalar(select(OrdreTravail.id).order_by(OrdreTravail.id.desc()).limit(1)) or 0
    client = Client(nom="Diallo", prenom="Moussa", telephone="0645716308")
    db.add(client)
    db.flush()
    vehicule = Vehicule(
        client_id=client.id,
        immatriculation=f"FD-{rang % 899 + 101:03d}-RT",
        marque="Renault",
        modele="Clio V",
        kilometrage=38_900,
    )
    ordre = OrdreTravail(
        numero=f"OT-2026-{rang + 1:03d}",
        vehicule=vehicule,
        demande_client="Voyant moteur allumé.",
        statut=statut,
        ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
        createur=gerant,
    )
    db.add_all([vehicule, ordre])
    db.flush()
    return ordre


@pytest.fixture
def nouvel_ordre(db: Session, gerant: Utilisateur) -> Callable[..., OrdreTravail]:
    def _nouveau(statut: StatutOT = StatutOT.TERMINE) -> OrdreTravail:
        return _ordre(db, gerant, statut)

    return _nouveau


def _creer(c: TestClient, ordre_id: int, lignes: list[dict[str, Any]] = LIGNES_BACKLOG) -> Any:
    reponse = c.post(f"/ordres/{ordre_id}/devis", json={"lignes": lignes})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _statut(c: TestClient, devis_id: int, nouveau: str) -> Any:
    return c.post(f"/devis/{devis_id}/statut", json={"nouveau": nouveau})


def _amener(c: TestClient, devis_id: int, cible: StatutDevis) -> Any:
    """Fait passer un brouillon jusqu'au statut voulu par les seules transitions permises."""
    chemin = {B: [], E: ["envoye"], A: ["envoye", "accepte"], R: ["envoye", "refuse"]}[cible]
    corps = c.get(f"/devis/{devis_id}").json()
    for etape in chemin:
        reponse = _statut(c, devis_id, etape)
        assert reponse.status_code == 200, reponse.text
        corps = reponse.json()
    return corps


# --- Règle pure : chaque passage autorisé ou interdit -----------------------------------------

AUTORISEES = {(B, E), (E, A), (E, R)}


@pytest.mark.parametrize("ancien", list(StatutDevis))
@pytest.mark.parametrize("nouveau", list(StatutDevis))
def test_chaque_transition_autorisee_ou_interdite(
    ancien: StatutDevis, nouveau: StatutDevis
) -> None:
    if (ancien, nouveau) in AUTORISEES:
        verifier_transition_devis(ancien, nouveau)
        return
    with pytest.raises(AppError) as erreur:
        verifier_transition_devis(ancien, nouveau)
    assert (erreur.value.status_code, erreur.value.code) == (409, "transition_devis_interdite")
    assert erreur.value.details == {"statut": ancien.value}


def test_table_des_transitions() -> None:
    assert {(a, n) for a, suivants in TRANSITIONS_DEVIS.items() for n in suivants} == AUTORISEES


@pytest.mark.parametrize(
    ("ancien", "nouveau", "message"),
    [
        (B, B, "Le devis est déjà « Brouillon »."),
        (E, E, "Le devis est déjà « Envoyé »."),
        (
            B,
            A,
            "Passage de « Brouillon » à « Accepté » impossible : "
            "le devis doit d'abord être envoyé au client.",
        ),
        (E, B, "Passage de « Envoyé » à « Brouillon » impossible : pas de retour en arrière."),
        (A, R, "Le devis est « Accepté » : la décision du client est définitive."),
        (R, A, "Le devis est « Refusé » : la décision du client est définitive."),
    ],
)
def test_messages_en_francais(ancien: StatutDevis, nouveau: StatutDevis, message: str) -> None:
    with pytest.raises(AppError) as erreur:
        verifier_transition_devis(ancien, nouveau)
    assert erreur.value.message == message


# --- API : transitions, dates et auteur -------------------------------------------------------


def test_un_nouveau_devis_est_un_brouillon(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)

    assert (devis["statut"], devis["envoye_le"], devis["decide_le"], devis["decide_par"]) == (
        "brouillon",
        None,
        None,
        None,
    )


def test_envoi_puis_acceptation_dates_de_l_horloge_et_auteur(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)

    envoye = _statut(client_gerant, devis["id"], "envoye")
    assert envoye.status_code == 200
    assert envoye.json()["statut"] == "envoye"
    assert envoye.json()["envoye_le"] == "2026-11-02T13:47:00Z"
    assert envoye.json()["decide_le"] is None

    horloge.avancer(minutes=40)
    accepte = _statut(client_gerant, devis["id"], "accepte").json()

    assert accepte["statut"] == "accepte"
    assert accepte["envoye_le"] == "2026-11-02T13:47:00Z"
    assert accepte["decide_le"] == "2026-11-02T14:27:00Z"
    assert accepte["decide_par"] == {"id": gerant.id, "nom": "Nadia Benali"}
    resume = client_gerant.get("/devis").json()["elements"][0]
    assert (resume["statut"], resume["decide_le"]) == ("accepte", "2026-11-02T14:27:00Z")


def test_refus_date_et_auteur(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)
    _statut(client_gerant, devis["id"], "envoye")
    horloge.avancer(hours=3)

    refuse = _statut(client_gerant, devis["id"], "refuse").json()

    assert (refuse["statut"], refuse["decide_le"]) == ("refuse", "2026-11-02T16:47:00Z")
    assert refuse["decide_par"]["id"] == gerant.id


@pytest.mark.parametrize(
    ("depart", "nouveau"),
    [(B, "accepte"), (B, "refuse"), (E, "envoye"), (A, "refuse"), (A, "envoye"), (R, "accepte")],
)
def test_transition_interdite_par_l_api_409(
    client_gerant: TestClient,
    nouvel_ordre: Callable[..., OrdreTravail],
    depart: StatutDevis,
    nouveau: str,
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)
    avant = _amener(client_gerant, devis["id"], depart)

    reponse = _statut(client_gerant, devis["id"], nouveau)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "transition_devis_interdite"
    assert reponse.json()["statut"] == depart.value
    assert client_gerant.get(f"/devis/{devis['id']}").json() == avant


def test_statut_inconnu_422_et_devis_inconnu_404(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)

    assert _statut(client_gerant, devis["id"], "facture").status_code == 422
    assert _statut(client_gerant, devis["id"], "brouillon").status_code == 409
    for identifiant in (999_999, 2**31):
        assert _statut(client_gerant, identifiant, "envoye").status_code == 404


# --- Verrouillage des lignes hors brouillon ---------------------------------------------------


def test_un_brouillon_se_modifie(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)

    reponse = client_gerant.put(f"/devis/{devis['id']}", json={"lignes": LIGNES_MAQUETTE})

    assert reponse.status_code == 200
    assert reponse.json()["totaux"]["total_ttc_centimes"] == 45_480


@pytest.mark.parametrize("statut", [E, A, R])
def test_lignes_verrouillees_hors_brouillon_409(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], statut: StatutDevis
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)
    _amener(client_gerant, devis["id"], statut)

    reponse = client_gerant.put(f"/devis/{devis['id']}", json={"lignes": LIGNES_MAQUETTE})

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "devis_verrouille"
    assert reponse.json()["message"] == MESSAGE_DEVIS_VERROUILLE
    assert MESSAGE_DEVIS_VERROUILLE == (
        "Ce devis a été envoyé : il ne se modifie plus. "
        "Refusé, il peut être remplacé par un nouveau devis."
    )
    assert client_gerant.get(f"/devis/{devis['id']}").json()["totaux"]["total_ttc_centimes"] == (
        16_800
    )


# --- Facturation réservée au devis accepté ----------------------------------------------------


@pytest.mark.parametrize("statut", [B, E, R])
def test_facture_refusee_tant_que_le_devis_n_est_pas_accepte(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], statut: StatutDevis
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)
    _amener(client_gerant, devis["id"], statut)

    reponse = client_gerant.post(f"/devis/{devis['id']}/facture")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "devis_non_accepte"
    assert reponse.json()["message"] == MESSAGE_DEVIS_NON_ACCEPTE
    assert MESSAGE_DEVIS_NON_ACCEPTE == "Seul un devis accepté peut être facturé."
    assert client_gerant.get("/factures").json()["total"] == 0


def test_devis_accepte_facture(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)
    _amener(client_gerant, devis["id"], A)

    reponse = client_gerant.post(f"/devis/{devis['id']}/facture")

    assert reponse.status_code == 201
    assert reponse.json()["totaux"]["total_ttc_centimes"] == 16_800


def test_ordre_des_controles_de_facturation(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    """Déjà facturé passe avant non accepté ; non accepté passe avant l'OT non terminé."""
    en_cours = _creer(client_gerant, nouvel_ordre(StatutOT.EN_COURS).id)
    assert client_gerant.post(f"/devis/{en_cours['id']}/facture").json()["code"] == (
        "devis_non_accepte"
    )
    _amener(client_gerant, en_cours["id"], A)
    assert client_gerant.post(f"/devis/{en_cours['id']}/facture").json()["code"] == (
        "ordre_non_termine"
    )

    facture = _creer(client_gerant, nouvel_ordre().id)
    _amener(client_gerant, facture["id"], A)
    assert client_gerant.post(f"/devis/{facture['id']}/facture").status_code == 201
    assert client_gerant.post(f"/devis/{facture['id']}/facture").json()["code"] == (
        "devis_deja_facture"
    )


def test_devis_facture_reste_fige(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)
    _amener(client_gerant, devis["id"], A)
    client_gerant.post(f"/devis/{devis['id']}/facture")

    assert _statut(client_gerant, devis["id"], "refuse").json()["code"] == (
        "transition_devis_interdite"
    )
    modification = client_gerant.put(f"/devis/{devis['id']}", json={"lignes": LIGNES_MAQUETTE})
    assert modification.json()["code"] == "devis_facture"


# --- Nouveau devis après un refus -------------------------------------------------------------


def test_nouveau_devis_apres_un_refus(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    ordre = nouvel_ordre()
    premier = _creer(client_gerant, ordre.id)
    _amener(client_gerant, premier["id"], R)
    assert client_gerant.get(f"/ordres/{ordre.id}/devis").json()["id"] == premier["id"]

    second = _creer(client_gerant, ordre.id, LIGNES_MAQUETTE)

    assert second["statut"] == "brouillon"
    courant = client_gerant.get(f"/ordres/{ordre.id}/devis").json()
    assert (courant["id"], courant["totaux"]["total_ttc_centimes"]) == (second["id"], 45_480)
    assert client_gerant.get(f"/devis/{premier['id']}").json()["statut"] == "refuse"
    assert client_gerant.get("/devis").json()["total"] == 2


@pytest.mark.parametrize("statut", [B, E, A])
def test_pas_de_second_devis_tant_qu_un_devis_n_est_pas_refuse(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], statut: StatutDevis
) -> None:
    ordre = nouvel_ordre()
    refuse = _creer(client_gerant, ordre.id)
    _amener(client_gerant, refuse["id"], R)
    en_cours = _creer(client_gerant, ordre.id)
    _amener(client_gerant, en_cours["id"], statut)

    reponse = client_gerant.post(f"/ordres/{ordre.id}/devis", json={"lignes": LIGNES_MAQUETTE})

    assert reponse.status_code == 409
    corps = reponse.json()
    assert (corps["code"], corps["devis_id"], corps["statut"]) == (
        "devis_existant",
        en_cours["id"],
        statut.value,
    )
    if statut == B:
        assert corps["message"] == "Cet ordre de travail a déjà un devis : modifiez-le."
    else:
        assert "un nouveau devis n'est possible qu'après un refus du client" in corps["message"]


def test_la_base_refuse_deux_devis_non_refuses_sur_un_ot(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], db: Session
) -> None:
    ordre = nouvel_ordre()
    _creer(client_gerant, ordre.id)
    copie = (
        "INSERT INTO devis (ordre_travail_id, total_ht_centimes, total_tva_centimes,"
        " total_ttc_centimes, cree_par, statut) SELECT ordre_travail_id, 0, 0, 0, cree_par,"
        " CAST(:statut AS statut_devis) FROM devis WHERE ordre_travail_id = :ordre"
    )

    with pytest.raises(IntegrityError) as erreur, db.begin_nested():
        db.execute(text(copie), {"statut": "brouillon", "ordre": ordre.id})
    assert "uq_devis_ordre_non_refuse" in str(erreur.value.orig)

    # Un devis refusé à côté est permis (date d'envoi et de décision : contrainte de cohérence).
    with db.begin_nested():
        db.execute(
            text(
                "INSERT INTO devis (ordre_travail_id, total_ht_centimes, total_tva_centimes,"
                " total_ttc_centimes, cree_par, statut, envoye_le, decide_le)"
                " SELECT ordre_travail_id, 0, 0, 0, cree_par, 'refuse', now(), now()"
                " FROM devis WHERE ordre_travail_id = :ordre"
            ),
            {"ordre": ordre.id},
        )


def test_la_base_refuse_un_statut_incoherent_avec_ses_dates(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], db: Session
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)

    for requete in (
        "UPDATE devis SET statut = 'envoye' WHERE id = :id",
        "UPDATE devis SET statut = 'accepte', envoye_le = now() WHERE id = :id",
        "UPDATE devis SET envoye_le = now() WHERE id = :id",
    ):
        with pytest.raises(IntegrityError) as erreur, db.begin_nested():
            db.execute(text(requete), {"id": devis["id"]})
        assert "ck_devis_statut_coherent" in str(erreur.value.orig)


# --- Accès ------------------------------------------------------------------------------------


def test_mecanicien_refuse_sur_le_statut_du_devis(
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    devis = _creer(client_gerant, nouvel_ordre().id)

    reponse = _statut(client_mecanicien, devis["id"], "envoye")

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "interdit"
    assert client_gerant.get(f"/devis/{devis['id']}").json()["statut"] == "brouillon"


def test_sans_session_401_et_sans_csrf_403(client_anonyme: TestClient, client: TestClient) -> None:
    assert _statut(client_anonyme, 1, "envoye").status_code == 401
    assert _statut(client, 1, "envoye").status_code == 403


# --- Tableau de bord --------------------------------------------------------------------------


def test_tableau_de_bord_devis_a_faire_valider_et_facture_a_etablir(
    horloge: Horloge, client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    brouillon = nouvel_ordre()
    _creer(client_gerant, brouillon.id)  # brouillon d'un OT « Prêt » : rien à traiter
    envoye = nouvel_ordre(StatutOT.A_FAIRE)
    devis_envoye = _creer(client_gerant, envoye.id, LIGNES_MAQUETTE)
    _amener(client_gerant, devis_envoye["id"], E)
    accepte = nouvel_ordre()
    _amener(client_gerant, _creer(client_gerant, accepte.id)["id"], A)
    refuse = nouvel_ordre()
    _amener(client_gerant, _creer(client_gerant, refuse.id)["id"], R)

    a_traiter = client_gerant.get("/tableau-de-bord").json()["a_traiter"]
    devis = [a for a in a_traiter if a["type"] in ("devis_a_valider", "facture_a_etablir")]

    assert devis == [
        {
            "type": "facture_a_etablir",
            "titre": "Facture à établir",
            "detail": f"Moussa Diallo · Renault Clio V · {accepte.numero} · 168,00{NBSP}€ TTC",
            "ordre_id": accepte.id,
            "numero": accepte.numero,
            "utilisateur_id": None,
        },
        {
            "type": "devis_a_valider",
            "titre": "Devis à faire valider",
            "detail": (
                f"Moussa Diallo · Renault Clio V · 454,80{NBSP}€ TTC envoyé à 14{NBSP}h{NBSP}47"
            ),
            "ordre_id": envoye.id,
            "numero": envoye.numero,
            "utilisateur_id": None,
        },
    ]

    horloge.avancer(hours=9, minutes=30)  # 0 h 17 le lendemain à Paris, session encore valide
    detail = next(
        a["detail"]
        for a in client_gerant.get("/tableau-de-bord").json()["a_traiter"]
        if a["type"] == "devis_a_valider"
    )
    assert detail.endswith(f"envoyé le lun. 2 nov. à 14{NBSP}h{NBSP}47")


# --- Migration 0012 : reprise des devis existants ---------------------------------------------


def _migration(nom: str) -> ModuleType:
    chemin = Path(__file__).resolve().parent.parent / "alembic" / "versions" / nom
    spec = importlib.util.spec_from_file_location(chemin.stem, chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0012_devis_factures_acceptes_les_autres_en_brouillon(engine: Engine) -> None:
    """Rejoue downgrade puis upgrade de 0012 dans une transaction annulée (DDL transactionnel) :
    un devis déjà facturé devient « accepté » à la date d'émission de sa facture, par l'auteur
    de la facture ; un devis non facturé reste « brouillon ». La facture n'est pas touchée."""
    migration = _migration("20261214_0012_statut_devis.py")
    with engine.connect() as connexion:
        transaction = connexion.begin()
        try:
            s = Session(bind=connexion, join_transaction_mode="create_savepoint")
            gerant = Utilisateur(
                email="migration@garage.test",
                prenom="Nadia",
                nom="Migration",
                role=Role.GERANT,
                mot_de_passe_hash="x",
            )
            client = Client(nom="Migration", telephone="0612483075")
            s.add_all([gerant, client])
            s.flush()
            vehicule = Vehicule(
                client_id=client.id,
                immatriculation="ZZ-012-ZZ",
                marque="Peugeot",
                modele="308",
                kilometrage=1,
            )
            ordres = [
                OrdreTravail(
                    numero=f"OT-2091-00{i}",
                    vehicule=vehicule,
                    demande_client="Reprise.",
                    statut=StatutOT.LIVRE,
                    ouvert_le=datetime(2091, 1, 2, 8, tzinfo=UTC),
                    createur=gerant,
                )
                for i in (1, 2)
            ]
            s.add_all([vehicule, *ordres])
            s.flush()
            ids = []
            for ordre in ordres:
                ids.append(
                    connexion.execute(
                        text(
                            "INSERT INTO devis (ordre_travail_id, total_ht_centimes,"
                            " total_tva_centimes, total_ttc_centimes, cree_par)"
                            " VALUES (:o, 100, 20, 120, :g) RETURNING id"
                        ),
                        {"o": ordre.id, "g": gerant.id},
                    ).scalar_one()
                )
            connexion.execute(
                text(
                    "INSERT INTO facture (numero, devis_id, ordre_travail_id, emise_le, echeance,"
                    " client_fige, vehicule_fige, garage_fige, taux_tva_bp, total_ht_centimes,"
                    " total_tva_centimes, total_ttc_centimes, cree_par) VALUES"
                    " ('F-2091-001', :d, :o, '2091-01-03T10:00:00Z', '2091-02-02', '{}', '{}',"
                    " '{}', 2000, 100, 20, 120, :g)"
                ),
                {"d": ids[0], "o": ordres[0].id, "g": gerant.id},
            )

            with Operations.context(MigrationContext.configure(connexion)):
                migration.downgrade()
                migration.upgrade()

            lignes = connexion.execute(
                text(
                    "SELECT id, statut, envoye_le, decide_le, decide_par FROM devis"
                    " WHERE id = ANY(:ids) ORDER BY id"
                ),
                {"ids": ids},
            ).all()
            emise = datetime(2091, 1, 3, 10, tzinfo=UTC)
            assert [tuple(ligne) for ligne in lignes] == [
                (ids[0], "accepte", emise, emise, gerant.id),
                (ids[1], "brouillon", None, None, None),
            ]
        finally:
            transaction.rollback()
    with engine.connect() as connexion:
        reste = "SELECT count(*) FROM facture WHERE numero = 'F-2091-001'"
        assert connexion.execute(text(reste)).scalar() == 0
        defaut = connexion.execute(
            text(
                "SELECT column_default FROM information_schema.columns"
                " WHERE table_name = 'devis' AND column_name = 'statut'"
            )
        ).scalar()
        assert defaut is not None and "brouillon" in defaut
