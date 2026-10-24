"""Story S3.1 — ordre de travail : numérotation sans trou, véhicule obligatoire, tâches, accès."""

import threading
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Client, Compteur, OrdreTravail, Role, StatutOT, Utilisateur, Vehicule
from app.schemas.ordre import MESSAGE_VEHICULE_OBLIGATOIRE
from app.services.delais import est_en_retard
from app.services.numerotation import formater_numero, prochain_numero
from app.services.ordres import message_kilometrage_inferieur
from tests.conftest import Horloge, MakeUser, connecter


@pytest.fixture
def vehicule(db: Session) -> Vehicule:
    client = Client(
        nom="Laurent", prenom="Claire", telephone="0612483075", email="claire@exemple.test"
    )
    db.add(client)
    db.flush()
    vehicule = Vehicule(
        client_id=client.id,
        immatriculation="GH-482-KL",
        marque="Peugeot",
        modele="308 SW",
        kilometrage=84312,
        vin="VF3LCYHZPKS123456",
    )
    db.add(vehicule)
    db.flush()
    return vehicule


def _ordre(vehicule: Vehicule, **surcharges: Any) -> dict[str, Any]:
    corps: dict[str, Any] = {
        "vehicule_id": vehicule.id,
        "demande_client": "Bruit au freinage côté avant gauche, surtout à basse vitesse.",
        "taches": [
            {"libelle": "Diagnostic bruit de freinage", "duree_prevue_minutes": 30},
            {"libelle": "Remplacement plaquettes et disques avant", "duree_prevue_minutes": 90},
            {"libelle": "Vidange moteur et filtre à huile", "duree_prevue_minutes": 30},
        ],
    }
    corps.update(surcharges)
    return corps


def _creer(c: TestClient, vehicule: Vehicule, **surcharges: Any) -> dict[str, Any]:
    reponse = c.post("/ordres", json=_ordre(vehicule, **surcharges))
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


# --- Numérotation ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rang", "attendu"),
    [(1, "OT-2026-001"), (42, "OT-2026-042"), (999, "OT-2026-999"), (1000, "OT-2026-1000")],
)
def test_format_du_numero(rang: int, attendu: str) -> None:
    assert formater_numero("OT", 2026, rang) == attendu


def test_numeros_uniques_et_consecutifs(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule
) -> None:
    numeros = [_creer(client_gerant, vehicule)["numero"] for _ in range(3)]

    assert numeros == ["OT-2026-001", "OT-2026-002", "OT-2026-003"]


def test_changement_d_annee_a_l_heure_de_paris(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule, gerant: Utilisateur
) -> None:
    # 31 décembre 2026 à 23 h 30 à Paris (22 h 30 UTC) : encore 2026.
    horloge.maintenant = datetime(2026, 12, 31, 22, 30, tzinfo=UTC)
    connecter(client_gerant, gerant.email)
    assert _creer(client_gerant, vehicule)["numero"] == "OT-2026-001"
    # 1er janvier 2027 à 0 h 30 à Paris (23 h 30 UTC la veille) : la série repart à 001.
    horloge.maintenant = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)
    assert _creer(client_gerant, vehicule)["numero"] == "OT-2027-001"
    assert _creer(client_gerant, vehicule)["numero"] == "OT-2027-002"


def test_une_creation_annulee_ne_laisse_pas_de_trou(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule, db: Session
) -> None:
    assert _creer(client_gerant, vehicule)["numero"] == "OT-2026-001"

    # Le numéro 002 est réservé, puis la transaction est annulée (erreur pendant l'insertion).
    with pytest.raises(IntegrityError), db.begin_nested():
        assert prochain_numero(db, "OT", 2026) == "OT-2026-002"
        db.execute(text("INSERT INTO ordre_travail (numero) VALUES ('OT-2026-002')"))

    assert _creer(client_gerant, vehicule)["numero"] == "OT-2026-002"


def test_une_validation_refusee_ne_consomme_pas_de_numero(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule
) -> None:
    _creer(client_gerant, vehicule)
    refus = client_gerant.post("/ordres", json=_ordre(vehicule, kilometrage_entree=10))
    assert refus.status_code == 422

    assert _creer(client_gerant, vehicule)["numero"] == "OT-2026-002"


@pytest.fixture
def annee_isolee(engine: Engine) -> Any:
    """Année réservée à un test qui valide réellement ses transactions ; nettoyée ensuite."""
    annee = 2091
    yield annee
    with engine.begin() as connexion:
        connexion.execute(delete(Compteur).where(Compteur.annee == annee))


def test_deux_transactions_concurrentes_obtiennent_des_numeros_consecutifs(
    engine: Engine, annee_isolee: int
) -> None:
    resultats: dict[str, str] = {}
    erreurs: list[BaseException] = []

    def seconde_transaction() -> None:
        try:
            with Session(engine) as session:
                resultats["seconde"] = prochain_numero(session, "OT", annee_isolee)
                session.commit()
        except BaseException as exc:  # pragma: no cover - remonté par l'assertion
            erreurs.append(exc)

    with Session(engine) as premiere:
        resultats["premiere"] = prochain_numero(premiere, "OT", annee_isolee)
        fil = threading.Thread(target=seconde_transaction)
        fil.start()
        fil.join(timeout=0.5)
        # La seconde transaction attend le verrou de la première…
        assert fil.is_alive()
        premiere.commit()
    # … puis lit la valeur validée et prend le numéro suivant.
    fil.join(timeout=10)

    assert not fil.is_alive()
    assert erreurs == []
    assert resultats == {"premiere": "OT-2091-001", "seconde": "OT-2091-002"}


def test_transaction_annulee_puis_concurrente_sans_trou(engine: Engine, annee_isolee: int) -> None:
    with Session(engine) as premiere:
        assert prochain_numero(premiere, "OT", annee_isolee) == "OT-2091-001"
        premiere.rollback()
    with Session(engine) as seconde:
        assert prochain_numero(seconde, "OT", annee_isolee) == "OT-2091-001"
        seconde.commit()
    with Session(engine) as troisieme:
        assert prochain_numero(troisieme, "OT", annee_isolee) == "OT-2091-002"
        troisieme.commit()


# --- Création -------------------------------------------------------------------------------


def test_creation_d_un_ordre_de_travail(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule, gerant: Utilisateur
) -> None:
    ordre = _creer(client_gerant, vehicule, diagnostic="  ", prioritaire=True)

    assert ordre["statut"] == "a_faire"
    assert ordre["prioritaire"] is True
    assert ordre["diagnostic"] is None
    assert ordre["ouvert_le"] == "2026-11-02T13:47:00Z"
    assert ordre["cloture_le"] is None
    assert ordre["cree_par"] == {"id": gerant.id, "nom": "Nadia Benali"}
    assert ordre["mecanicien"] is None
    assert ordre["vehicule"]["immatriculation"] == "GH-482-KL"
    assert ordre["vehicule"]["vin"] == "VF3LCYHZPKS123456"
    assert ordre["client"]["nom"] == "Laurent"
    assert ordre["client"]["contact"] == {
        "telephone": "0612483075",
        "email": "claire@exemple.test",
    }
    assert [(t["libelle"], t["duree_prevue_minutes"], t["position"]) for t in ordre["taches"]] == [
        ("Diagnostic bruit de freinage", 30, 0),
        ("Remplacement plaquettes et disques avant", 90, 1),
        ("Vidange moteur et filtre à huile", 30, 2),
    ]
    assert (ordre["taches_terminees"], ordre["taches_total"]) == (0, 3)
    assert ordre["duree_prevue_minutes"] == 150
    assert ordre["en_retard"] is False


def test_restitution_sans_fuseau_lue_a_l_heure_de_paris(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule
) -> None:
    sans_fuseau = _creer(client_gerant, vehicule, restitution_prevue="2026-11-02T17:30")
    avec_fuseau = _creer(client_gerant, vehicule, restitution_prevue="2026-11-02T17:30:00+01:00")

    assert sans_fuseau["restitution_prevue"] == "2026-11-02T16:30:00Z"
    assert avec_fuseau["restitution_prevue"] == "2026-11-02T16:30:00Z"


@pytest.mark.parametrize("corps", [{}, {"vehicule_id": None}])
def test_vehicule_obligatoire(client_gerant: TestClient, vehicule: Vehicule, corps: Any) -> None:
    donnees = _ordre(vehicule)
    del donnees["vehicule_id"]
    donnees.update(corps)

    reponse = client_gerant.post("/ordres", json=donnees)

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"vehicule_id": MESSAGE_VEHICULE_OBLIGATOIRE}


def test_vehicule_inconnu_404(client_gerant: TestClient, vehicule: Vehicule) -> None:
    reponse = client_gerant.post("/ordres", json=_ordre(vehicule, vehicule_id=999999))

    assert reponse.status_code == 404
    assert reponse.json()["message"] == MESSAGE_VEHICULE_OBLIGATOIRE
    assert reponse.json()["champs"] == {"vehicule_id": "Véhicule introuvable."}


@pytest.mark.parametrize("valeur", ["3", True, 2_147_483_648])
def test_identifiant_de_vehicule_mal_forme_422(
    client_gerant: TestClient, vehicule: Vehicule, valeur: Any
) -> None:
    reponse = client_gerant.post("/ordres", json=_ordre(vehicule, vehicule_id=valeur))

    assert reponse.status_code == 422
    assert "vehicule_id" in reponse.json()["champs"]


def test_demande_du_client_obligatoire(client_gerant: TestClient, vehicule: Vehicule) -> None:
    reponse = client_gerant.post("/ordres", json=_ordre(vehicule, demande_client="   "))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"demande_client": "Champ obligatoire."}


@pytest.mark.parametrize(
    ("tache", "champ"),
    [
        ({"libelle": "", "duree_prevue_minutes": 30}, "taches.0.libelle"),
        ({"libelle": "Vidange", "duree_prevue_minutes": 0}, "taches.0.duree_prevue_minutes"),
        ({"libelle": "Vidange", "duree_prevue_minutes": 601}, "taches.0.duree_prevue_minutes"),
        ({"libelle": "Vidange", "duree_prevue_minutes": "30"}, "taches.0.duree_prevue_minutes"),
    ],
)
def test_tache_invalide(
    client_gerant: TestClient, vehicule: Vehicule, tache: dict[str, Any], champ: str
) -> None:
    reponse = client_gerant.post("/ordres", json=_ordre(vehicule, taches=[tache]))

    assert reponse.status_code == 422
    assert list(reponse.json()["champs"]) == [champ]


def test_affectation_d_un_mecanicien_actif(
    client_gerant: TestClient, vehicule: Vehicule, mecanicien: Utilisateur
) -> None:
    ordre = _creer(client_gerant, vehicule, mecanicien_id=mecanicien.id)

    assert ordre["mecanicien"] == {"id": mecanicien.id, "nom": "Karim B."}


def test_le_mecanicien_affecte_doit_etre_un_mecanicien_actif(
    client_gerant: TestClient, vehicule: Vehicule, gerant: Utilisateur, make_user: MakeUser
) -> None:
    inactif = make_user(Role.MECANICIEN, actif=False)
    for identifiant in (gerant.id, inactif.id, 999999):
        reponse = client_gerant.post("/ordres", json=_ordre(vehicule, mecanicien_id=identifiant))
        assert reponse.status_code == 422
        assert reponse.json()["champs"] == {"mecanicien_id": "Choisissez un mécanicien actif."}


def test_kilometrage_d_entree_superieur_met_a_jour_le_vehicule(
    client_gerant: TestClient, vehicule: Vehicule, db: Session
) -> None:
    ordre = _creer(client_gerant, vehicule, kilometrage_entree=85000)

    assert ordre["kilometrage_entree"] == 85000
    assert ordre["vehicule"]["kilometrage"] == 85000
    db.refresh(vehicule)
    assert vehicule.kilometrage == 85000


def test_kilometrage_d_entree_egal_accepte(client_gerant: TestClient, vehicule: Vehicule) -> None:
    ordre = _creer(client_gerant, vehicule, kilometrage_entree=84312)

    assert ordre["vehicule"]["kilometrage"] == 84312


def test_kilometrage_d_entree_inferieur_refuse(
    client_gerant: TestClient, vehicule: Vehicule, db: Session
) -> None:
    reponse = client_gerant.post("/ordres", json=_ordre(vehicule, kilometrage_entree=80000))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"kilometrage_entree": message_kilometrage_inferieur(84312)}
    assert "84 312 km" in reponse.json()["champs"]["kilometrage_entree"]
    assert db.scalar(select(OrdreTravail.id)) is None


@pytest.mark.parametrize(
    ("valeur", "message"),
    [(-1, "Doit être supérieur ou égal à 0."), ("12", "Nombre entier attendu.")],
)
def test_kilometrage_d_entree_mal_forme(
    client_gerant: TestClient, vehicule: Vehicule, valeur: Any, message: str
) -> None:
    reponse = client_gerant.post("/ordres", json=_ordre(vehicule, kilometrage_entree=valeur))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"kilometrage_entree": message}


# --- Consultation et liste ------------------------------------------------------------------


def test_le_mecanicien_lit_l_ordre_sans_les_coordonnees_du_client(
    client_gerant: TestClient, client_mecanicien: TestClient, vehicule: Vehicule
) -> None:
    ordre = _creer(client_gerant, vehicule)

    reponse = client_mecanicien.get(f"/ordres/{ordre['id']}")

    assert reponse.status_code == 200
    assert reponse.json()["client"] == {
        "id": vehicule.client_id,
        "nom": "Laurent",
        "prenom": "Claire",
        "contact": None,
    }
    assert "0612483075" not in reponse.text
    assert "claire@exemple.test" not in reponse.text
    liste = client_mecanicien.get("/ordres")
    assert liste.status_code == 200
    assert liste.json()["elements"][0]["client"]["contact"] is None
    assert "0612483075" not in liste.text


def test_ordre_inconnu_404(client_gerant: TestClient) -> None:
    for identifiant in ("999999", "2147483648", "-1"):
        reponse = client_gerant.get(f"/ordres/{identifiant}")
        assert reponse.status_code == 404
        assert reponse.json()["message"] == "Ordre de travail introuvable."


def test_liste_triee_et_filtree(
    horloge: Horloge,
    client_gerant: TestClient,
    vehicule: Vehicule,
    mecanicien: Utilisateur,
    db: Session,
) -> None:
    premier = _creer(client_gerant, vehicule)  # lundi 2 novembre, 14 h 47 à Paris
    horloge.avancer(hours=9, minutes=40)  # mardi 3 novembre, 0 h 27 à Paris (23 h 27 UTC)
    second = _creer(client_gerant, vehicule, mecanicien_id=mecanicien.id)
    db.get_one(OrdreTravail, second["id"]).statut = StatutOT.EN_COURS
    db.flush()

    tous = client_gerant.get("/ordres").json()
    assert [o["numero"] for o in tous["elements"]] == ["OT-2026-002", "OT-2026-001"]
    assert tous["total"] == 2

    def numeros(requete: str) -> list[str]:
        reponse = client_gerant.get(f"/ordres?{requete}")
        assert reponse.status_code == 200, reponse.text
        return [o["numero"] for o in reponse.json()["elements"]]

    assert numeros("statut=a_faire") == [premier["numero"]]
    assert numeros("statut=a_faire&statut=en_cours") == ["OT-2026-002", "OT-2026-001"]
    assert numeros(f"mecanicien_id={mecanicien.id}") == [second["numero"]]
    assert numeros(f"vehicule_id={vehicule.id}") == ["OT-2026-002", "OT-2026-001"]
    assert numeros("vehicule_id=999999") == []
    # Jours de Paris : le premier OT est ouvert le 2 novembre, le second le 3 (le 2 en UTC).
    assert numeros("du=2026-11-03") == [second["numero"]]
    assert numeros("au=2026-11-02") == [premier["numero"]]
    assert numeros("du=2026-11-02&au=2026-11-02") == [premier["numero"]]
    assert client_gerant.get("/ordres?du=2026-11-03&au=2026-11-02").status_code == 422
    assert client_gerant.get("/ordres?statut=urgent").status_code == 422
    assert client_gerant.get("/ordres?mecanicien_id=2147483648").status_code == 422


def test_carte_en_retard_si_l_heure_promise_est_depassee(
    horloge: Horloge, client_gerant: TestClient, vehicule: Vehicule
) -> None:
    _creer(client_gerant, vehicule, restitution_prevue="2026-11-02T12:00")

    carte = client_gerant.get("/ordres").json()["elements"][0]

    assert carte["en_retard"] is True


def test_regle_du_retard() -> None:
    promis = datetime(2026, 11, 2, 11, 0, tzinfo=UTC)
    apres = datetime(2026, 11, 2, 11, 1, tzinfo=UTC)
    assert est_en_retard(StatutOT.EN_COURS, promis, apres) is True
    assert est_en_retard(StatutOT.A_FAIRE, promis, apres) is True
    assert est_en_retard(StatutOT.TERMINE, promis, apres) is False
    assert est_en_retard(StatutOT.LIVRE, promis, apres) is False
    assert est_en_retard(StatutOT.EN_COURS, promis, promis) is False
    assert est_en_retard(StatutOT.EN_COURS, None, apres) is False


# --- Modification ---------------------------------------------------------------------------


def test_modification_des_champs_et_des_taches(
    client_gerant: TestClient, vehicule: Vehicule, mecanicien: Utilisateur
) -> None:
    ordre = _creer(client_gerant, vehicule)
    diagnostic, plaquettes, vidange = ordre["taches"]

    reponse = client_gerant.put(
        f"/ordres/{ordre['id']}",
        json={
            "demande_client": "Bruit au freinage.",
            "diagnostic": "Plaquettes avant usées.",
            "prioritaire": True,
            "restitution_prevue": "2026-11-02T17:30",
            "mecanicien_id": mecanicien.id,
            "taches": [
                {
                    "id": plaquettes["id"],
                    "libelle": "Plaquettes et disques",
                    "duree_prevue_minutes": 120,
                },
                {"libelle": "Essai routier", "duree_prevue_minutes": 15},
                {
                    "id": diagnostic["id"],
                    "libelle": diagnostic["libelle"],
                    "duree_prevue_minutes": 30,
                },
            ],
        },
    )

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["diagnostic"] == "Plaquettes avant usées."
    assert corps["prioritaire"] is True
    assert corps["restitution_prevue"] == "2026-11-02T16:30:00Z"
    assert corps["mecanicien"]["id"] == mecanicien.id
    assert [(t["libelle"], t["duree_prevue_minutes"], t["position"]) for t in corps["taches"]] == [
        ("Plaquettes et disques", 120, 0),
        ("Essai routier", 15, 1),
        ("Diagnostic bruit de freinage", 30, 2),
    ]
    assert corps["taches"][0]["id"] == plaquettes["id"]
    assert vidange["id"] not in [t["id"] for t in corps["taches"]]


def test_modification_sans_liste_de_taches_les_conserve(
    client_gerant: TestClient, vehicule: Vehicule
) -> None:
    ordre = _creer(client_gerant, vehicule)

    reponse = client_gerant.put(f"/ordres/{ordre['id']}", json={"demande_client": "Autre demande"})

    assert reponse.status_code == 200
    assert reponse.json()["taches_total"] == 3
    assert reponse.json()["mecanicien"] is None


def test_tache_d_un_autre_ordre_refusee(client_gerant: TestClient, vehicule: Vehicule) -> None:
    autre = _creer(client_gerant, vehicule)
    ordre = _creer(client_gerant, vehicule)
    etrangere = autre["taches"][0]

    reponse = client_gerant.put(
        f"/ordres/{ordre['id']}",
        json={
            "demande_client": "Bruit",
            "taches": [{"id": etrangere["id"], "libelle": "X", "duree_prevue_minutes": 10}],
        },
    )

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "taches.0.id": "Tâche introuvable pour cet ordre de travail."
    }


def test_ordre_livre_non_modifiable(
    client_gerant: TestClient, vehicule: Vehicule, db: Session
) -> None:
    ordre = _creer(client_gerant, vehicule)
    db.get_one(OrdreTravail, ordre["id"]).statut = StatutOT.LIVRE
    db.flush()

    reponse = client_gerant.put(f"/ordres/{ordre['id']}", json={"demande_client": "Autre"})

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "ordre_livre"


def test_ordre_pret_refuse_une_nouvelle_tache(
    client_gerant: TestClient, vehicule: Vehicule, db: Session
) -> None:
    ordre = _creer(client_gerant, vehicule, taches=[])
    db.get_one(OrdreTravail, ordre["id"]).statut = StatutOT.TERMINE
    db.flush()

    reponse = client_gerant.put(
        f"/ordres/{ordre['id']}",
        json={
            "demande_client": "Bruit",
            "taches": [{"libelle": "Essai", "duree_prevue_minutes": 10}],
        },
    )

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "ordre_pret"


# --- Accès ----------------------------------------------------------------------------------


def test_mecanicien_refuse_a_l_ouverture_et_a_la_modification(
    client_gerant: TestClient, client_mecanicien: TestClient, vehicule: Vehicule
) -> None:
    ordre = _creer(client_gerant, vehicule)

    assert client_mecanicien.post("/ordres", json=_ordre(vehicule)).status_code == 403
    assert client_mecanicien.post("/ordres", json={}).status_code == 403
    modification = client_mecanicien.put(f"/ordres/{ordre['id']}", json={"demande_client": "X"})
    assert modification.status_code == 403


def test_sans_session_401(client_anonyme: TestClient) -> None:
    assert client_anonyme.get("/ordres").status_code == 401
    assert client_anonyme.get("/ordres/1").status_code == 401
    assert client_anonyme.post("/ordres", json={}).status_code == 401
    assert client_anonyme.get("/mecaniciens").status_code == 401


def test_liste_des_mecaniciens_actifs(
    client_mecanicien: TestClient, mecanicien: Utilisateur, make_user: MakeUser
) -> None:
    make_user(Role.MECANICIEN, nom="Ancien", actif=False)
    make_user(Role.GERANT, nom="Autre gérant")
    lucas = make_user(Role.MECANICIEN, nom="Lucas R.")

    reponse = client_mecanicien.get("/mecaniciens")

    assert reponse.status_code == 200
    assert reponse.json() == [
        {"id": mecanicien.id, "nom": "Karim B."},
        {"id": lucas.id, "nom": "Lucas R."},
    ]


def test_liste_des_vehicules_groupes_par_proprietaire(
    client_gerant: TestClient, client_mecanicien: TestClient, vehicule: Vehicule, db: Session
) -> None:
    autre = Client(nom="Diallo", prenom="Moussa", telephone="0645716308")
    db.add(autre)
    db.flush()
    db.add(
        Vehicule(
            client_id=autre.id,
            immatriculation="FD-119-RT",
            marque="Renault",
            modele="Clio V",
            kilometrage=38900,
        )
    )
    db.flush()

    reponse = client_gerant.get("/vehicules")

    assert reponse.status_code == 200
    assert [(v["proprietaire"]["nom"], v["immatriculation"]) for v in reponse.json()] == [
        ("Diallo", "FD-119-RT"),
        ("Laurent", "GH-482-KL"),
    ]
    assert client_mecanicien.get("/vehicules").status_code == 200


# --- Base de données ------------------------------------------------------------------------


def test_la_base_refuse_un_ordre_sans_vehicule_et_une_tache_sans_duree(
    client_gerant: TestClient, vehicule: Vehicule, db: Session
) -> None:
    ordre = _creer(client_gerant, vehicule)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO ordre_travail (numero, demande_client, ouvert_le, cree_par)"
                " SELECT 'OT-2026-900', 'x', now(), cree_par FROM ordre_travail LIMIT 1"
            )
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO tache_ot (ordre_travail_id, libelle, duree_prevue_minutes)"
                " VALUES (:id, 'Vidange', 0)"
            ),
            {"id": ordre["id"]},
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text("UPDATE ordre_travail SET numero = 'OT-26-1' WHERE id = :id"), {"id": ordre["id"]}
        )
