"""Story S1.5 — recherche dans les listes : devis et factures, clients, véhicules, ordres de
travail (les employés sont couverts par la story S8.2).

Chaque liste filtre côté base sur `q` (2 à 100 caractères, 422 sinon), sans accents ni casse,
jokers LIKE pris à la lettre ; le total de la page reste juste. Le mécanicien ne cherche que
dans les listes qu'il voit déjà, et jamais par le téléphone ou l'e-mail d'un client."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Select, event, select, text
from sqlalchemy.orm import Session

from app.models import Client, OrdreTravail, StatutOT, Utilisateur, Vehicule
from app.services.clients import requete_liste_clients
from app.services.recherche import MESSAGE_TROP_COURT, MESSAGE_TROP_LONG, recherche_de_liste
from app.services.vehicules import requete_liste_vehicules
from tests.test_s4_1_devis import LIGNES_BACKLOG

VIN_CLAIRE = "VF3LBHZTEFS123456"


def _client(
    db: Session,
    nom: str,
    prenom: str | None,
    telephone: str,
    *vehicules: tuple[str, str, str],
    email: str | None = None,
) -> Client:
    client = Client(nom=nom, prenom=prenom, telephone=telephone, email=email)
    db.add(client)
    db.flush()
    for plaque, marque, modele in vehicules:
        db.add(
            Vehicule(
                client_id=client.id,
                immatriculation=plaque,
                marque=marque,
                modele=modele,
                kilometrage=84_312,
                vin=VIN_CLAIRE if plaque == "GH-482-KL" else None,
            )
        )
    db.flush()
    return client


def _ordre(
    db: Session,
    createur: Utilisateur,
    plaque: str,
    numero: str,
    demande: str,
    statut: StatutOT = StatutOT.A_FAIRE,
    mecanicien: Utilisateur | None = None,
) -> OrdreTravail:
    vehicule = db.scalars(select(Vehicule).where(Vehicule.immatriculation == plaque)).one()
    ordre = OrdreTravail(
        numero=numero,
        vehicule=vehicule,
        demande_client=demande,
        statut=statut,
        mecanicien=mecanicien,
        ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
        createur=createur,
    )
    db.add(ordre)
    db.flush()
    return ordre


@pytest.fixture
def parc(db: Session, gerant: Utilisateur, mecanicien: Utilisateur) -> dict[str, Any]:
    """Clients des maquettes (nom accentué, prénom composé), leurs véhicules et trois OT."""
    claire = _client(
        db,
        "Laurent",
        "Claire",
        "0612483075",
        ("GH-482-KL", "Peugeot", "308 SW"),
        email="claire.laurent@exemple.test",
    )
    helene = _client(db, "Lefèvre", "Hélène", "0478214455", ("FD-301-RT", "Renault", "Clio"))
    moussa = _client(
        db,
        "Diallo",
        "Moussa",
        "0645716308",
        ("AB-123-CD", "Citroën", "C3"),
        ("EF-456-GH", "Dacia", "Sandero"),
    )
    ordres = [
        _ordre(
            db,
            gerant,
            "GH-482-KL",
            "OT-2026-001",
            "Bruit au freinage côté avant gauche.",
            StatutOT.EN_COURS,
            mecanicien,
        ),
        _ordre(db, gerant, "FD-301-RT", "OT-2026-002", "Vidange et contrôle des pneus."),
        _ordre(db, gerant, "AB-123-CD", "OT-2026-003", "Révision des 60 000 km."),
    ]
    return {"claire": claire, "helene": helene, "moussa": moussa, "ordres": ordres}


def _lister(c: TestClient, chemin: str, **params: Any) -> dict[str, Any]:
    reponse = c.get(chemin, params=params)
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


def _clients(c: TestClient, q: str) -> list[str]:
    return [f"{e['prenom']} {e['nom']}" for e in _lister(c, "/clients", q=q)["elements"]]


def _plaques(c: TestClient, q: str) -> list[str]:
    return [e["immatriculation"] for e in _lister(c, "/vehicules", q=q)["elements"]]


def _numeros(c: TestClient, q: str, **params: Any) -> list[str]:
    return sorted(e["numero"] for e in _lister(c, "/ordres", q=q, **params)["elements"])


# --- Lecture du paramètre (fonction pure) ------------------------------------------------------


def test_parametre_absent_ou_blanc_sans_filtre() -> None:
    assert recherche_de_liste(None) is None
    assert recherche_de_liste("") is None
    assert recherche_de_liste("   ") is None
    assert recherche_de_liste("  Lefèvre ") == "Lefèvre"


# --- Clients ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "attendus"),
    [
        ("helene", ["Hélène Lefèvre"]),
        ("LEFEVRE", ["Hélène Lefèvre"]),
        ("lefèvre hél", ["Hélène Lefèvre"]),
        ("06 12 48", ["Claire Laurent"]),
        ("4830", ["Claire Laurent"]),
        ("+33 6 45 71", ["Moussa Diallo"]),
        ("gh482kl", ["Claire Laurent"]),
        ("EF-456", ["Moussa Diallo"]),
        ("456-gh", ["Moussa Diallo"]),
        ("claire.laurent@", ["Claire Laurent"]),
        ("@EXEMPLE.test", ["Claire Laurent"]),
        ("dupont", []),
    ],
)
def test_clients_par_nom_telephone_plaque_ou_email(
    client_gerant: TestClient, parc: dict[str, Any], saisie: str, attendus: list[str]
) -> None:
    assert _clients(client_gerant, saisie) == attendus


def test_clients_sans_recherche_tous_les_clients(
    client_gerant: TestClient, parc: dict[str, Any]
) -> None:
    corps = _lister(client_gerant, "/clients", q="  ")
    assert corps["total"] == 3


def test_clients_pagination_juste_avec_la_recherche(
    client_gerant: TestClient, db: Session, parc: dict[str, Any]
) -> None:
    for i in range(23):
        _client(db, f"Bernard{i:02d}", "Jean", f"07{i:08d}")
    page1 = _lister(client_gerant, "/clients", q="bernard", taille=10)
    page3 = _lister(client_gerant, "/clients", q="bernard", taille=10, page=3)
    assert page1["total"] == page3["total"] == 23
    assert len(page1["elements"]) == 10
    assert [e["nom"] for e in page3["elements"]] == ["Bernard20", "Bernard21", "Bernard22"]


def test_jokers_pris_a_la_lettre(client_gerant: TestClient, db: Session) -> None:
    _client(db, "Garage_50%", None, "0611111111")
    _client(db, "Garage X 50", None, "0622222222")
    assert [e["nom"] for e in _lister(client_gerant, "/clients", q="e_50%")["elements"]] == [
        "Garage_50%"
    ]
    # Pleine chasse : unaccent la ramène à « _ » et « % », toujours pris à la lettre.
    assert [e["nom"] for e in _lister(client_gerant, "/clients", q="e＿50％")["elements"]] == [
        "Garage_50%"
    ]
    assert _lister(client_gerant, "/clients", q="%%")["total"] == 0


@pytest.mark.parametrize("chemin", ["/clients", "/vehicules", "/ordres", "/devis", "/factures"])
@pytest.mark.parametrize(
    ("saisie", "message"),
    [("a", MESSAGE_TROP_COURT), (" b ", MESSAGE_TROP_COURT), ("x" * 101, MESSAGE_TROP_LONG)],
)
def test_saisie_trop_courte_ou_trop_longue_422(
    client_gerant: TestClient, chemin: str, saisie: str, message: str
) -> None:
    reponse = client_gerant.get(chemin, params={"q": saisie})
    assert reponse.status_code == 422, reponse.text
    assert reponse.json()["champs"] == {"q": message}


@pytest.mark.parametrize("chemin", ["/clients", "/ordres", "/vehicules"])
def test_caractere_de_controle_422(client_gerant: TestClient, chemin: str) -> None:
    reponse = client_gerant.get(chemin, params={"q": "Laur\x00ent"})
    assert reponse.status_code == 422
    assert "q" in reponse.json()["champs"]


def test_injection_sql_sans_effet(client_gerant: TestClient, parc: dict[str, Any]) -> None:
    for saisie in ("'; DROP TABLE client; --", "' OR '1'='1"):
        assert _clients(client_gerant, saisie) == []
        assert _plaques(client_gerant, saisie) == []
    assert _clients(client_gerant, "diallo") == ["Moussa Diallo"]


# --- Véhicules -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "attendues"),
    [
        ("gh482kl", ["GH-482-KL"]),
        ("GH-482-KL", ["GH-482-KL"]),
        ("301-r", ["FD-301-RT"]),
        ("citroen", ["AB-123-CD"]),
        ("clio", ["FD-301-RT"]),
        ("308 sw", ["GH-482-KL"]),
        ("fs1234", ["GH-482-KL"]),
        ("diallo", ["AB-123-CD", "EF-456-GH"]),
        ("hélène", ["FD-301-RT"]),
        ("LEFEVRE", ["FD-301-RT"]),
        ("dupont", []),
    ],
)
def test_vehicules_par_plaque_vehicule_vin_ou_proprietaire(
    client_gerant: TestClient, parc: dict[str, Any], saisie: str, attendues: list[str]
) -> None:
    assert _plaques(client_gerant, saisie) == attendues


def test_vehicules_jamais_par_les_coordonnees_du_proprietaire(
    client_gerant: TestClient, client_mecanicien: TestClient, parc: dict[str, Any]
) -> None:
    for c in (client_gerant, client_mecanicien):
        assert _plaques(c, "0612483075") == []
        assert _plaques(c, "06 12 48") == []
        assert _plaques(c, "claire.laurent@exemple.test") == []


def test_mecanicien_cherche_les_vehicules_sans_voir_les_coordonnees(
    client_mecanicien: TestClient, parc: dict[str, Any]
) -> None:
    corps = _lister(client_mecanicien, "/vehicules", q="laurent")
    assert corps["total"] == 1
    vehicule = corps["elements"][0]
    assert vehicule["immatriculation"] == "GH-482-KL"
    assert set(vehicule["proprietaire"]) == {"id", "nom", "prenom"}
    assert "0612483075" not in str(corps)
    assert "exemple.test" not in str(corps)


def test_vehicules_pagines_groupes_par_proprietaire(
    client_gerant: TestClient, parc: dict[str, Any]
) -> None:
    page1 = _lister(client_gerant, "/vehicules", taille=2)
    page2 = _lister(client_gerant, "/vehicules", taille=2, page=2)
    assert (page1["total"], page1["page"], page1["taille"]) == (4, 1, 2)
    assert [e["immatriculation"] for e in page1["elements"] + page2["elements"]] == [
        "AB-123-CD",
        "EF-456-GH",
        "GH-482-KL",
        "FD-301-RT",
    ]
    filtre = _lister(client_gerant, "/vehicules", q="diallo", taille=1, page=2)
    assert filtre["total"] == 2
    assert [e["immatriculation"] for e in filtre["elements"]] == ["EF-456-GH"]


def test_liste_de_choix_des_vehicules_en_une_grande_page(
    client_gerant: TestClient, parc: dict[str, Any]
) -> None:
    assert _lister(client_gerant, "/vehicules", taille=1000)["total"] == 4
    assert client_gerant.get("/vehicules", params={"taille": 1001}).status_code == 422


# --- Ordres de travail -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "attendus"),
    [
        ("OT-2026-002", ["OT-2026-002"]),
        ("ot-2026-00", ["OT-2026-001", "OT-2026-002", "OT-2026-003"]),
        ("gh482kl", ["OT-2026-001"]),
        ("GH-482", ["OT-2026-001"]),
        ("peugeot 308", ["OT-2026-001"]),
        ("citroen", ["OT-2026-003"]),
        ("helene", ["OT-2026-002"]),
        ("moussa diallo", ["OT-2026-003"]),
        ("karim", ["OT-2026-001"]),
        ("revision", ["OT-2026-003"]),
        ("CONTROLE pneus", ["OT-2026-002"]),
        ("dupont", []),
    ],
)
def test_ordres_par_numero_plaque_vehicule_client_mecanicien_ou_demande(
    client_gerant: TestClient, parc: dict[str, Any], saisie: str, attendus: list[str]
) -> None:
    assert _numeros(client_gerant, saisie) == attendus


def test_ordres_recherche_et_statut_combines(
    client_gerant: TestClient, parc: dict[str, Any]
) -> None:
    corps = _lister(client_gerant, "/ordres", q="OT-2026", statut="a_faire")
    assert corps["total"] == 2
    assert sorted(e["numero"] for e in corps["elements"]) == ["OT-2026-002", "OT-2026-003"]
    assert _numeros(client_gerant, "karim", statut="a_faire") == []


def test_mecanicien_cherche_les_ordres_sans_les_coordonnees_du_client(
    client_mecanicien: TestClient, parc: dict[str, Any]
) -> None:
    assert _numeros(client_mecanicien, "laurent") == ["OT-2026-001"]
    assert _numeros(client_mecanicien, "0612483075") == []
    assert _numeros(client_mecanicien, "06 12 48") == []
    assert _numeros(client_mecanicien, "claire.laurent@exemple.test") == []


def test_ordres_pagination_juste_avec_la_recherche(
    client_gerant: TestClient, db: Session, gerant: Utilisateur, parc: dict[str, Any]
) -> None:
    for i in range(5):
        _ordre(db, gerant, "EF-456-GH", f"OT-2026-1{i:02d}", "Pneus hiver.")
    page = _lister(client_gerant, "/ordres", q="pneus hiver", taille=2, page=3)
    assert page["total"] == 5
    assert len(page["elements"]) == 1


# --- Devis et factures -----------------------------------------------------------------------


@pytest.fixture
def facturation(
    client_gerant: TestClient,
    db: Session,
    gerant: Utilisateur,
    parc: dict[str, Any],
) -> dict[str, Any]:
    """Un devis accepté et facturé (Claire Laurent, GH-482-KL), un devis brouillon (Hélène
    Lefèvre, FD-301-RT)."""
    termine = _ordre(db, gerant, "GH-482-KL", "OT-2026-010", "Plaquettes avant.", StatutOT.TERMINE)
    brouillon = _ordre(db, gerant, "FD-301-RT", "OT-2026-011", "Courroie.", StatutOT.TERMINE)
    devis = client_gerant.post(f"/ordres/{termine.id}/devis", json={"lignes": LIGNES_BACKLOG})
    assert devis.status_code == 201, devis.text
    for nouveau in ("envoye", "accepte"):
        reponse = client_gerant.post(
            f"/devis/{devis.json()['id']}/statut", json={"nouveau": nouveau}
        )
        assert reponse.status_code == 200, reponse.text
    facture = client_gerant.post(f"/devis/{devis.json()['id']}/facture")
    assert facture.status_code == 201, facture.text
    autre = client_gerant.post(f"/ordres/{brouillon.id}/devis", json={"lignes": LIGNES_BACKLOG})
    assert autre.status_code == 201, autre.text
    return {"facture": facture.json(), "devis": devis.json(), "brouillon": autre.json()}


def _ordres_des_devis(c: TestClient, q: str) -> list[str]:
    return sorted(e["ordre"]["numero"] for e in _lister(c, "/devis", q=q)["elements"])


@pytest.mark.parametrize(
    ("saisie", "attendus"),
    [
        ("OT-2026-011", ["OT-2026-011"]),
        ("ot-2026-01", ["OT-2026-010", "OT-2026-011"]),
        ("gh482kl", ["OT-2026-010"]),
        ("FD-301", ["OT-2026-011"]),
        ("lefevre", ["OT-2026-011"]),
        ("CLAIRE laurent", ["OT-2026-010"]),
        ("0612483075", []),
        ("dupont", []),
    ],
)
def test_devis_par_numero_d_ot_plaque_ou_client(
    client_gerant: TestClient, facturation: dict[str, Any], saisie: str, attendus: list[str]
) -> None:
    assert _ordres_des_devis(client_gerant, saisie) == attendus


def test_devis_total_juste_avec_la_recherche(
    client_gerant: TestClient, facturation: dict[str, Any]
) -> None:
    corps = _lister(client_gerant, "/devis", q="hélène", taille=1)
    assert corps["total"] == 1
    assert _lister(client_gerant, "/devis", taille=1)["total"] == 2


def _numeros_factures(c: TestClient, q: str, **params: Any) -> list[str]:
    return [e["numero"] for e in _lister(c, "/factures", q=q, **params)["elements"]]


def test_factures_par_numero_ordre_client_ou_plaque_figes(
    client_gerant: TestClient, db: Session, facturation: dict[str, Any]
) -> None:
    numero = facturation["facture"]["numero"]
    for saisie in (numero, numero.lower(), "OT-2026-010", "laurent", "CLAIRE", "gh482kl"):
        assert _numeros_factures(client_gerant, saisie) == [numero], saisie
    for saisie in ("OT-2026-011", "lefevre", "FD-301-RT", "0612483075"):
        assert _numeros_factures(client_gerant, saisie) == [], saisie


def test_factures_cherchees_par_la_copie_figee(
    client_gerant: TestClient, db: Session, parc: dict[str, Any], facturation: dict[str, Any]
) -> None:
    """La fiche client modifiée après l'émission ne change pas ce que l'on trouve."""
    claire: Client = parc["claire"]
    claire.nom = "Martin"
    db.flush()
    numero = facturation["facture"]["numero"]
    assert _numeros_factures(client_gerant, "laurent") == [numero]
    assert _numeros_factures(client_gerant, "martin") == []


def test_factures_recherche_et_statut_de_paiement_combines(
    client_gerant: TestClient, facturation: dict[str, Any]
) -> None:
    numero = facturation["facture"]["numero"]
    assert _numeros_factures(client_gerant, "laurent", statut_paiement="impayee") == [numero]
    assert _numeros_factures(client_gerant, "laurent", statut_paiement="payee") == []


# --- Droits ----------------------------------------------------------------------------------


@pytest.mark.parametrize("chemin", ["/clients", "/devis", "/factures"])
def test_mecanicien_refuse_sur_les_listes_du_gerant_403(
    client_mecanicien: TestClient, chemin: str
) -> None:
    assert client_mecanicien.get(chemin, params={"q": "laurent"}).status_code == 403


@pytest.mark.parametrize("chemin", ["/clients", "/vehicules", "/ordres", "/devis", "/factures"])
def test_sans_session_401(client_anonyme: TestClient, chemin: str) -> None:
    assert client_anonyme.get(chemin, params={"q": "laurent"}).status_code == 401


# --- Performance : index et nombre de requêtes -------------------------------------------------


def _plan(db: Session, requete: Select[Any]) -> str:
    """Plan de la requête, parcours séquentiels découragés : s'il reste un « Seq Scan », aucun
    plan par index n'existe pour cette partie de la requête."""
    compilee = requete.compile(dialect=db.get_bind().dialect)
    db.execute(text("SET LOCAL enable_seqscan = off"))
    lignes = db.connection().exec_driver_sql(f"EXPLAIN {compilee}", dict(compilee.params))
    return "\n".join(str(ligne[0]) for ligne in lignes)


@pytest.mark.parametrize(
    ("saisie", "index"),
    [
        ("laurent", "ix_client_nom_prenom_trgm"),
        ("06 12 48", "ix_client_telephone_trgm"),
        ("gh482kl", "ix_vehicule_immatriculation_trgm"),
    ],
)
def test_liste_des_clients_par_les_index_trigrammes(
    db: Session, parc: dict[str, Any], saisie: str, index: str
) -> None:
    plan = _plan(db, requete_liste_clients(saisie))
    assert "Seq Scan on client" not in plan, plan
    assert index in plan, plan
    assert "ix_client_nom_prenom_trgm" in plan, plan


@pytest.mark.parametrize("saisie", ["laurent", "gh482kl"])
def test_liste_des_vehicules_par_les_index_trigrammes(
    db: Session, parc: dict[str, Any], saisie: str
) -> None:
    """Propriétaire par l'index de son nom, plaque par celui de la plaque compacte. Marque,
    modèle et VIN n'ont pas d'index (texte court, une table de quelques milliers de lignes)."""
    plan = _plan(db, requete_liste_vehicules(saisie))
    assert "Seq Scan on client" not in plan, plan
    assert "ix_client_nom_prenom_trgm" in plan, plan
    if saisie == "gh482kl":
        assert "ix_vehicule_immatriculation_trgm" in plan, plan


@contextmanager
def _compter_requetes(db: Session) -> Iterator[list[str]]:
    requetes: list[str] = []

    def _noter(*args: Any) -> None:
        requetes.append(str(args[2]))

    connexion = db.connection()
    event.listen(connexion, "before_cursor_execute", _noter)
    try:
        yield requetes
    finally:
        event.remove(connexion, "before_cursor_execute", _noter)


@pytest.mark.parametrize(("chemin", "saisie"), [("/vehicules", "petit"), ("/clients", "petit")])
def test_nombre_de_requetes_independant_du_nombre_de_resultats(
    client_gerant: TestClient, db: Session, chemin: str, saisie: str
) -> None:
    _client(db, "Petit", "Ana", "0611111111", ("AB-101-CD", "Renault", "Kangoo"))
    with _compter_requetes(db) as peu:
        assert _lister(client_gerant, chemin, q=saisie)["total"] == 1
    for i in range(8):
        _client(db, f"Petit{i}", "Ana", f"07{i:08d}", (f"AB-2{i}0-CD", "Renault", "Kangoo"))
    with _compter_requetes(db) as beaucoup:
        assert _lister(client_gerant, chemin, q=saisie)["total"] == 9
    assert len(beaucoup) == len(peu)
