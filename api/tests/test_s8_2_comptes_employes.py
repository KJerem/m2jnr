"""Story S8.2 — comptes des employés : créer, consulter, modifier, désactiver, réactiver."""

import importlib.util
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.errors import AppError
from app.models import Role, StatutCompte, Utilisateur
from app.schemas.utilisateur import UtilisateurModification
from app.security.hachage import verifier
from app.services import comptes
from app.services.utilisateurs import separer_nom
from tests.conftest import MOT_DE_PASSE_TEST, Horloge, MakeUser, connecter

NOUVEAU_MOT_DE_PASSE = "une phrase de passe neuve"


def _nouveau(**champs: Any) -> dict[str, Any]:
    return {
        "prenom": "Paul",
        "nom": "Girard",
        "email": "paul.girard@garage.test",
        "mot_de_passe": NOUVEAU_MOT_DE_PASSE,
        "role": "mecanicien",
        **champs,
    }


def _login(c: TestClient, email: str, mot_de_passe: str = MOT_DE_PASSE_TEST):  # type: ignore[no-untyped-def]
    return c.post("/auth/login", json={"email": email, "mot_de_passe": mot_de_passe})


def _sans_secret(corps: object) -> None:
    """Aucun hash ni mot de passe dans une réponse, à quelque profondeur que ce soit."""
    assert "mot_de_passe" not in str(corps)
    assert "$argon2" not in str(corps)


# --- Règles pures ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("Nadia Benali", ("Nadia", "Benali")),
        ("Karim B.", ("Karim", "B.")),
        ("  Jean Paul  Martin ", ("Jean", "Paul  Martin")),
        ("Admin", ("Admin", "")),
    ],
)
def test_separer_nom_coupe_au_premier_espace(saisie: str, attendu: tuple[str, str]) -> None:
    assert separer_nom(saisie) == attendu


def test_reste_un_gerant_actif() -> None:
    assert comptes.reste_un_gerant_actif(1, [1, 2])
    assert not comptes.reste_un_gerant_actif(1, [1])
    assert not comptes.reste_un_gerant_actif(1, [])


def test_refus_retrait_du_dernier_gerant_actif(make_user: MakeUser) -> None:
    seul = make_user(Role.GERANT)
    mecanicien = make_user(Role.MECANICIEN)

    refus = comptes.refus_retrait(seul, [seul.id], retire_le_gerant=True)
    assert refus is not None and refus.code == "dernier_gerant"
    assert refus.message == "Il doit rester au moins un gérant actif."
    assert comptes.refus_retrait(seul, [seul.id], retire_le_gerant=False) is None
    assert comptes.refus_retrait(mecanicien, [seul.id], retire_le_gerant=True) is None


# --- Liste et consultation ------------------------------------------------------------------


def test_liste_en_attente_d_abord_puis_actifs_puis_desactives(
    client_gerant: TestClient, gerant: Utilisateur, make_user: MakeUser
) -> None:
    ancien = make_user(Role.MECANICIEN, prenom="Paul", nom="Girard", actif=False)
    attente = make_user(Role.GERANT, prenom="Inès", nom="Morel", statut=StatutCompte.EN_ATTENTE)
    actif = make_user(Role.MECANICIEN, prenom="Sophie", nom="Martin")

    corps = client_gerant.get("/utilisateurs").json()

    assert [e["id"] for e in corps["elements"]] == [attente.id, gerant.id, actif.id, ancien.id]
    assert corps["total"] == 4
    premier = corps["elements"][0]
    assert premier["statut"] == "en_attente"
    assert premier["nom_affiche"] == "Inès Morel"
    assert set(premier) == {
        "id",
        "prenom",
        "nom",
        "nom_affiche",
        "email",
        "role",
        "statut",
        "bloque_jusqu_a",
        "derniere_connexion",
        "cree_le",
        "valide_le",
        "desactive_le",
    }
    _sans_secret(corps)


def test_recherche_sans_accents_ni_casse_sur_prenom_nom_et_e_mail(
    client_gerant: TestClient, make_user: MakeUser
) -> None:
    helene = make_user(Role.MECANICIEN, prenom="Hélène", nom="Dupré", email="h.dupre@garage.test")
    make_user(Role.MECANICIEN, prenom="Lucas", nom="Roux", email="lucas@garage.test")

    for q in ("helene", "DUPRE", "hélène dupré", "h.dupre@", "  dupre  "):
        corps = client_gerant.get("/utilisateurs", params={"q": q}).json()
        assert [e["id"] for e in corps["elements"]] == [helene.id], q
        assert corps["total"] == 1


def test_recherche_jokers_pris_a_la_lettre_et_saisie_trop_courte(
    client_gerant: TestClient, make_user: MakeUser
) -> None:
    make_user(Role.MECANICIEN, prenom="Lucas", nom="Roux")

    assert client_gerant.get("/utilisateurs", params={"q": "%%"}).json()["total"] == 0
    assert client_gerant.get("/utilisateurs", params={"q": "l_cas"}).json()["total"] == 0
    reponse = client_gerant.get("/utilisateurs", params={"q": "a"})
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"q": "Saisissez au moins 2 caractères."}
    assert client_gerant.get("/utilisateurs", params={"q": " "}).status_code == 200


def test_filtres_role_statut_et_pagination(
    client_gerant: TestClient, gerant: Utilisateur, make_user: MakeUser
) -> None:
    mecaniciens = [make_user(Role.MECANICIEN, prenom="Meca", nom=f"N{i}") for i in range(3)]
    make_user(Role.MECANICIEN, prenom="Meca", nom="Parti", actif=False)

    corps = client_gerant.get(
        "/utilisateurs", params={"role": "mecanicien", "statut": "actif", "taille": 2, "page": 2}
    ).json()

    assert corps["total"] == 3
    assert [e["id"] for e in corps["elements"]] == [mecaniciens[2].id]
    gerants = client_gerant.get("/utilisateurs", params={"role": "gerant"}).json()
    assert [e["id"] for e in gerants["elements"]] == [gerant.id]
    desactives = client_gerant.get("/utilisateurs", params={"statut": "desactive", "q": "meca"})
    assert desactives.json()["total"] == 1
    assert client_gerant.get("/utilisateurs", params={"statut": "inconnu"}).status_code == 422


def test_consultation_et_identifiants_hors_limites(
    client_gerant: TestClient, mecanicien: Utilisateur
) -> None:
    reponse = client_gerant.get(f"/utilisateurs/{mecanicien.id}")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert (corps["prenom"], corps["nom"], corps["nom_affiche"]) == ("Karim", "B.", "Karim B.")
    _sans_secret(corps)
    for identifiant in (999_999, 2**31, 0):
        inconnu = client_gerant.get(f"/utilisateurs/{identifiant}")
        assert inconnu.status_code == 404
        assert inconnu.json()["message"] == "Employé introuvable."


def test_blocage_affiche_seulement_s_il_court_encore(
    horloge: Horloge, client_gerant: TestClient, mecanicien: Utilisateur, db: Session
) -> None:
    mecanicien.bloque_jusqu_a = horloge.maintenant + timedelta(minutes=10)
    db.flush()
    assert client_gerant.get(f"/utilisateurs/{mecanicien.id}").json()["bloque_jusqu_a"] == (
        "2026-11-02T13:57:00Z"
    )
    horloge.avancer(minutes=11)
    assert client_gerant.get(f"/utilisateurs/{mecanicien.id}").json()["bloque_jusqu_a"] is None


# --- Création -------------------------------------------------------------------------------


def test_creation_d_un_compte_actif_mot_de_passe_hache(
    horloge: Horloge, client_gerant: TestClient, gerant: Utilisateur, db: Session
) -> None:
    reponse = client_gerant.post("/utilisateurs", json=_nouveau(email="  Paul.Girard@Garage.TEST "))

    assert reponse.status_code == 201
    corps = reponse.json()
    _sans_secret(corps)
    assert corps["email"] == "paul.girard@garage.test"
    assert (corps["statut"], corps["role"], corps["nom_affiche"]) == (
        "actif",
        "mecanicien",
        "Paul Girard",
    )
    paul = db.get_one(Utilisateur, corps["id"])
    assert paul.mot_de_passe_hash.startswith("$argon2id$")
    assert verifier(paul.mot_de_passe_hash, NOUVEAU_MOT_DE_PASSE)
    assert (paul.valide_le, paul.valide_par) == (horloge.maintenant, gerant.id)


def test_le_nouvel_employe_se_connecte(
    client_gerant: TestClient, nouveau_client: Callable[[], TestClient]
) -> None:
    client_gerant.post("/utilisateurs", json=_nouveau())

    reponse = _login(nouveau_client(), "paul.girard@garage.test", NOUVEAU_MOT_DE_PASSE)

    assert reponse.status_code == 200
    assert reponse.json()["utilisateur"]["role"] == "mecanicien"


def test_e_mail_deja_pris_avec_une_autre_casse_409(
    client_gerant: TestClient, mecanicien: Utilisateur
) -> None:
    reponse = client_gerant.post("/utilisateurs", json=_nouveau(email="MECANICIEN@garage.test"))

    assert reponse.status_code == 409
    assert reponse.json() == {
        "code": "email_existant",
        "message": "Un compte existe déjà avec cet e-mail.",
        "champs": {"email": "Un compte existe déjà avec cet e-mail."},
    }


@pytest.mark.parametrize(
    ("champs", "champ", "message"),
    [
        (
            {"mot_de_passe": "onze-caract"},
            "mot_de_passe",
            "Le mot de passe doit contenir au moins 12 caractères.",
        ),
        ({"email": "pas-un-e-mail"}, "email", "Adresse e-mail invalide."),
        ({"prenom": "  "}, "prenom", "Champ obligatoire."),
        ({"nom": ""}, "nom", "Champ obligatoire."),
        ({"role": "patron"}, "role", "Valeur non autorisée."),
        ({"nom": "Gi\x00rard"}, "nom", "Caractère non autorisé."),
    ],
)
def test_creation_refusee_champ_par_champ(
    client_gerant: TestClient, champs: dict[str, str], champ: str, message: str
) -> None:
    reponse = client_gerant.post("/utilisateurs", json=_nouveau(**champs))

    assert reponse.status_code == 422
    assert reponse.json()["champs"][champ] == message


def test_douze_caracteres_suffisent_espaces_compris(client_gerant: TestClient) -> None:
    assert (
        client_gerant.post("/utilisateurs", json=_nouveau(mot_de_passe=" " * 12)).status_code == 201
    )


# --- Modification ---------------------------------------------------------------------------


def test_modification_du_nom_de_l_e_mail_et_du_role(
    client_gerant: TestClient, mecanicien: Utilisateur, db: Session
) -> None:
    reponse = client_gerant.put(
        f"/utilisateurs/{mecanicien.id}",
        json={
            "prenom": "Karim",
            "nom": "Benhamou",
            "email": "k.benhamou@garage.test",
            "role": "gerant",
        },
    )

    assert reponse.status_code == 200
    assert reponse.json()["nom_affiche"] == "Karim Benhamou"
    db.refresh(mecanicien)
    assert (mecanicien.email, mecanicien.role) == ("k.benhamou@garage.test", Role.GERANT)


def test_modification_vers_un_e_mail_pris_409(
    client_gerant: TestClient, mecanicien: Utilisateur, gerant: Utilisateur
) -> None:
    reponse = client_gerant.put(
        f"/utilisateurs/{mecanicien.id}",
        json={"prenom": "Karim", "nom": "B.", "email": "GERANT@garage.test", "role": "mecanicien"},
    )

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "email_existant"


def test_le_gerant_modifie_son_nom_mais_pas_son_role(
    client_gerant: TestClient, gerant: Utilisateur
) -> None:
    corps = {"prenom": "Nadia", "nom": "Benali-Roux", "email": gerant.email, "role": "gerant"}
    assert client_gerant.put(f"/utilisateurs/{gerant.id}", json=corps).status_code == 200
    assert client_gerant.get("/auth/me").json()["utilisateur"]["nom_affiche"] == "Nadia Benali-Roux"

    reponse = client_gerant.put(f"/utilisateurs/{gerant.id}", json={**corps, "role": "mecanicien"})

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "soi_meme"
    assert reponse.json()["message"] == "Vous ne pouvez pas changer votre propre rôle."


def test_retrograder_un_autre_gerant_est_permis(
    client_gerant: TestClient, make_user: MakeUser
) -> None:
    autre = make_user(Role.GERANT, prenom="Inès", nom="Morel")
    corps = {"prenom": "Inès", "nom": "Morel", "email": autre.email, "role": "mecanicien"}

    assert client_gerant.put(f"/utilisateurs/{autre.id}", json=corps).json()["role"] == "mecanicien"


def test_le_dernier_gerant_actif_ne_peut_pas_etre_retrograde(
    db: Session, gerant: Utilisateur, make_user: MakeUser
) -> None:
    """Par le service, avec un auteur qui n'est plus gérant actif (cas d'une requête restée
    en vol après sa propre rétrogradation) : il ne resterait aucun gérant."""
    ancien = make_user(Role.GERANT, actif=False)
    entree = UtilisateurModification(
        prenom="Nadia", nom="Benali", email=gerant.email, role=Role.MECANICIEN
    )

    with pytest.raises(AppError) as erreur:
        comptes.modifier_compte(db, gerant.id, entree, ancien)

    assert erreur.value.code == "dernier_gerant"
    with pytest.raises(AppError) as erreur:
        comptes.desactiver(db, gerant.id, ancien, datetime(2026, 11, 2, tzinfo=UTC))
    assert erreur.value.code == "dernier_gerant"


# --- Désactivation et réactivation ----------------------------------------------------------


def test_desactivation_refuse_la_connexion_et_coupe_la_session_ouverte(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    mecanicien: Utilisateur,
    gerant: Utilisateur,
    nouveau_client: Callable[[], TestClient],
    db: Session,
) -> None:
    assert client_mecanicien.get("/auth/me").status_code == 200

    reponse = client_gerant.post(f"/utilisateurs/{mecanicien.id}/desactiver")

    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "desactive"
    assert reponse.json()["desactive_le"] == "2026-11-02T13:47:00Z"
    db.refresh(mecanicien)
    assert mecanicien.desactive_par == gerant.id
    session = client_mecanicien.get("/ordres")
    assert session.status_code == 401
    assert session.json()["code"] == "non_authentifie"
    refus = _login(nouveau_client(), mecanicien.email)
    assert refus.status_code == 401
    assert refus.json()["message"] == "Identifiants invalides."


def test_un_desactive_disparait_des_mecaniciens_proposes(
    client_gerant: TestClient, mecanicien: Utilisateur
) -> None:
    client_gerant.post(f"/utilisateurs/{mecanicien.id}/desactiver")

    assert client_gerant.get("/mecaniciens").json() == []


def test_reactivation_rend_la_connexion(
    client_gerant: TestClient,
    mecanicien: Utilisateur,
    nouveau_client: Callable[[], TestClient],
) -> None:
    client_gerant.post(f"/utilisateurs/{mecanicien.id}/desactiver")

    reponse = client_gerant.post(f"/utilisateurs/{mecanicien.id}/reactiver")

    assert reponse.json()["statut"] == "actif"
    assert _login(nouveau_client(), mecanicien.email).status_code == 200
    assert [m["id"] for m in client_gerant.get("/mecaniciens").json()] == [mecanicien.id]


def test_reactiver_ne_rend_pas_vie_aux_sessions_ouvertes_avant_la_desactivation(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    mecanicien: Utilisateur,
    nouveau_client: Callable[[], TestClient],
    db: Session,
) -> None:
    """Revue du sprint 5 : la tablette restée connectée ou le téléphone volé d'un employé
    désactivé ne retrouvent pas leur session quand le compte est réactivé."""
    horloge.avancer(minutes=5)
    client_gerant.post(f"/utilisateurs/{mecanicien.id}/desactiver")
    horloge.avancer(hours=2)

    assert client_gerant.post(f"/utilisateurs/{mecanicien.id}/reactiver").status_code == 200

    ancienne = client_mecanicien.get("/auth/me")
    assert (ancienne.status_code, ancienne.json()["code"]) == (401, "non_authentifie")
    db.refresh(mecanicien)
    assert mecanicien.sessions_valides_depuis == horloge.maintenant - timedelta(hours=2)
    nouvelle = connecter(nouveau_client(), mecanicien.email)
    assert nouvelle.get("/auth/me").status_code == 200


def test_session_valide_comparee_a_la_seconde(make_user: MakeUser) -> None:
    compte = make_user(Role.MECANICIEN)
    coupure = datetime(2027, 1, 11, 9, 30, 15, 600_000, tzinfo=UTC)

    assert compte.session_valide(coupure - timedelta(days=1))
    compte.sessions_valides_depuis = coupure
    assert not compte.session_valide(coupure - timedelta(seconds=1))
    # Le jeton ne garde que la seconde : une session émise dans la même seconde est acceptée.
    assert compte.session_valide(coupure.replace(microsecond=0))
    assert compte.session_valide(coupure + timedelta(minutes=1))
    compte.statut = StatutCompte.DESACTIVE
    assert not compte.session_valide(coupure + timedelta(minutes=1))


def test_le_gerant_ne_se_desactive_pas(client_gerant: TestClient, gerant: Utilisateur) -> None:
    reponse = client_gerant.post(f"/utilisateurs/{gerant.id}/desactiver")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "soi_meme"
    assert client_gerant.get("/auth/me").status_code == 200


def test_transitions_de_statut_incompatibles_409(
    client_gerant: TestClient, mecanicien: Utilisateur, make_user: MakeUser
) -> None:
    attente = make_user(Role.GERANT, statut=StatutCompte.EN_ATTENTE)

    assert client_gerant.post(f"/utilisateurs/{mecanicien.id}/reactiver").status_code == 409
    client_gerant.post(f"/utilisateurs/{mecanicien.id}/desactiver")
    deja = client_gerant.post(f"/utilisateurs/{mecanicien.id}/desactiver")
    assert (deja.status_code, deja.json()["code"]) == (409, "statut_incompatible")
    for action in ("desactiver", "reactiver"):
        reponse = client_gerant.post(f"/utilisateurs/{attente.id}/{action}")
        assert reponse.status_code == 409, action
        assert "validez-le ou refusez" in reponse.json()["message"]


def test_desactiver_un_autre_gerant(
    client_gerant: TestClient, make_user: MakeUser, nouveau_client: Callable[[], TestClient]
) -> None:
    autre = make_user(Role.GERANT)
    session_autre = connecter(nouveau_client(), autre.email)

    assert client_gerant.post(f"/utilisateurs/{autre.id}/desactiver").status_code == 200
    assert session_autre.get("/utilisateurs").status_code == 401


# --- Mot de passe et blocage ----------------------------------------------------------------


def test_reinitialisation_du_mot_de_passe_et_deblocage(
    horloge: Horloge,
    client_gerant: TestClient,
    mecanicien: Utilisateur,
    nouveau_client: Callable[[], TestClient],
    db: Session,
) -> None:
    mecanicien.tentatives_echouees = 5
    mecanicien.bloque_jusqu_a = horloge.maintenant + timedelta(minutes=15)
    db.flush()

    reponse = client_gerant.post(
        f"/utilisateurs/{mecanicien.id}/mot-de-passe", json={"mot_de_passe": NOUVEAU_MOT_DE_PASSE}
    )

    assert reponse.status_code == 200
    _sans_secret(reponse.json())
    assert reponse.json()["bloque_jusqu_a"] is None
    assert _login(nouveau_client(), mecanicien.email).status_code == 401
    assert _login(nouveau_client(), mecanicien.email, NOUVEAU_MOT_DE_PASSE).status_code == 200


def test_reinitialisation_coupe_les_sessions_ouvertes(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    mecanicien: Utilisateur,
    nouveau_client: Callable[[], TestClient],
) -> None:
    """Revue du sprint 5 : le gérant réinitialise le mot de passe d'un compte compromis ; la
    session volée ne reste pas valable jusqu'à son expiration."""
    horloge.avancer(minutes=5)

    reponse = client_gerant.post(
        f"/utilisateurs/{mecanicien.id}/mot-de-passe", json={"mot_de_passe": NOUVEAU_MOT_DE_PASSE}
    )

    assert reponse.status_code == 200
    assert client_mecanicien.get("/auth/me").status_code == 401
    nouvelle = connecter(nouveau_client(), mecanicien.email, NOUVEAU_MOT_DE_PASSE)
    assert nouvelle.get("/auth/me").status_code == 200


def test_le_gerant_qui_change_son_propre_mot_de_passe_reste_connecte(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouveau_client: Callable[[], TestClient],
) -> None:
    autre_appareil = connecter(nouveau_client(), gerant.email)
    horloge.avancer(minutes=5)

    reponse = client_gerant.post(
        f"/utilisateurs/{gerant.id}/mot-de-passe", json={"mot_de_passe": NOUVEAU_MOT_DE_PASSE}
    )

    assert reponse.status_code == 200
    assert get_settings().session_cookie_name in reponse.headers["set-cookie"]
    assert client_gerant.get("/auth/me").status_code == 200
    assert autre_appareil.get("/auth/me").status_code == 401


def test_reinitialisation_exige_douze_caracteres(
    client_gerant: TestClient, mecanicien: Utilisateur
) -> None:
    reponse = client_gerant.post(
        f"/utilisateurs/{mecanicien.id}/mot-de-passe", json={"mot_de_passe": "court"}
    )

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "mot_de_passe": "Le mot de passe doit contenir au moins 12 caractères."
    }


def test_debloquer_rend_la_connexion_avant_quinze_minutes(
    horloge: Horloge,
    client_gerant: TestClient,
    mecanicien: Utilisateur,
    nouveau_client: Callable[[], TestClient],
) -> None:
    anonyme = nouveau_client()
    for _ in range(5):
        _login(anonyme, mecanicien.email, "mauvais-mot-de-passe")
    assert _login(anonyme, mecanicien.email).status_code == 423
    assert client_gerant.get(f"/utilisateurs/{mecanicien.id}").json()["bloque_jusqu_a"]

    reponse = client_gerant.post(f"/utilisateurs/{mecanicien.id}/debloquer")

    assert reponse.json()["bloque_jusqu_a"] is None
    assert _login(anonyme, mecanicien.email).status_code == 200


# --- Droits ---------------------------------------------------------------------------------


ROUTES = [
    ("get", "/utilisateurs", None),
    ("post", "/utilisateurs", _nouveau()),
    ("get", "/utilisateurs/{id}", None),
    (
        "put",
        "/utilisateurs/{id}",
        {"prenom": "K", "nom": "B", "email": "k@garage.test", "role": "gerant"},
    ),
    ("post", "/utilisateurs/{id}/mot-de-passe", {"mot_de_passe": NOUVEAU_MOT_DE_PASSE}),
    ("post", "/utilisateurs/{id}/desactiver", None),
    ("post", "/utilisateurs/{id}/reactiver", None),
    ("post", "/utilisateurs/{id}/debloquer", None),
]


@pytest.mark.parametrize(("methode", "chemin", "corps"), ROUTES)
def test_mecanicien_refuse_sur_toutes_les_routes(
    client_mecanicien: TestClient,
    mecanicien: Utilisateur,
    methode: str,
    chemin: str,
    corps: dict[str, str] | None,
    db: Session,
) -> None:
    hash_avant = mecanicien.mot_de_passe_hash
    reponse = client_mecanicien.request(methode, chemin.format(id=mecanicien.id), json=corps)

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "interdit"
    db.refresh(mecanicien)
    assert (mecanicien.role, mecanicien.statut, mecanicien.mot_de_passe_hash) == (
        Role.MECANICIEN,
        StatutCompte.ACTIF,
        hash_avant,
    )


@pytest.mark.parametrize(("methode", "chemin", "corps"), ROUTES)
def test_sans_session_401(
    client_anonyme: TestClient, methode: str, chemin: str, corps: dict[str, str] | None
) -> None:
    assert client_anonyme.request(methode, chemin.format(id=1), json=corps).status_code == 401


def test_ecriture_sans_jeton_csrf_refusee(client_gerant: TestClient) -> None:
    del client_gerant.headers["X-CSRF-Token"]

    assert client_gerant.post("/utilisateurs", json=_nouveau()).status_code == 403


def test_session_expose_prenom_nom_et_nom_affiche(client_mecanicien: TestClient) -> None:
    utilisateur = client_mecanicien.get("/auth/me").json()["utilisateur"]

    assert (utilisateur["prenom"], utilisateur["nom"], utilisateur["nom_affiche"]) == (
        "Karim",
        "B.",
        "Karim B.",
    )
    _sans_secret(utilisateur)


# --- Deux gérants en même temps (deux connexions réelles) -----------------------------------


def nouvelle_session(engine: Engine) -> Session:
    return Session(engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def deux_gerants(engine: Engine) -> Iterator[tuple[int, int]]:
    with nouvelle_session(engine) as s:
        a = Utilisateur(
            email="a.course@garage.test",
            prenom="Anne",
            nom="Course",
            role=Role.GERANT,
            mot_de_passe_hash="x",
        )
        b = Utilisateur(
            email="b.course@garage.test",
            prenom="Bruno",
            nom="Course",
            role=Role.GERANT,
            mot_de_passe_hash="x",
        )
        s.add_all([a, b])
        s.commit()
        ids = (a.id, b.id)
    yield ids
    with engine.begin() as c:
        c.execute(delete(Utilisateur).where(Utilisateur.id.in_(ids)))


def _en_parallele(
    engine: Engine, premiere: Callable[[Session], Any], seconde: Callable[[Session], Any]
) -> tuple[bool, list[Any]]:
    """`premiere` s'exécute et garde sa transaction ouverte ; `seconde` démarre dans un autre
    fil. Renvoie (la seconde attendait-elle ?, [résultat ou exception de la seconde])."""
    issue: list[Any] = []

    def fil_second() -> None:
        try:
            with nouvelle_session(engine) as s:
                resultat = seconde(s)
                s.commit()
                issue.append(resultat)
        except BaseException as exc:
            issue.append(exc)

    with nouvelle_session(engine) as s:
        premiere(s)
        fil = threading.Thread(target=fil_second)
        fil.start()
        fil.join(timeout=0.5)
        attendait = fil.is_alive()
        s.commit()
    fil.join(timeout=10)
    assert not fil.is_alive()
    return attendait, issue


def _retrograder(cible: int, auteur: int) -> Callable[[Session], Any]:
    def _faire(s: Session) -> Any:
        acteur = s.get_one(Utilisateur, auteur)
        cible_ligne = s.get_one(Utilisateur, cible)
        entree = UtilisateurModification(
            prenom=cible_ligne.prenom,
            nom=cible_ligne.nom,
            email=cible_ligne.email,
            role=Role.MECANICIEN,
        )
        return comptes.modifier_compte(s, cible, entree, acteur)

    return _faire


def _desactiver(cible: int, auteur: int) -> Callable[[Session], Any]:
    def _faire(s: Session) -> Any:
        return comptes.desactiver(s, cible, s.get_one(Utilisateur, auteur), datetime.now(UTC))

    return _faire


@pytest.mark.parametrize("operation", [_retrograder, _desactiver])
def test_deux_gerants_qui_se_retirent_l_un_l_autre_en_laissent_un(
    engine: Engine, deux_gerants: tuple[int, int], operation: Callable[..., Any]
) -> None:
    a, b = deux_gerants

    attendait, issue = _en_parallele(engine, operation(b, a), operation(a, b))

    assert attendait, "la seconde opération doit attendre le verrou des gérants"
    assert isinstance(issue[0], AppError) and issue[0].code == "dernier_gerant"
    with nouvelle_session(engine) as s:
        restants = [
            u.id
            for u in (s.get_one(Utilisateur, a), s.get_one(Utilisateur, b))
            if u.role == Role.GERANT and u.statut == StatutCompte.ACTIF
        ]
    assert restants == [a]


# --- Migration 0016 : reprise des comptes existants ---------------------------------------------


def _migration_0016() -> Any:
    chemin = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    fichier = next(chemin.glob("*_0016_*.py"))
    spec = importlib.util.spec_from_file_location(fichier.stem, fichier)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_0016_prenom_repris_et_statut_du_booleen(engine: Engine) -> None:
    """Downgrade puis upgrade de 0016 dans une transaction annulée : le nom est coupé au premier
    espace, l'affichage ne change pas, un compte inactif devient « desactive » ; le downgrade
    recolle le prénom et le nom."""
    migration = _migration_0016()
    with engine.connect() as connexion:
        transaction = connexion.begin()
        try:
            contexte = MigrationContext.configure(
                connexion, opts={"target_metadata": Base.metadata}
            )
            with Operations.context(contexte):
                migration.downgrade()
                connexion.execute(
                    text(
                        "INSERT INTO utilisateur (email, nom, mot_de_passe_hash, role, actif)"
                        " VALUES"
                        " ('n@m.test', 'Nadia Benali', 'x', 'gerant', true),"
                        " ('k@m.test', 'Karim B.', 'x', 'mecanicien', true),"
                        " ('a@m.test', '  Admin ', 'x', 'gerant', true),"
                        " ('p@m.test', 'Paul Girard', 'x', 'mecanicien', false)"
                    )
                )
                migration.upgrade()
                lignes = connexion.execute(
                    text(
                        "SELECT email, prenom, nom, statut FROM utilisateur"
                        " WHERE email LIKE '%@m.test' ORDER BY email"
                    )
                ).all()
                assert [tuple(ligne) for ligne in lignes] == [
                    ("a@m.test", "Admin", "", "actif"),
                    ("k@m.test", "Karim", "B.", "actif"),
                    ("n@m.test", "Nadia", "Benali", "actif"),
                    ("p@m.test", "Paul", "Girard", "desactive"),
                ]
                migration.downgrade()
                retour = connexion.execute(
                    text(
                        "SELECT email, nom, actif FROM utilisateur"
                        " WHERE email LIKE '%@m.test' ORDER BY email"
                    )
                ).all()
                assert [tuple(ligne) for ligne in retour] == [
                    ("a@m.test", "Admin", True),
                    ("k@m.test", "Karim B.", True),
                    ("n@m.test", "Nadia Benali", True),
                    ("p@m.test", "Paul Girard", False),
                ]
                migration.upgrade()
        finally:
            transaction.rollback()


# --- Migration 0017 : sessions des comptes déjà désactivés ----------------------------------------


def test_migration_0017_date_de_coupure_des_comptes_deja_desactives(engine: Engine) -> None:
    """Un compte désactivé avant la migration garde ses anciens cookies refusés après sa
    réactivation : la date de coupure reprend la date de désactivation."""
    chemin = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    fichier = next(chemin.glob("*_0017_*.py"))
    spec = importlib.util.spec_from_file_location(fichier.stem, fichier)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connexion:
        transaction = connexion.begin()
        try:
            contexte = MigrationContext.configure(
                connexion, opts={"target_metadata": Base.metadata}
            )
            with Operations.context(contexte):
                migration.downgrade()
                connexion.execute(
                    text(
                        "INSERT INTO utilisateur"
                        " (email, prenom, nom, mot_de_passe_hash, role, statut, desactive_le)"
                        " VALUES"
                        " ('p@m.test', 'Paul', 'Girard', 'x', 'mecanicien', 'desactive',"
                        "  '2026-09-25 10:00+00'),"
                        " ('k@m.test', 'Karim', 'B.', 'x', 'mecanicien', 'actif', NULL)"
                    )
                )
                migration.upgrade()
                lignes = connexion.execute(
                    text(
                        "SELECT email, sessions_valides_depuis = desactive_le,"
                        " sessions_valides_depuis IS NULL FROM utilisateur"
                        " WHERE email LIKE '%@m.test' ORDER BY email"
                    )
                ).all()
                assert [tuple(ligne) for ligne in lignes] == [
                    ("k@m.test", None, True),
                    ("p@m.test", True, False),
                ]
        finally:
            transaction.rollback()
