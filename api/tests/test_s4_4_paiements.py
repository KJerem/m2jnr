"""Story S4.4 — paiements d'une facture : paiements partiels, solde restant, statut payé ;
trop-perçu refusé (par l'API et par la base), paiements immuables, retard, accès."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import (
    Client,
    Compteur,
    Devis,
    Facture,
    LigneFacture,
    ModePaiement,
    OrdreTravail,
    Paiement,
    Role,
    StatutDevis,
    StatutOT,
    Utilisateur,
    Vehicule,
)
from app.routers import factures as routes_factures
from app.schemas.devis import DevisEntree
from app.schemas.facture import PaiementEntree
from app.services import devis as service_devis
from app.services import factures as service_factures
from app.services.paiements import Solde, StatutPaiement, en_retard, solde
from app.services.statut_devis import changer_statut_devis
from tests.conftest import Horloge, connecter
from tests.test_concurrence_ordres import en_parallele, nouvelle_session
from tests.test_s4_1_devis import LIGNES_BACKLOG
from tests.test_s4_3_facture import _devis, _facturer, _ordre, _texte_pdf

NBSP = " "


@pytest.fixture
def facture(horloge: Horloge, client_gerant: TestClient, db: Session, gerant: Utilisateur) -> Any:
    """Facture de 168,00 € TTC émise le lundi 2 novembre 2026 à 14 h 47 (Paris), échéance
    le 2 décembre (délai de 30 jours). Le gérant se reconnecte à l'heure de l'horloge (sa
    session, ouverte avant, aurait expiré)."""
    connecter(client_gerant, gerant.email)
    devis = _devis(client_gerant, _ordre(db, gerant), LIGNES_BACKLOG)
    emise = _facturer(client_gerant, devis["id"])
    assert emise["totaux"]["total_ttc_centimes"] == 16_800
    return emise


def _payer(c: TestClient, facture_id: int, **corps: Any) -> Any:
    return c.post(f"/factures/{facture_id}/paiements", json={"mode": "carte", **corps})


# --- Règles pures ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("deja", "reste", "statut"),
    [
        (0, 16_800, StatutPaiement.IMPAYEE),
        (1, 16_799, StatutPaiement.PARTIELLE),
        (16_799, 1, StatutPaiement.PARTIELLE),
        (16_800, 0, StatutPaiement.PAYEE),
    ],
)
def test_solde(deja: int, reste: int, statut: StatutPaiement) -> None:
    assert solde(16_800, deja) == Solde(deja, reste, statut)


def test_facture_a_zero_euro_payee() -> None:
    assert solde(0, 0).statut == StatutPaiement.PAYEE


def test_retard_le_lendemain_de_l_echeance_seulement() -> None:
    echeance = date(2026, 12, 2)
    assert not en_retard(StatutPaiement.IMPAYEE, echeance, date(2026, 12, 2))
    assert en_retard(StatutPaiement.IMPAYEE, echeance, date(2026, 12, 3))
    assert en_retard(StatutPaiement.PARTIELLE, echeance, date(2026, 12, 3))
    assert not en_retard(StatutPaiement.PAYEE, echeance, date(2027, 1, 1))


# --- Paiement partiel puis total ---------------------------------------------------------------


def test_facture_emise_impayee(facture: Any) -> None:
    assert facture["paiements"] == []
    assert (facture["deja_paye_centimes"], facture["reste_centimes"]) == (0, 16_800)
    assert facture["statut_paiement"] == "impayee"
    assert facture["en_retard"] is False


def test_paiement_partiel_puis_total(
    horloge: Horloge, client_gerant: TestClient, gerant: Utilisateur, facture: Any
) -> None:
    horloge.avancer(hours=1)
    partiel = _payer(
        client_gerant, facture["id"], montant_centimes=5_000, mode="cheque", reference=" 1234567 "
    )
    assert partiel.status_code == 201, partiel.text
    corps = partiel.json()
    assert (corps["deja_paye_centimes"], corps["reste_centimes"]) == (5_000, 11_800)
    assert corps["statut_paiement"] == "partielle"
    [paiement] = corps["paiements"]
    assert paiement["montant_centimes"] == 5_000
    assert paiement["mode"] == "cheque"
    assert paiement["reference"] == "1234567"
    assert paiement["recu_le"] == "2026-11-02T14:47:00Z"  # par défaut : maintenant
    assert paiement["cree_par"] == {"id": gerant.id, "nom": "Nadia Benali"}

    horloge.avancer(hours=3)
    total = _payer(client_gerant, facture["id"], montant_centimes=11_800, mode="especes")
    assert total.status_code == 201, total.text
    corps = total.json()
    assert (corps["deja_paye_centimes"], corps["reste_centimes"]) == (16_800, 0)
    assert corps["statut_paiement"] == "payee"
    assert [p["mode"] for p in corps["paiements"]] == ["cheque", "especes"]

    relue = client_gerant.get(f"/factures/{facture['id']}").json()
    assert relue["statut_paiement"] == "payee"
    assert relue["paiements"] == corps["paiements"]


def test_paiements_du_plus_ancien_au_plus_recent(
    horloge: Horloge, client_gerant: TestClient, gerant: Utilisateur, facture: Any
) -> None:
    horloge.avancer(days=2)
    connecter(client_gerant, gerant.email)  # la session dure 10 h
    _payer(client_gerant, facture["id"], montant_centimes=100, recu_le="2026-11-04T09:00:00")
    corps = _payer(
        client_gerant, facture["id"], montant_centimes=200, recu_le="2026-11-03T10:15:00"
    ).json()
    assert [p["montant_centimes"] for p in corps["paiements"]] == [200, 100]
    # Date et heure sans fuseau : lues à l'heure de Paris (UTC+1 en novembre).
    assert corps["paiements"][0]["recu_le"] == "2026-11-03T09:15:00Z"


# --- Refus -------------------------------------------------------------------------------------


def test_trop_percu_409_avec_le_reste_a_payer(
    horloge: Horloge, client_gerant: TestClient, facture: Any
) -> None:
    assert _payer(client_gerant, facture["id"], montant_centimes=15_560).status_code == 201

    reponse = _payer(client_gerant, facture["id"], montant_centimes=1_241)

    assert reponse.status_code == 409
    assert reponse.json() == {
        "code": "trop_percu",
        "message": f"Le paiement dépasse le reste à payer (12,40{NBSP}€).",
        "champs": {},
        "reste_centimes": 1_240,
    }
    assert client_gerant.get(f"/factures/{facture['id']}").json()["reste_centimes"] == 1_240


def test_trop_percu_des_le_premier_paiement(client_gerant: TestClient, facture: Any) -> None:
    reponse = _payer(client_gerant, facture["id"], montant_centimes=16_801)
    assert reponse.status_code == 409
    assert reponse.json()["reste_centimes"] == 16_800


def test_paiement_sur_une_facture_payee_409(client_gerant: TestClient, facture: Any) -> None:
    assert _payer(client_gerant, facture["id"], montant_centimes=16_800).status_code == 201

    reponse = _payer(client_gerant, facture["id"], montant_centimes=1)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "facture_payee"
    assert reponse.json()["message"] == "Cette facture est déjà payée."


@pytest.mark.parametrize(
    ("montant", "message"),
    [
        (0, "Doit être supérieur à 0."),
        (-500, "Doit être supérieur à 0."),
        (12.5, "Nombre entier attendu."),
        ("1000", "Nombre entier attendu."),
        (True, "Nombre entier attendu."),
        (None, "Nombre entier attendu."),
        (1_000_000_001, "Doit être inférieur ou égal à 1000000000."),
    ],
)
def test_montant_invalide_422(
    client_gerant: TestClient, facture: Any, montant: Any, message: str
) -> None:
    reponse = _payer(client_gerant, facture["id"], montant_centimes=montant)
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"montant_centimes": message}


def test_montant_absent_422(client_gerant: TestClient, facture: Any) -> None:
    reponse = client_gerant.post(f"/factures/{facture['id']}/paiements", json={"mode": "carte"})
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"montant_centimes": "Champ obligatoire."}


@pytest.mark.parametrize("mode", ["cb", "Carte", "", None, "numero_de_carte"])
def test_mode_invalide_422(client_gerant: TestClient, facture: Any, mode: Any) -> None:
    reponse = client_gerant.post(
        f"/factures/{facture['id']}/paiements", json={"montant_centimes": 100, "mode": mode}
    )
    assert reponse.status_code == 422
    assert "mode" in reponse.json()["champs"]


def test_reception_dans_le_futur_422(
    horloge: Horloge, client_gerant: TestClient, facture: Any
) -> None:
    reponse = _payer(
        client_gerant, facture["id"], montant_centimes=100, recu_le="2026-11-02T14:48:00+01:00"
    )
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "recu_le": "La date de réception ne peut pas être dans le futur."
    }


def test_reception_avant_l_emission_422(
    horloge: Horloge, client_gerant: TestClient, facture: Any
) -> None:
    horloge.avancer(hours=1)
    reponse = _payer(
        client_gerant, facture["id"], montant_centimes=100, recu_le="2026-11-02T14:46:00"
    )
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "recu_le": "Le paiement ne peut pas précéder l'émission de la facture"
        f" (02/11/2026 à 14{NBSP}h{NBSP}47)."
    }
    # À l'instant même de l'émission : accepté.
    reponse = _payer(
        client_gerant, facture["id"], montant_centimes=100, recu_le="2026-11-02T13:47:00Z"
    )
    assert reponse.status_code == 201


def test_reception_saisie_dans_la_minute_de_l_emission(
    horloge: Horloge, client_gerant: TestClient, db: Session, gerant: Utilisateur
) -> None:
    """Le formulaire envoie une heure à la minute (« 2026-11-02T14:47 ») alors que la facture
    est émise à 14 h 47 min 40 s : le paiement est accepté et daté de l'émission, jamais avant."""
    horloge.avancer(seconds=40)
    connecter(client_gerant, gerant.email)
    emise = _facturer(
        client_gerant, _devis(client_gerant, _ordre(db, gerant), LIGNES_BACKLOG)["id"]
    )
    assert emise["emise_le"] == "2026-11-02T13:47:40Z"
    horloge.avancer(minutes=5)

    reponse = _payer(client_gerant, emise["id"], montant_centimes=100, recu_le="2026-11-02T14:47")
    assert reponse.status_code == 201, reponse.text
    assert reponse.json()["paiements"][0]["recu_le"] == "2026-11-02T13:47:40Z"

    # La minute précédente reste refusée.
    reponse = _payer(client_gerant, emise["id"], montant_centimes=100, recu_le="2026-11-02T14:46")
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "recu_le": "Le paiement ne peut pas précéder l'émission de la facture"
        f" (02/11/2026 à 14{NBSP}h{NBSP}47)."
    }


@pytest.mark.parametrize("recu_le", ["1999-12-31T10:00:00", "demain", "2026-13-01T10:00"])
def test_reception_invalide_422(client_gerant: TestClient, facture: Any, recu_le: str) -> None:
    reponse = _payer(client_gerant, facture["id"], montant_centimes=100, recu_le=recu_le)
    assert reponse.status_code == 422
    assert "recu_le" in reponse.json()["champs"]


@pytest.mark.parametrize(
    ("reference", "attendue", "statut"),
    [
        ("", None, 201),
        ("   ", None, 201),
        ("VIR-2026-1122", "VIR-2026-1122", 201),
        ("x" * 61, None, 422),
        ("ch\x00eque", None, 422),
    ],
)
def test_reference_facultative(
    client_gerant: TestClient, facture: Any, reference: str, attendue: str | None, statut: int
) -> None:
    reponse = _payer(client_gerant, facture["id"], montant_centimes=100, reference=reference)
    assert reponse.status_code == statut, reponse.text
    if statut == 201:
        assert reponse.json()["paiements"][0]["reference"] == attendue


def test_facture_inconnue_404(client_gerant: TestClient) -> None:
    for facture_id in (999_999, 2**40):
        reponse = _payer(client_gerant, facture_id, montant_centimes=100)
        assert reponse.status_code == 404
        assert reponse.json()["message"] == "Facture introuvable."


# --- Retard, liste filtrée, PDF ----------------------------------------------------------------


def test_en_retard_le_lendemain_de_l_echeance_a_paris(
    horloge: Horloge, client_gerant: TestClient, gerant: Utilisateur, facture: Any
) -> None:
    assert facture["echeance"] == "2026-12-02"
    # Mercredi 2 décembre, 23 h 59 à Paris : pas encore en retard.
    horloge.maintenant = datetime(2026, 12, 2, 22, 59, tzinfo=UTC)
    connecter(client_gerant, gerant.email)  # la session dure 10 h
    assert client_gerant.get(f"/factures/{facture['id']}").json()["en_retard"] is False
    # Jeudi 3 décembre, 0 h 01 à Paris (23 h 01 UTC le 2) : en retard.
    horloge.maintenant = datetime(2026, 12, 2, 23, 1, tzinfo=UTC)
    assert client_gerant.get(f"/factures/{facture['id']}").json()["en_retard"] is True
    [ligne] = client_gerant.get("/factures").json()["elements"]
    assert ligne["en_retard"] is True

    _payer(client_gerant, facture["id"], montant_centimes=8_000)
    assert client_gerant.get(f"/factures/{facture['id']}").json()["en_retard"] is True
    corps = _payer(client_gerant, facture["id"], montant_centimes=8_800).json()
    assert corps["statut_paiement"] == "payee"
    assert corps["en_retard"] is False


def test_liste_filtree_par_statut_de_paiement(
    horloge: Horloge,
    client_gerant: TestClient,
    db: Session,
    gerant: Utilisateur,
) -> None:
    ids = []
    for _ in range(3):
        devis = _devis(client_gerant, _ordre(db, gerant), LIGNES_BACKLOG)
        ids.append(_facturer(client_gerant, devis["id"])["id"])
    impayee, partielle, payee = ids
    _payer(client_gerant, partielle, montant_centimes=1_000)
    _payer(client_gerant, payee, montant_centimes=16_800)

    def _liste(filtre: str | None = None) -> list[tuple[int, str, int]]:
        params = {"statut_paiement": filtre} if filtre else {}
        reponse = client_gerant.get("/factures", params=params)
        assert reponse.status_code == 200, reponse.text
        return [
            (f["id"], f["statut_paiement"], f["reste_centimes"]) for f in reponse.json()["elements"]
        ]

    assert _liste() == [
        (payee, "payee", 0),
        (partielle, "partielle", 15_800),
        (impayee, "impayee", 16_800),
    ]
    assert _liste("impayee") == [(impayee, "impayee", 16_800)]
    assert _liste("partielle") == [(partielle, "partielle", 15_800)]
    assert _liste("payee") == [(payee, "payee", 0)]
    assert client_gerant.get("/factures", params={"statut_paiement": "payées"}).status_code == 422
    resume = client_gerant.get("/factures", params={"statut_paiement": "partielle"}).json()
    assert resume["total"] == 1
    assert resume["elements"][0]["deja_paye_centimes"] == 1_000
    assert len(resume["elements"][0]["paiements"]) == 1


def test_le_pdf_ne_change_pas_avec_les_paiements(
    horloge: Horloge, client_gerant: TestClient, facture: Any
) -> None:
    avant = client_gerant.get(f"/factures/{facture['id']}/pdf").content
    _payer(client_gerant, facture["id"], montant_centimes=16_800)
    apres = client_gerant.get(f"/factures/{facture['id']}/pdf").content
    assert apres == avant
    assert "Payé" not in _texte_pdf(apres)


# --- Accès ---------------------------------------------------------------------------------


def test_mecanicien_refuse_403(
    client_mecanicien: TestClient, mecanicien: Utilisateur, facture: Any
) -> None:
    connecter(client_mecanicien, mecanicien.email)
    reponse = _payer(client_mecanicien, facture["id"], montant_centimes=100)
    assert reponse.status_code == 403


def test_sans_session_401(client_anonyme: TestClient) -> None:
    reponse = client_anonyme.post("/factures/1/paiements", json={"montant_centimes": 1})
    assert reponse.status_code == 401


def test_sans_jeton_csrf_403(client_gerant: TestClient, facture: Any) -> None:
    del client_gerant.headers[get_settings().csrf_header_name]
    assert _payer(client_gerant, facture["id"], montant_centimes=100).status_code == 403


# --- Garanties de la base (deux connexions réelles) -------------------------------------------

ANNEE = 2095
MAINTENANT = datetime(ANNEE, 3, 2, 10, 0, tzinfo=UTC)


@dataclass(frozen=True)
class DonneesPaiement:
    gerant_id: int
    client_id: int
    vehicule_id: int
    ordre_id: int
    devis_id: int
    facture_id: int


@pytest.fixture
def facture_validee(engine: Engine) -> Iterator[DonneesPaiement]:
    """Facture de 168,00 € TTC validée en base, supprimée à la fin du test.

    La base refuse DELETE sur paiement, facture et ligne_facture : le nettoyage désactive
    les triggers d'immuabilité le temps de sa transaction (DDL transactionnel : aucune autre
    session ne les voit désactivés)."""
    with nouvelle_session(engine) as s:
        gerant = Utilisateur(
            email="gerant.paiement@garage.test",
            nom="Nadia Paiement",
            role=Role.GERANT,
            mot_de_passe_hash="x",
        )
        client = Client(nom="Concurrence", prenom="Paiement", telephone="0612483075")
        s.add_all([gerant, client])
        s.flush()
        vehicule = Vehicule(
            client_id=client.id,
            immatriculation="ZZ-095-ZZ",
            marque="Peugeot",
            modele="308 SW",
            kilometrage=1,
        )
        ordre = OrdreTravail(
            numero=f"OT-{ANNEE}-001",
            vehicule=vehicule,
            demande_client="Sonde de concurrence.",
            statut=StatutOT.TERMINE,
            ouvert_le=MAINTENANT,
            createur=gerant,
        )
        s.add_all([vehicule, ordre])
        s.flush()
        entree = DevisEntree.model_validate({"lignes": LIGNES_BACKLOG})
        devis = service_devis.creer_devis(s, ordre, entree.lignes, gerant, MAINTENANT)
        changer_statut_devis(devis, StatutDevis.ENVOYE, gerant, MAINTENANT)
        changer_statut_devis(devis, StatutDevis.ACCEPTE, gerant, MAINTENANT)
        facture = service_factures.etablir_facture(s, devis, gerant, MAINTENANT, get_settings())
        s.commit()
        donnees = DonneesPaiement(gerant.id, client.id, vehicule.id, ordre.id, devis.id, facture.id)
    yield donnees
    with engine.begin() as c:
        for table in ("paiement", "ligne_facture", "facture"):
            c.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {table}_immuable"))
        c.execute(delete(Paiement).where(Paiement.facture_id == donnees.facture_id))
        c.execute(delete(LigneFacture).where(LigneFacture.facture_id == donnees.facture_id))
        c.execute(delete(Facture).where(Facture.id == donnees.facture_id))
        for table in ("paiement", "ligne_facture", "facture"):
            c.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {table}_immuable"))
        c.execute(delete(Devis).where(Devis.id == donnees.devis_id))
        c.execute(delete(OrdreTravail).where(OrdreTravail.id == donnees.ordre_id))
        c.execute(delete(Vehicule).where(Vehicule.id == donnees.vehicule_id))
        c.execute(delete(Client).where(Client.id == donnees.client_id))
        c.execute(delete(Utilisateur).where(Utilisateur.id == donnees.gerant_id))
        c.execute(delete(Compteur).where(Compteur.annee == ANNEE))


def _encaisser(donnees: DonneesPaiement, montant: int) -> Callable[[Session], Any]:
    def _post(s: Session) -> Any:
        gerant = s.get_one(Utilisateur, donnees.gerant_id)
        entree = PaiementEntree(montant_centimes=montant, mode=ModePaiement.CARTE)
        return routes_factures.encaisser(
            donnees.facture_id, entree, s, gerant, MAINTENANT, get_settings()
        )

    return _post


def _cumul(engine: Engine, facture_id: int) -> tuple[int, int]:
    with nouvelle_session(engine) as s:
        nombre, total = s.execute(
            select(func.count(), func.coalesce(func.sum(Paiement.montant_centimes), 0)).where(
                Paiement.facture_id == facture_id
            )
        ).one()
        return int(nombre), int(total)


def test_deux_paiements_simultanes_qui_depassent_un_seul_accepte(
    engine: Engine, facture_validee: DonneesPaiement
) -> None:
    attendait, issue = en_parallele(
        engine, _encaisser(facture_validee, 10_000), _encaisser(facture_validee, 10_000)
    )

    assert attendait, "le second paiement doit attendre le verrou de la facture"
    assert isinstance(issue[0], AppError)
    assert (issue[0].status_code, issue[0].code) == (409, "trop_percu")
    assert issue[0].details == {"reste_centimes": 6_800}
    assert _cumul(engine, facture_validee.facture_id) == (1, 10_000)


def test_deux_paiements_simultanes_qui_soldent_la_facture(
    engine: Engine, facture_validee: DonneesPaiement
) -> None:
    attendait, issue = en_parallele(
        engine, _encaisser(facture_validee, 8_400), _encaisser(facture_validee, 8_400)
    )

    assert attendait
    assert issue[0].statut_paiement == StatutPaiement.PAYEE
    assert _cumul(engine, facture_validee.facture_id) == (2, 16_800)


def _inserer(s: Session, donnees: DonneesPaiement, montant: int) -> None:
    s.execute(
        text(
            "INSERT INTO paiement (facture_id, montant_centimes, mode, recu_le, cree_par)"
            " VALUES (:facture, :montant, 'especes', now(), :gerant)"
        ),
        {"facture": donnees.facture_id, "montant": montant, "gerant": donnees.gerant_id},
    )


def test_la_base_refuse_un_cumul_superieur_au_ttc(
    engine: Engine, facture_validee: DonneesPaiement
) -> None:
    with nouvelle_session(engine) as s:
        _inserer(s, facture_validee, 16_000)
        with pytest.raises(DBAPIError) as erreur, s.begin_nested():
            _inserer(s, facture_validee, 801)
        assert getattr(erreur.value.orig, "sqlstate", None) == "ET002"
        assert "trop perçu" in str(erreur.value.orig)
        _inserer(s, facture_validee, 800)
        s.commit()
    assert _cumul(engine, facture_validee.facture_id) == (2, 16_800)


def test_la_base_refuse_un_paiement_nul_ou_negatif(
    engine: Engine, facture_validee: DonneesPaiement
) -> None:
    with nouvelle_session(engine) as s:
        for montant in (0, -100):
            with pytest.raises(DBAPIError), s.begin_nested():
                _inserer(s, facture_validee, montant)


def test_la_base_refuse_de_modifier_ou_supprimer_un_paiement(
    engine: Engine, facture_validee: DonneesPaiement
) -> None:
    with nouvelle_session(engine) as s:
        _inserer(s, facture_validee, 1_000)
        s.commit()
    with nouvelle_session(engine) as s:
        for requete in (
            "UPDATE paiement SET montant_centimes = 1 WHERE facture_id = :facture",
            "DELETE FROM paiement WHERE facture_id = :facture",
            "TRUNCATE paiement",
        ):
            with pytest.raises(DBAPIError) as erreur, s.begin_nested():
                s.execute(text(requete), {"facture": facture_validee.facture_id})
            assert getattr(erreur.value.orig, "sqlstate", None) == "ET003", requete
            assert "paiement immuable" in str(erreur.value.orig)
    assert _cumul(engine, facture_validee.facture_id) == (1, 1_000)
