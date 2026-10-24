"""Story S2.1 — rendez-vous : date passée, chevauchement par pont, planning du jour à Paris."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Client, OrdreTravail, Pont, RendezVous, StatutOT, Utilisateur, Vehicule
from app.services import rendez_vous as service
from tests.conftest import Horloge

NBSP = " "


@pytest.fixture(autouse=True)
def _horloge_d_abord(horloge: Horloge) -> Horloge:
    """Lundi 2 novembre 2026, 14 h 47 à Paris ; posée avant toute connexion."""
    return horloge


@pytest.fixture
def ponts(db: Session) -> dict[str, Pont]:
    return {p.nom: p for p in db.scalars(select(Pont))}


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


def _rdv(
    vehicule: Vehicule, pont: Pont, debut: str, duree: int = 90, **autres: Any
) -> dict[str, Any]:
    corps: dict[str, Any] = {
        "vehicule_id": vehicule.id,
        "pont_id": pont.id,
        "debut": debut,
        "duree_minutes": duree,
        "motif": "Remplacement des plaquettes avant",
    }
    corps.update(autres)
    return corps


def _prendre(c: TestClient, vehicule: Vehicule, pont: Pont, debut: str, duree: int = 90) -> Any:
    return c.post("/rendez-vous", json=_rdv(vehicule, pont, debut, duree))


# --- Prise de rendez-vous -------------------------------------------------------------------


def test_prise_de_rendez_vous(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont]
) -> None:
    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00")

    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    # 9 h 00 à Paris = 8 h 00 UTC ; fin calculée par la base.
    assert corps["debut"] == "2026-11-03T08:00:00Z"
    assert corps["fin"] == "2026-11-03T09:30:00Z"
    assert corps["duree_minutes"] == 90
    assert corps["pont"] == {"id": ponts["Pont 1"].id, "nom": "Pont 1"}
    assert corps["vehicule"]["immatriculation"] == "GH-482-KL"
    assert corps["client"] == {
        "id": vehicule.client_id,
        "nom": "Laurent",
        "prenom": "Claire",
        "contact": None,
    }
    assert corps["ordre"] is None


def test_debut_avec_fuseau_accepte(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont]
) -> None:
    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00:00+01:00")

    assert reponse.json()["debut"] == "2026-11-03T08:00:00Z"


@pytest.mark.parametrize("debut", ["2026-11-02T14:46", "2026-11-01T10:00", "2026-11-02T13:46:59Z"])
def test_date_passee_refusee(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont], debut: str
) -> None:
    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], debut)

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "debut": "Impossible de prendre un rendez-vous dans le passé."
    }


def test_maintenant_exactement_accepte(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont]
) -> None:
    assert _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-02T14:47").status_code == 201


@pytest.mark.parametrize(
    ("debut", "duree"),
    [
        ("2026-11-03T09:30", 60),  # chevauchement partiel (fin)
        ("2026-11-03T08:30", 60),  # chevauchement partiel (début)
        ("2026-11-03T09:15", 30),  # contenu
        ("2026-11-03T08:30", 180),  # englobant
        ("2026-11-03T09:00", 90),  # identique
    ],
)
def test_chevauchement_sur_le_meme_pont_refuse(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont], debut: str, duree: int
) -> None:
    premier = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00").json()

    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], debut, duree)

    assert reponse.status_code == 409
    assert reponse.json() == {
        "code": "creneau_occupe",
        "message": f"Le Pont 1 est déjà occupé de 9{NBSP}h{NBSP}00 à 10{NBSP}h{NBSP}30.",
        "champs": {},
        "rendez_vous_id": premier["id"],
    }


@pytest.mark.parametrize(("debut", "duree"), [("2026-11-03T10:30", 30), ("2026-11-03T08:00", 60)])
def test_creneaux_adjacents_acceptes(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont], debut: str, duree: int
) -> None:
    _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00")

    assert _prendre(client_gerant, vehicule, ponts["Pont 1"], debut, duree).status_code == 201


def test_autre_pont_accepte(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont]
) -> None:
    _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00")

    assert _prendre(client_gerant, vehicule, ponts["Pont 2"], "2026-11-03T09:00").status_code == 201


def test_prise_simultanee_arretee_par_la_contrainte_de_la_base(
    client_gerant: TestClient,
    vehicule: Vehicule,
    ponts: dict[str, Pont],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    premier = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00").json()
    verification = service.creneau_en_conflit
    appels: list[int] = []

    def verification_trop_tot(*args: Any) -> RendezVous | None:
        # Simule une requête concurrente : la vérification du service ne voit rien encore.
        appels.append(1)
        return None if len(appels) == 1 else verification(*args)

    monkeypatch.setattr(service, "creneau_en_conflit", verification_trop_tot)

    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T10:00", 60)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "creneau_occupe"
    assert reponse.json()["rendez_vous_id"] == premier["id"]
    assert db.scalar(select(func.count()).select_from(RendezVous)) == 1
    # La transaction reste utilisable après le refus (point de sauvegarde annulé seul).
    assert (
        _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T10:30", 30).status_code
        == 201
    )


@pytest.mark.parametrize(
    ("duree", "message"),
    [
        (0, "Doit être supérieur ou égal à 1."),
        (601, "Doit être inférieur ou égal à 600."),
        ("30", "Nombre entier attendu."),
        (None, "Nombre entier attendu."),
    ],
)
def test_bornes_de_la_duree(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont], duree: Any, message: str
) -> None:
    reponse = client_gerant.post(
        "/rendez-vous", json=_rdv(vehicule, ponts["Pont 1"], "2026-11-03T09:00", duree)
    )

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"duree_minutes": message}


def test_duree_maximale_de_dix_heures(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont]
) -> None:
    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T07:00", 600)

    assert reponse.status_code == 201
    assert reponse.json()["fin"] == "2026-11-03T16:00:00Z"


def test_champs_obligatoires(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/rendez-vous", json={"motif": "  "})

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "vehicule_id": "Champ obligatoire.",
        "pont_id": "Champ obligatoire.",
        "debut": "Champ obligatoire.",
        "duree_minutes": "Champ obligatoire.",
        "motif": "Champ obligatoire.",
    }


def test_vehicule_inconnu_et_pont_invalide(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont], db: Session
) -> None:
    inconnu = client_gerant.post(
        "/rendez-vous", json=_rdv(vehicule, ponts["Pont 1"], "2026-11-03T09:00", vehicule_id=999999)
    )
    assert inconnu.status_code == 404
    assert inconnu.json()["champs"] == {"vehicule_id": "Véhicule introuvable."}

    ponts["Pont 3"].actif = False
    db.flush()
    for pont_id in (ponts["Pont 3"].id, 999999):
        reponse = client_gerant.post(
            "/rendez-vous",
            json=_rdv(vehicule, ponts["Pont 1"], "2026-11-03T09:00", pont_id=pont_id),
        )
        assert reponse.status_code == 422
        assert reponse.json()["champs"] == {"pont_id": "Choisissez un pont de l'atelier."}
    assert [p["nom"] for p in client_gerant.get("/ponts").json()] == ["Pont 1", "Pont 2"]


# --- Liste ----------------------------------------------------------------------------------


def test_liste_triee_par_date_et_filtree(
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    vehicule: Vehicule,
    ponts: dict[str, Pont],
    gerant: Utilisateur,
    db: Session,
) -> None:
    # Un rendez-vous d'hier (écrit directement : l'API refuse le passé).
    db.add(
        RendezVous(
            vehicule_id=vehicule.id,
            pont_id=ponts["Pont 1"].id,
            debut=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
            duree_minutes=60,
            motif="Hier",
            cree_par=gerant.id,
        )
    )
    db.flush()
    _prendre(client_gerant, vehicule, ponts["Pont 2"], "2026-11-04T08:00")
    _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T14:00")
    _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-03T09:00")

    def debuts(requete: str = "", c: TestClient = client_gerant) -> list[str]:
        reponse = c.get(f"/rendez-vous{requete}")
        assert reponse.status_code == 200, reponse.text
        return [r["debut"] for r in reponse.json()]

    assert debuts() == ["2026-11-03T08:00:00Z", "2026-11-03T13:00:00Z", "2026-11-04T07:00:00Z"]
    assert debuts(c=client_mecanicien) == debuts()
    assert debuts(f"?pont_id={ponts['Pont 2'].id}") == ["2026-11-04T07:00:00Z"]
    assert debuts("?du=2026-11-01&au=2026-11-01") == ["2026-11-01T09:00:00Z"]
    assert debuts("?au=2026-11-03") == ["2026-11-03T08:00:00Z", "2026-11-03T13:00:00Z"]
    assert client_gerant.get("/rendez-vous?du=2026-11-05&au=2026-11-04").status_code == 422


# --- Ouverture d'un OT ----------------------------------------------------------------------


def test_ouvrir_l_ordre_de_travail_d_un_rendez_vous(
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    vehicule: Vehicule,
    ponts: dict[str, Pont],
) -> None:
    rdv = _prendre(client_gerant, vehicule, ponts["Pont 2"], "2026-11-03T09:00").json()

    assert client_mecanicien.post(f"/rendez-vous/{rdv['id']}/ordre").status_code == 403
    reponse = client_gerant.post(f"/rendez-vous/{rdv['id']}/ordre")

    assert reponse.status_code == 201, reponse.text
    ordre = reponse.json()
    assert ordre["numero"] == "OT-2026-001"
    assert ordre["vehicule"]["id"] == vehicule.id
    assert ordre["demande_client"] == "Remplacement des plaquettes avant"
    assert ordre["rendez_vous"]["id"] == rdv["id"]
    assert ordre["rendez_vous"]["pont"]["nom"] == "Pont 2"
    assert len(ordre["historique"]) == 1
    liste = client_gerant.get("/rendez-vous").json()
    assert liste[0]["ordre"] == {"id": ordre["id"], "numero": "OT-2026-001", "statut": "a_faire"}

    deuxieme = client_gerant.post(f"/rendez-vous/{rdv['id']}/ordre")
    assert deuxieme.status_code == 409
    assert deuxieme.json()["code"] == "ordre_existant"
    assert deuxieme.json()["ordre_id"] == ordre["id"]
    assert client_gerant.post("/rendez-vous/999999/ordre").status_code == 404


# --- Planning -------------------------------------------------------------------------------


def test_planning_groupe_par_pont_et_par_jour_de_paris(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    vehicule: Vehicule,
    ponts: dict[str, Pont],
    db: Session,
) -> None:
    # Jeudi 5 novembre : 23 h 30 à Paris (22 h 30 UTC) appartient au 5 ; 0 h 30 le 6
    # (23 h 30 UTC le 5) appartient au 6.
    tard = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-05T23:30", 30).json()
    lendemain = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-06T00:30", 30).json()
    matin = _prendre(client_gerant, vehicule, ponts["Pont 1"], "2026-11-05T08:00", 150).json()
    pont2 = _prendre(client_gerant, vehicule, ponts["Pont 2"], "2026-11-05T10:00", 240).json()
    ordre = client_gerant.post(f"/rendez-vous/{matin['id']}/ordre").json()
    sans_rdv = client_gerant.post(
        "/ordres", json={"vehicule_id": vehicule.id, "demande_client": "Pneus"}
    ).json()
    livre = client_gerant.post(
        "/ordres", json={"vehicule_id": vehicule.id, "demande_client": "Vidange"}
    ).json()
    db.get_one(OrdreTravail, livre["id"]).statut = StatutOT.LIVRE
    db.get_one(OrdreTravail, livre["id"]).cloture_le = horloge.maintenant
    db.flush()

    reponse = client_mecanicien.get("/planning?jour=2026-11-05")

    assert reponse.status_code == 200, reponse.text
    planning = reponse.json()
    assert planning["jour"] == "2026-11-05"
    assert [p["nom"] for p in planning["ponts"]] == ["Pont 1", "Pont 2", "Pont 3"]
    p1, p2, p3 = planning["ponts"]
    assert [(e["type"], e["rendez_vous"]["id"]) for e in p1["elements"]] == [
        ("ordre", matin["id"]),
        ("rendez_vous", tard["id"]),
    ]
    assert p1["elements"][0]["heure"] == "2026-11-05T07:00:00Z"
    assert p1["elements"][0]["ordre"]["numero"] == ordre["numero"]
    assert p1["elements"][0]["ordre"]["client"]["contact"] is None
    assert p1["elements"][1]["ordre"] is None
    assert (p1["charge_minutes"], p1["capacite_minutes"]) == (180, 480)
    assert [e["rendez_vous"]["id"] for e in p2["elements"]] == [pont2["id"]]
    assert p2["charge_minutes"] == 240
    assert (p3["elements"], p3["charge_minutes"]) == ([], 0)
    assert [o["id"] for o in planning["a_planifier"]] == [sans_rdv["id"]]

    suivant = client_gerant.get("/planning?jour=2026-11-06").json()
    # L'OT du matin, non livré, reste sur son pont le lendemain (report), avant le créneau.
    assert [(e["rendez_vous"]["id"], e["report"]) for e in suivant["ponts"][0]["elements"]] == [
        (matin["id"], True),
        (lendemain["id"], False),
    ]
    # Sans jour : aujourd'hui à Paris (lundi 2 novembre).
    assert client_gerant.get("/planning").json()["jour"] == "2026-11-02"
    assert client_gerant.get("/planning?jour=2026-13-01").status_code == 422


def test_planning_reporte_un_ot_non_livre_dont_le_rendez_vous_est_passe(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    vehicule: Vehicule,
    ponts: dict[str, Pont],
    db: Session,
) -> None:
    # Rendez-vous le mardi 3 novembre ; l'OT est encore en cours le mercredi 4 et le jeudi 5.
    rdv = _prendre(client_gerant, vehicule, ponts["Pont 2"], "2026-11-03T09:00", 60).json()
    ordre = client_gerant.post(f"/rendez-vous/{rdv['id']}/ordre").json()
    maj = client_gerant.put(
        f"/ordres/{ordre['id']}",
        json={
            "demande_client": "Embrayage",
            "taches": [
                {"libelle": "Diagnostic", "duree_prevue_minutes": 30},
                {"libelle": "Remplacement embrayage", "duree_prevue_minutes": 240},
            ],
        },
    ).json()
    assert client_gerant.post(f"/ordres/{ordre['id']}/statut", json={"nouveau": "en_cours"})
    terminee = client_gerant.post(f"/ordres/{ordre['id']}/taches/{maj['taches'][0]['id']}/terminer")
    assert terminee.status_code == 200
    matin = _prendre(client_gerant, vehicule, ponts["Pont 2"], "2026-11-04T08:00", 90).json()

    jour_du_rdv = client_gerant.get("/planning?jour=2026-11-03").json()["ponts"][1]
    assert [(e["rendez_vous"]["id"], e["report"]) for e in jour_du_rdv["elements"]] == [
        (rdv["id"], False)
    ]

    lendemain = client_mecanicien.get("/planning?jour=2026-11-04").json()
    pont2 = lendemain["ponts"][1]
    # Le report vient d'abord (à minuit, heure de Paris), puis les rendez-vous du jour.
    assert [(e["type"], e["rendez_vous"]["id"], e["report"]) for e in pont2["elements"]] == [
        ("ordre", rdv["id"], True),
        ("rendez_vous", matin["id"], False),
    ]
    assert pont2["elements"][0]["heure"] == "2026-11-03T23:00:00Z"
    assert pont2["elements"][0]["ordre"]["statut"] == "en_cours"
    assert pont2["elements"][0]["ordre"]["client"]["contact"] is None
    # Charge : 240 min de tâches restantes + 90 min de rendez-vous.
    assert pont2["charge_minutes"] == 330
    assert lendemain["a_planifier"] == []
    surlendemain = client_gerant.get("/planning?jour=2026-11-05").json()["ponts"][1]
    assert [e["rendez_vous"]["id"] for e in surlendemain["elements"]] == [rdv["id"]]
    # Avant le rendez-vous, rien n'est reporté.
    assert client_gerant.get("/planning?jour=2026-11-02").json()["ponts"][1]["elements"] == []

    livre = db.get_one(OrdreTravail, ordre["id"])
    livre.statut = StatutOT.LIVRE
    livre.cloture_le = horloge.maintenant
    db.flush()
    pont2 = client_gerant.get("/planning?jour=2026-11-04").json()["ponts"][1]
    assert [e["rendez_vous"]["id"] for e in pont2["elements"]] == [matin["id"]]
    assert pont2["charge_minutes"] == 90


def test_planning_et_ponts_lisibles_sans_session_refuses(client_anonyme: TestClient) -> None:
    assert client_anonyme.get("/planning").status_code == 401
    assert client_anonyme.get("/ponts").status_code == 401
    assert client_anonyme.get("/rendez-vous").status_code == 401


def test_mecanicien_refuse_a_la_prise_de_rendez_vous(
    client_mecanicien: TestClient, vehicule: Vehicule, ponts: dict[str, Pont]
) -> None:
    reponse = _prendre(client_mecanicien, vehicule, ponts["Pont 1"], "2026-11-03T09:00")

    assert reponse.status_code == 403


# --- Dates hors limites (revue du sprint 2) ------------------------------------------------


@pytest.mark.parametrize(
    ("url", "champ"),
    [
        ("/ordres?au=9999-12-31", "au"),
        ("/ordres?du=0001-01-01", "du"),
        ("/planning?jour=9999-12-31", "jour"),
        ("/rendez-vous?au=9999-12-31", "au"),
        ("/rendez-vous?du=0001-01-01", "du"),
        ("/ordres?du=1999-12-31", "du"),
        ("/planning?jour=2101-01-01", "jour"),
    ],
)
def test_jour_hors_limites_refuse_en_422(
    client_mecanicien: TestClient, url: str, champ: str
) -> None:
    reponse = client_mecanicien.get(url)

    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["champs"] == {champ: "Date hors limites."}


def test_jours_aux_limites_acceptes(client_gerant: TestClient) -> None:
    assert client_gerant.get("/ordres?du=2000-01-01&au=2100-12-31").status_code == 200
    assert client_gerant.get("/planning?jour=2100-12-31").status_code == 200
    assert client_gerant.get("/rendez-vous?du=2000-01-01&au=2100-12-31").status_code == 200


@pytest.mark.parametrize(
    "debut", ["9999-12-31T20:00:00Z", "0001-01-01T00:30", "0001-01-01T00:30:00+05:00"]
)
def test_rendez_vous_hors_limites_refuse_en_422(
    client_gerant: TestClient, vehicule: Vehicule, ponts: dict[str, Pont], debut: str
) -> None:
    reponse = _prendre(client_gerant, vehicule, ponts["Pont 1"], debut, 600)

    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["champs"] == {"debut": "Date hors limites."}


def test_restitution_hors_limites_refusee_en_422(
    client_gerant: TestClient, vehicule: Vehicule
) -> None:
    reponse = client_gerant.post(
        "/ordres",
        json={
            "vehicule_id": vehicule.id,
            "demande_client": "Pneus",
            "restitution_prevue": "0001-01-01T00:30",
        },
    )

    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["champs"] == {"restitution_prevue": "Date hors limites."}


# --- Base de données ------------------------------------------------------------------------


def test_la_base_calcule_la_fin_et_refuse_un_chevauchement(
    vehicule: Vehicule, ponts: dict[str, Pont], gerant: Utilisateur, db: Session
) -> None:
    def inserer(debut: datetime, duree: int, pont: Pont) -> None:
        db.execute(
            text(
                "INSERT INTO rendez_vous"
                " (vehicule_id, pont_id, debut, duree_minutes, motif, cree_par)"
                " VALUES (:v, :p, :d, :m, 'Test', :u)"
            ),
            {"v": vehicule.id, "p": pont.id, "d": debut, "m": duree, "u": gerant.id},
        )

    neuf_heures = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
    inserer(neuf_heures, 90, ponts["Pont 1"])
    fin = db.scalar(select(RendezVous.fin).where(RendezVous.debut == neuf_heures))
    assert fin == neuf_heures + timedelta(minutes=90)

    with pytest.raises(IntegrityError, match="excl_rendez_vous_pont_creneau"), db.begin_nested():
        inserer(neuf_heures + timedelta(minutes=89), 30, ponts["Pont 1"])
    with pytest.raises(IntegrityError, match="duree_bornee"), db.begin_nested():
        inserer(neuf_heures + timedelta(days=1), 601, ponts["Pont 1"])
    inserer(neuf_heures + timedelta(minutes=90), 30, ponts["Pont 1"])
    inserer(neuf_heures, 90, ponts["Pont 2"])
