"""Story S4.1 — devis : calcul en centimes sans erreur d'arrondi, quantités, accès du gérant."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.models import Client, Devis, OrdreTravail, Role, TypeLigne, Utilisateur, Vehicule
from app.routers import devis as routes_devis
from app.schemas.devis import DevisEntree
from app.services import calcul_devis
from app.services import devis as service_devis
from app.services.calcul_devis import lire_quantite, total_ligne, totaux, tva
from tests.conftest import Horloge
from tests.test_concurrence_ordres import en_parallele, nouvelle_session

# Lignes de la maquette « détail d'un OR » : 454,80 € TTC.
LIGNES_MAQUETTE: list[dict[str, Any]] = [
    {"type": "main_oeuvre", "reference": "MO-DIAG", "designation": "Diagnostic freinage",
     "quantite": "0.5", "prix_unitaire_ht_centimes": 7200},
    {"type": "main_oeuvre", "reference": "MO-FREIN-AV",
     "designation": "Remplacement plaquettes + disques AV", "quantite": "1,5",
     "prix_unitaire_ht_centimes": 7200},
    {"type": "main_oeuvre", "reference": "MO-VIDANGE", "designation": "Vidange + filtre",
     "quantite": "0,5", "prix_unitaire_ht_centimes": 7200},
    {"type": "piece", "reference": "PLQ-308-AV", "designation": "Jeu de plaquettes avant",
     "quantite": 1, "prix_unitaire_ht_centimes": 4850},
    {"type": "piece", "reference": "DSQ-308-283", "designation": "Disques avant ventilés (paire)",
     "quantite": "1", "prix_unitaire_ht_centimes": 9600},
    {"type": "piece", "reference": "HUI-5W30-5L", "designation": "Huile moteur 5W30, bidon 5 L",
     "quantite": "1", "prix_unitaire_ht_centimes": 4290},
    {"type": "piece", "reference": "FLT-H-12PT", "designation": "Filtre à huile 1.2 PureTech",
     "quantite": "1", "prix_unitaire_ht_centimes": 1160},
]  # fmt: skip

# Exemple du backlog : 2 pièces à 40 € + 1 h à 60 € = 168,00 € TTC.
LIGNES_BACKLOG: list[dict[str, Any]] = [
    {"type": "piece", "designation": "Pièce", "quantite": "2", "prix_unitaire_ht_centimes": 4000},
    {"type": "main_oeuvre", "designation": "Main-d'œuvre", "quantite": "1",
     "prix_unitaire_ht_centimes": 6000},
]  # fmt: skip


@dataclass(frozen=True)
class Ligne:
    type: TypeLigne
    quantite: Decimal
    prix_unitaire_ht_centimes: int


def _lignes(donnees: list[dict[str, Any]]) -> list[Ligne]:
    return [
        Ligne(TypeLigne(d["type"]), lire_quantite(d["quantite"]), d["prix_unitaire_ht_centimes"])
        for d in donnees
    ]


# --- Calcul (fonctions pures) ---------------------------------------------------------------


def test_exemple_du_backlog_168_euros_ttc() -> None:
    resultat = totaux(_lignes(LIGNES_BACKLOG), 2000)

    assert resultat.total_ht_centimes == 14_000
    assert resultat.total_tva_centimes == 2_800
    assert resultat.total_ttc_centimes == 16_800
    assert (resultat.pieces_ht_centimes, resultat.main_oeuvre_ht_centimes) == (8_000, 6_000)


def test_exemple_de_la_maquette_454_80_euros_ttc() -> None:
    resultat = totaux(_lignes(LIGNES_MAQUETTE), 2000)

    assert resultat.main_oeuvre_ht_centimes == 18_000
    assert resultat.pieces_ht_centimes == 19_900
    assert resultat.total_ht_centimes == 37_900
    assert resultat.total_tva_centimes == 7_580
    assert resultat.total_ttc_centimes == 45_480


@pytest.mark.parametrize(
    ("quantite", "prix", "attendu"),
    [
        ("0.5", 7_200, 3_600),  # 0,5 h × 72,00 € = 36,00 €
        ("1.25", 999, 1_249),  # 12,4875 € → 12,49 €
        ("0.33", 1_001, 330),  # 3,3033 € → 3,30 €
        ("0.5", 1, 1),  # 0,005 € : le demi-centime monte
        ("1.5", 1, 2),  # 0,015 € → 0,02 €
        ("0.01", 49, 0),  # 0,0049 € → 0,00 €
        ("9999.99", 10_000_000, 99_999_900_000),
    ],
)
def test_arrondi_d_une_ligne_au_centime_superieur_a_partir_du_demi(
    quantite: str, prix: int, attendu: int
) -> None:
    assert total_ligne(Decimal(quantite), prix) == attendu


@pytest.mark.parametrize(
    ("ht", "attendu"), [(5, 1), (12, 2), (13, 3), (14_000, 2_800), (37_900, 7_580), (0, 0)]
)
def test_tva_arrondie_au_centime(ht: int, attendu: int) -> None:
    assert tva(ht, 2000) == attendu


def test_total_ht_somme_des_lignes_arrondies() -> None:
    # 3 lignes de 0,33 × 10,01 € = 3,30 € chacune : 9,90 € HT (et non 9,9099 € arrondi à 9,91).
    ligne = {"type": "piece", "quantite": "0.33", "prix_unitaire_ht_centimes": 1_001}
    resultat = totaux(_lignes([ligne, ligne, ligne]), 2000)

    assert resultat.total_ht_centimes == 990
    assert resultat.total_tva_centimes == 198
    assert resultat.total_ttc_centimes == 1_188


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("0,5", Decimal("0.50")),
        ("1.50", Decimal("1.50")),
        (" 2 ", Decimal("2.00")),
        (2, Decimal("2.00")),
        ("0.25", Decimal("0.25")),
        ("1.500", Decimal("1.50")),
        ("9999.99", Decimal("9999.99")),
    ],
)
def test_lecture_de_la_quantite(saisie: object, attendu: Decimal) -> None:
    assert lire_quantite(saisie) == attendu


@pytest.mark.parametrize(
    ("saisie", "message"),
    [
        ("0", calcul_devis.MESSAGE_QUANTITE_POSITIVE),
        (0, calcul_devis.MESSAGE_QUANTITE_POSITIVE),
        ("-1", calcul_devis.MESSAGE_QUANTITE_POSITIVE),
        ("-0", calcul_devis.MESSAGE_QUANTITE_POSITIVE),
        ("1.005", calcul_devis.MESSAGE_QUANTITE_DECIMALES),
        ("0.333", calcul_devis.MESSAGE_QUANTITE_DECIMALES),
        ("10000", calcul_devis.MESSAGE_QUANTITE_MAX),
        ("abc", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("NaN", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("Infinity", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        (True, calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        (None, calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("1" * 40, calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        # Revue du sprint 3 : formes que Decimal accepte mais que l'interface refuse.
        ("1e3", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("1E-2", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("1_0", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("１", calcul_devis.MESSAGE_QUANTITE_INVALIDE),  # chiffre pleine largeur
        ("٢", calcul_devis.MESSAGE_QUANTITE_INVALIDE),  # chiffre arabe
        ("+2", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        (".5", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("1.", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("1,5,0", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        # Nombre JSON à virgule : déjà arrondi en flottant (1.0000000000000001 → 1.0) avant
        # toute lecture, il est refusé au lieu d'être accepté en silence.
        (1.0000000000000001, calcul_devis.MESSAGE_QUANTITE_TEXTE),
        (0.25, calcul_devis.MESSAGE_QUANTITE_TEXTE),
        (2.0, calcul_devis.MESSAGE_QUANTITE_TEXTE),
    ],
)
def test_quantite_refusee_jamais_arrondie_en_silence(saisie: object, message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("(", r"\(")):
        lire_quantite(saisie)


# --- API ------------------------------------------------------------------------------------


@pytest.fixture
def ordre(db: Session, gerant: Utilisateur) -> OrdreTravail:
    client = Client(nom="Laurent", prenom="Claire", telephone="0612483075")
    db.add(client)
    db.flush()
    vehicule = Vehicule(
        client_id=client.id,
        immatriculation="GH-482-KL",
        marque="Peugeot",
        modele="308 SW",
        kilometrage=84_312,
    )
    db.add(vehicule)
    db.flush()
    ordre = OrdreTravail(
        numero="OT-2026-001",
        vehicule=vehicule,
        demande_client="Bruit au freinage côté avant gauche.",
        ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
        createur=gerant,
    )
    db.add(ordre)
    db.flush()
    return ordre


def _creer(c: TestClient, ordre_id: int, lignes: list[dict[str, Any]]) -> dict[str, Any]:
    reponse = c.post(f"/ordres/{ordre_id}/devis", json={"lignes": lignes})
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


def test_creation_du_devis_de_la_maquette(
    horloge: Horloge, client_gerant: TestClient, ordre: OrdreTravail
) -> None:
    devis = _creer(client_gerant, ordre.id, LIGNES_MAQUETTE)

    assert devis["totaux"] == {
        "main_oeuvre_ht_centimes": 18_000,
        "pieces_ht_centimes": 19_900,
        "total_ht_centimes": 37_900,
        "total_tva_centimes": 7_580,
        "total_ttc_centimes": 45_480,
    }
    assert devis["taux_tva_bp"] == 2000
    assert devis["ordre"] == {"id": ordre.id, "numero": "OT-2026-001", "statut": "a_faire"}
    assert devis["facture"] is None
    assert devis["cree_le"] == "2026-11-02T13:47:00Z"
    premiere = devis["lignes"][0]
    assert premiere == {
        "id": premiere["id"],
        "type": "main_oeuvre",
        "reference": "MO-DIAG",
        "designation": "Diagnostic freinage",
        "quantite": "0.50",
        "prix_unitaire_ht_centimes": 7200,
        "total_ht_centimes": 3600,
        "position": 0,
    }
    assert [ligne["quantite"] for ligne in devis["lignes"]] == [
        "0.50", "1.50", "0.50", "1.00", "1.00", "1.00", "1.00"
    ]  # fmt: skip
    assert [ligne["position"] for ligne in devis["lignes"]] == list(range(7))

    lu = client_gerant.get(f"/ordres/{ordre.id}/devis")
    assert lu.status_code == 200
    assert lu.json() == devis
    assert client_gerant.get(f"/devis/{devis['id']}").json() == devis


def test_creation_168_euros_ttc_par_l_api(
    client_gerant: TestClient, ordre: OrdreTravail, db: Session
) -> None:
    devis = _creer(client_gerant, ordre.id, LIGNES_BACKLOG)

    assert devis["totaux"]["total_ht_centimes"] == 14_000
    assert devis["totaux"]["total_tva_centimes"] == 2_800
    assert devis["totaux"]["total_ttc_centimes"] == 16_800
    # Les totaux sont enregistrés tels que renvoyés.
    enregistre = db.get_one(Devis, devis["id"])
    db.refresh(enregistre)
    assert (enregistre.total_ht_centimes, enregistre.total_ttc_centimes) == (14_000, 16_800)


def test_reference_vide_enregistree_comme_absente(
    client_gerant: TestClient, ordre: OrdreTravail
) -> None:
    ligne = {**LIGNES_BACKLOG[0], "reference": "   "}

    devis = _creer(client_gerant, ordre.id, [ligne])

    assert devis["lignes"][0]["reference"] is None


@pytest.mark.parametrize(
    ("quantite", "message"),
    [
        ("0", "La quantité doit être supérieure à 0."),
        (0, "La quantité doit être supérieure à 0."),
        ("-1", "La quantité doit être supérieure à 0."),
        ("-0,5", "La quantité doit être supérieure à 0."),
        ("1.005", "Deux décimales au plus pour la quantité."),
        ("deux", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("1e3", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        ("１", calcul_devis.MESSAGE_QUANTITE_INVALIDE),
        (1.0000000000000001, calcul_devis.MESSAGE_QUANTITE_TEXTE),
    ],
)
def test_quantite_nulle_negative_ou_a_trois_decimales_422(
    client_gerant: TestClient, ordre: OrdreTravail, quantite: object, message: str
) -> None:
    lignes = [LIGNES_BACKLOG[0], {**LIGNES_BACKLOG[1], "quantite": quantite}]

    reponse = client_gerant.post(f"/ordres/{ordre.id}/devis", json={"lignes": lignes})

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"lignes.1.quantite": message}
    assert client_gerant.get(f"/ordres/{ordre.id}/devis").status_code == 404


@pytest.mark.parametrize(
    ("surcharge", "champ"),
    [
        ({"prix_unitaire_ht_centimes": -1}, "lignes.0.prix_unitaire_ht_centimes"),
        ({"prix_unitaire_ht_centimes": 10_000_001}, "lignes.0.prix_unitaire_ht_centimes"),
        ({"prix_unitaire_ht_centimes": "4000"}, "lignes.0.prix_unitaire_ht_centimes"),
        ({"prix_unitaire_ht_centimes": 40.5}, "lignes.0.prix_unitaire_ht_centimes"),
        ({"designation": "  "}, "lignes.0.designation"),
        ({"designation": "x" * 201}, "lignes.0.designation"),
        ({"reference": "R" * 41}, "lignes.0.reference"),
        ({"type": "forfait"}, "lignes.0.type"),
    ],
)
def test_ligne_invalide_422_sur_le_champ(
    client_gerant: TestClient, ordre: OrdreTravail, surcharge: dict[str, Any], champ: str
) -> None:
    reponse = client_gerant.post(
        f"/ordres/{ordre.id}/devis", json={"lignes": [{**LIGNES_BACKLOG[0], **surcharge}]}
    )

    assert reponse.status_code == 422
    assert list(reponse.json()["champs"]) == [champ]


def test_devis_sans_ligne_ou_avec_trop_de_lignes_422(
    client_gerant: TestClient, ordre: OrdreTravail
) -> None:
    vide = client_gerant.post(f"/ordres/{ordre.id}/devis", json={"lignes": []})
    trop = client_gerant.post(
        f"/ordres/{ordre.id}/devis", json={"lignes": [LIGNES_BACKLOG[0]] * 101}
    )

    assert vide.status_code == 422
    assert vide.json()["champs"] == {"lignes": "Le devis doit contenir au moins une ligne."}
    assert trop.status_code == 422
    assert trop.json()["champs"] == {"lignes": "100 lignes au plus par devis."}


def test_ordre_inconnu_404(client_gerant: TestClient) -> None:
    for ordre_id in (999_999, 2**40):
        creation = client_gerant.post(f"/ordres/{ordre_id}/devis", json={"lignes": LIGNES_BACKLOG})
        assert creation.status_code == 404
        assert creation.json()["message"] == "Ordre de travail introuvable."
        assert client_gerant.get(f"/ordres/{ordre_id}/devis").status_code == 404


def test_ordre_sans_devis_404(client_gerant: TestClient, ordre: OrdreTravail) -> None:
    reponse = client_gerant.get(f"/ordres/{ordre.id}/devis")

    assert reponse.status_code == 404
    assert reponse.json()["message"] == "Aucun devis pour cet ordre de travail."


def test_devis_inconnu_404(client_gerant: TestClient) -> None:
    for devis_id in (999_999, 2**40):
        assert client_gerant.get(f"/devis/{devis_id}").status_code == 404
        modification = client_gerant.put(f"/devis/{devis_id}", json={"lignes": LIGNES_BACKLOG})
        assert modification.status_code == 404
        assert modification.json()["message"] == "Devis introuvable."


def test_un_seul_devis_courant_par_ordre_409(
    client_gerant: TestClient, ordre: OrdreTravail
) -> None:
    premier = _creer(client_gerant, ordre.id, LIGNES_BACKLOG)

    second = client_gerant.post(f"/ordres/{ordre.id}/devis", json={"lignes": LIGNES_MAQUETTE})

    assert second.status_code == 409
    assert second.json()["code"] == "devis_existant"
    assert second.json()["devis_id"] == premier["id"]


def test_modification_remplace_les_lignes_et_recalcule(
    horloge: Horloge, client_gerant: TestClient, ordre: OrdreTravail
) -> None:
    devis = _creer(client_gerant, ordre.id, LIGNES_BACKLOG)
    horloge.avancer(minutes=30)

    reponse = client_gerant.put(f"/devis/{devis['id']}", json={"lignes": LIGNES_MAQUETTE})

    assert reponse.status_code == 200
    modifie = reponse.json()
    assert modifie["id"] == devis["id"]
    assert modifie["totaux"]["total_ttc_centimes"] == 45_480
    assert len(modifie["lignes"]) == 7
    assert modifie["cree_le"] == "2026-11-02T13:47:00Z"
    assert modifie["modifie_le"] == "2026-11-02T14:17:00Z"
    assert client_gerant.get(f"/ordres/{ordre.id}/devis").json() == modifie

    invalide = client_gerant.put(f"/devis/{devis['id']}", json={"lignes": []})
    assert invalide.status_code == 422
    assert client_gerant.get(f"/devis/{devis['id']}").json()["totaux"] == modifie["totaux"]


def test_liste_des_devis_du_plus_recent_au_plus_ancien(
    horloge: Horloge, client_gerant: TestClient, ordre: OrdreTravail, db: Session
) -> None:
    autre = OrdreTravail(
        numero="OT-2026-002",
        vehicule=ordre.vehicule,
        demande_client="Vidange.",
        ouvert_le=ordre.ouvert_le,
        createur=ordre.createur,
    )
    db.add(autre)
    db.flush()
    _creer(client_gerant, ordre.id, LIGNES_BACKLOG)
    horloge.avancer(hours=1)
    _creer(client_gerant, autre.id, LIGNES_MAQUETTE)

    page = client_gerant.get("/devis?taille=1").json()

    assert (page["total"], page["page"], page["taille"]) == (2, 1, 1)
    recent = page["elements"][0]
    assert recent["ordre"]["numero"] == "OT-2026-002"
    assert recent["vehicule"]["immatriculation"] == "GH-482-KL"
    assert recent["client"] == {
        "id": ordre.vehicule.client_id,
        "nom": "Laurent",
        "prenom": "Claire",
    }
    assert (recent["total_ht_centimes"], recent["total_ttc_centimes"]) == (37_900, 45_480)
    assert recent["facture"] is None
    suivante = client_gerant.get("/devis?taille=1&page=2").json()["elements"]
    assert [d["ordre"]["numero"] for d in suivante] == ["OT-2026-001"]


# --- Accès ----------------------------------------------------------------------------------


def _routes(ordre_id: int, devis_id: int) -> list[tuple[str, str]]:
    return [
        ("POST", f"/ordres/{ordre_id}/devis"),
        ("GET", f"/ordres/{ordre_id}/devis"),
        ("GET", "/devis"),
        ("GET", f"/devis/{devis_id}"),
        ("PUT", f"/devis/{devis_id}"),
    ]


def test_mecanicien_refuse_sur_chaque_route_du_devis(
    client_gerant: TestClient, client_mecanicien: TestClient, ordre: OrdreTravail
) -> None:
    devis = _creer(client_gerant, ordre.id, LIGNES_BACKLOG)

    for methode, chemin in _routes(ordre.id, devis["id"]):
        reponse = client_mecanicien.request(methode, chemin, json={"lignes": LIGNES_MAQUETTE})
        assert reponse.status_code == 403, (methode, chemin)
        assert reponse.json()["code"] == "interdit"
    assert client_gerant.get(f"/devis/{devis['id']}").json()["totaux"]["total_ttc_centimes"] == (
        16_800
    )


def test_sans_session_401(client_anonyme: TestClient, ordre: OrdreTravail) -> None:
    for methode, chemin in _routes(ordre.id, 1):
        assert client_anonyme.request(methode, chemin, json={}).status_code == 401


def test_la_fiche_de_l_ot_ne_porte_aucun_montant_pour_le_mecanicien(
    client_gerant: TestClient, client_mecanicien: TestClient, ordre: OrdreTravail
) -> None:
    _creer(client_gerant, ordre.id, LIGNES_MAQUETTE)

    for chemin in (f"/ordres/{ordre.id}", "/ordres", "/planning"):
        reponse = client_mecanicien.get(chemin)
        assert reponse.status_code == 200
        assert "centimes" not in reponse.text, chemin
        assert "45480" not in reponse.text, chemin


# --- Concurrence ----------------------------------------------------------------------------


@dataclass(frozen=True)
class DonneesDevis:
    gerant_id: int
    client_id: int
    vehicule_id: int
    ordre_id: int
    devis_id: int


@pytest.fixture
def devis_valide(engine: Engine) -> Iterator[DonneesDevis]:
    """Devis réellement validé en base (deux connexions), supprimé à la fin du test."""
    with nouvelle_session(engine) as s:
        gerant = Utilisateur(
            email="gerant.devis@garage.test",
            prenom="Nadia",
            nom="Devis",
            role=Role.GERANT,
            mot_de_passe_hash="x",
        )
        client = Client(nom="Concurrence", prenom="Devis", telephone="0612483075")
        s.add_all([gerant, client])
        s.flush()
        vehicule = Vehicule(
            client_id=client.id,
            immatriculation="ZZ-093-ZZ",
            marque="Peugeot",
            modele="308 SW",
            kilometrage=1,
        )
        ordre = OrdreTravail(
            numero="OT-2093-001",
            vehicule=vehicule,
            demande_client="Sonde de concurrence.",
            ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
            createur=gerant,
        )
        s.add_all([vehicule, ordre])
        s.flush()
        entree = DevisEntree.model_validate({"lignes": LIGNES_BACKLOG})
        devis = service_devis.creer_devis(s, ordre, entree.lignes, gerant, datetime.now(UTC))
        s.commit()
        donnees = DonneesDevis(gerant.id, client.id, vehicule.id, ordre.id, devis.id)
    yield donnees
    with engine.begin() as c:
        c.execute(delete(Devis).where(Devis.id == donnees.devis_id))
        c.execute(delete(OrdreTravail).where(OrdreTravail.id == donnees.ordre_id))
        c.execute(delete(Vehicule).where(Vehicule.id == donnees.vehicule_id))
        c.execute(delete(Client).where(Client.id == donnees.client_id))
        c.execute(delete(Utilisateur).where(Utilisateur.id == donnees.gerant_id))


def test_deux_modifications_simultanees_s_appliquent_l_une_apres_l_autre(
    engine: Engine, devis_valide: DonneesDevis
) -> None:
    maintenant = datetime(2026, 11, 2, 13, 47, tzinfo=UTC)

    def modifier(lignes: list[dict[str, Any]]) -> Any:
        def _put(s: Session) -> Any:
            entree = DevisEntree.model_validate({"lignes": lignes})
            return routes_devis.modifier(devis_valide.devis_id, entree, s, maintenant)

        return _put

    attendait, issue = en_parallele(engine, modifier(LIGNES_MAQUETTE), modifier(LIGNES_BACKLOG))

    assert attendait, "la seconde modification doit attendre le verrou du devis"
    assert issue[0].totaux.total_ttc_centimes == 16_800
    with nouvelle_session(engine) as s:
        devis = s.get_one(Devis, devis_valide.devis_id)
        assert len(devis.lignes) == 2
        assert devis.total_ttc_centimes == 16_800
        assert sum(ligne.total_ht_centimes for ligne in devis.lignes) == devis.total_ht_centimes
