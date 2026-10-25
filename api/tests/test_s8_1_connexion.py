"""Story S8.1 — connexion, blocage après 5 échecs, rôles et CSRF."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Role, StatutCompte, Utilisateur
from app.security.hachage import hacher, verifier
from app.security.jetons import creer_jeton_session, lire_jeton_session
from app.services.donnees_demo import SeedImpossibleError, semer
from app.services.format import NBSP, formater_heure
from app.services.utilisateurs import CompteInvalideError, creer_utilisateur
from tests.conftest import MOT_DE_PASSE_TEST, Horloge, MakeUser

MESSAGE_BLOCAGE = f"Compte bloqué jusqu'à 15{NBSP}h{NBSP}02 après 5 essais erronés."


def _login(c: TestClient, email: str, mot_de_passe: str = MOT_DE_PASSE_TEST):  # type: ignore[no-untyped-def]
    return c.post("/auth/login", json={"email": email, "mot_de_passe": mot_de_passe})


def _echouer(c: TestClient, email: str, fois: int) -> None:
    for _ in range(fois):
        assert _login(c, email, "mauvais-mot-de-passe").status_code in (401, 423)


# --- Connexion -----------------------------------------------------------------------------


def test_connexion_reussie_renvoie_l_utilisateur_et_pose_un_cookie_httponly(
    client_anonyme: TestClient, gerant: Utilisateur, db: Session
) -> None:
    reponse = _login(client_anonyme, gerant.email)

    assert reponse.status_code == 200
    assert reponse.json() == {
        "utilisateur": {
            "id": gerant.id,
            "email": "gerant@garage.test",
            "prenom": "Nadia",
            "nom": "Benali",
            "nom_affiche": "Nadia Benali",
            "role": "gerant",
        }
    }
    cookie = reponse.headers["set-cookie"]
    assert cookie.startswith(f"{get_settings().session_cookie_name}=")
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    assert "Path=/" in cookie
    db.refresh(gerant)
    assert gerant.derniere_connexion is not None


def test_e_mail_insensible_a_la_casse(client_anonyme: TestClient, gerant: Utilisateur) -> None:
    assert _login(client_anonyme, "  GERANT@Garage.Test ").status_code == 200


def test_mauvais_mot_de_passe_401_et_compteur_incremente(
    client_anonyme: TestClient, gerant: Utilisateur, db: Session
) -> None:
    reponse = _login(client_anonyme, gerant.email, "pas-le-bon")

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "identifiants_invalides"
    assert reponse.json()["message"] == "Identifiants invalides."
    assert get_settings().session_cookie_name not in reponse.headers.get("set-cookie", "")
    db.refresh(gerant)
    assert gerant.tentatives_echouees == 1
    assert gerant.bloque_jusqu_a is None


def test_e_mail_inconnu_meme_reponse_que_mauvais_mot_de_passe(
    client_anonyme: TestClient, gerant: Utilisateur
) -> None:
    inconnu = _login(client_anonyme, "personne@garage.test", "peu-importe")
    mauvais = _login(client_anonyme, gerant.email, "peu-importe")

    assert inconnu.status_code == mauvais.status_code == 401
    assert inconnu.json() == mauvais.json()


def test_compte_desactive_refuse_avec_le_message_generique(
    client_anonyme: TestClient, make_user: MakeUser
) -> None:
    inactif = make_user(Role.MECANICIEN, actif=False)

    reponse = _login(client_anonyme, inactif.email)

    assert reponse.status_code == 401
    assert reponse.json()["message"] == "Identifiants invalides."


def test_compte_desactive_jamais_bloque_comme_un_e_mail_inconnu(
    client_anonyme: TestClient, make_user: MakeUser, db: Session
) -> None:
    inactif = make_user(Role.MECANICIEN, actif=False)

    reponses = [_login(client_anonyme, inactif.email, "mauvais-mot-de-passe") for _ in range(6)]
    reponses.append(_login(client_anonyme, inactif.email))

    assert [r.status_code for r in reponses] == [401] * 7
    assert all(r.json()["code"] == "identifiants_invalides" for r in reponses)
    db.refresh(inactif)
    assert inactif.tentatives_echouees == 0
    assert inactif.bloque_jusqu_a is None


def test_cinq_echecs_bloquent_le_compte_avec_l_heure_de_deblocage(
    client_anonyme: TestClient, gerant: Utilisateur, horloge: Horloge, db: Session
) -> None:
    _echouer(client_anonyme, gerant.email, 4)
    db.refresh(gerant)
    assert gerant.tentatives_echouees == 4
    assert gerant.bloque_jusqu_a is None

    reponse = _login(client_anonyme, gerant.email, "mauvais-mot-de-passe")

    assert reponse.status_code == 423
    corps = reponse.json()
    assert corps["code"] == "compte_bloque"
    # 13 h 47 UTC + 15 min = 14 h 02 UTC = 15 h 02 à Paris (heure d'hiver).
    assert corps["message"] == MESSAGE_BLOCAGE
    assert corps["bloque_jusqu_a"] == "2026-11-02T14:02:00+00:00"
    db.refresh(gerant)
    assert gerant.bloque_jusqu_a == datetime(2026, 11, 2, 14, 2, tzinfo=UTC)


def test_bon_mot_de_passe_refuse_pendant_le_blocage_sans_le_prolonger(
    client_anonyme: TestClient, gerant: Utilisateur, horloge: Horloge, db: Session
) -> None:
    _echouer(client_anonyme, gerant.email, 5)
    horloge.avancer(minutes=14)

    bon = _login(client_anonyme, gerant.email)
    mauvais = _login(client_anonyme, gerant.email, "encore-faux")

    assert bon.status_code == 423
    assert bon.json()["message"] == MESSAGE_BLOCAGE
    assert mauvais.status_code == 423
    db.refresh(gerant)
    assert gerant.bloque_jusqu_a == datetime(2026, 11, 2, 14, 2, tzinfo=UTC)


def test_apres_quinze_minutes_connexion_possible_et_compteur_remis_a_zero(
    client_anonyme: TestClient, gerant: Utilisateur, horloge: Horloge, db: Session
) -> None:
    _echouer(client_anonyme, gerant.email, 5)
    horloge.avancer(minutes=15)

    reponse = _login(client_anonyme, gerant.email)

    assert reponse.status_code == 200
    db.refresh(gerant)
    assert gerant.tentatives_echouees == 0
    assert gerant.bloque_jusqu_a is None
    assert gerant.derniere_connexion == horloge.maintenant


def test_apres_expiration_du_blocage_le_compteur_repart_de_zero(
    client_anonyme: TestClient, gerant: Utilisateur, horloge: Horloge, db: Session
) -> None:
    _echouer(client_anonyme, gerant.email, 5)
    horloge.avancer(minutes=16)

    reponse = _login(client_anonyme, gerant.email, "toujours-faux")

    assert reponse.status_code == 401
    db.refresh(gerant)
    assert gerant.tentatives_echouees == 1
    assert gerant.bloque_jusqu_a is None


def test_une_connexion_reussie_remet_le_compteur_a_zero(
    client_anonyme: TestClient, gerant: Utilisateur, db: Session
) -> None:
    _echouer(client_anonyme, gerant.email, 3)

    assert _login(client_anonyme, gerant.email).status_code == 200
    db.refresh(gerant)
    assert gerant.tentatives_echouees == 0


# --- Session -------------------------------------------------------------------------------


def test_me_renvoie_l_utilisateur_connecte(client_mecanicien: TestClient) -> None:
    reponse = client_mecanicien.get("/auth/me")

    assert reponse.status_code == 200
    assert reponse.json()["utilisateur"]["role"] == "mecanicien"
    assert reponse.json()["utilisateur"]["nom_affiche"] == "Karim B."


def test_sans_session_401(client: TestClient) -> None:
    for chemin in ("/auth/me", "/devis", "/factures"):
        reponse = client.get(chemin)
        assert reponse.status_code == 401, chemin
        assert reponse.json()["code"] == "non_authentifie"


def test_jeton_falsifie_401(client: TestClient, gerant: Utilisateur) -> None:
    autre_cle = get_settings().model_copy(update={"secret_key": "x" * 48})
    faux = creer_jeton_session(gerant.id, Role.GERANT, datetime.now(UTC), autre_cle)
    client.cookies.set(get_settings().session_cookie_name, faux)

    assert client.get("/auth/me").status_code == 401


def test_session_expiree_401(client_gerant: TestClient, horloge: Horloge) -> None:
    horloge.maintenant = datetime.now(UTC)
    horloge.avancer(minutes=get_settings().session_duration_minutes + 1)

    assert client_gerant.get("/auth/me").status_code == 401


def test_compte_desactive_apres_connexion_401(
    client_gerant: TestClient, gerant: Utilisateur, db: Session
) -> None:
    gerant.statut = StatutCompte.DESACTIVE
    db.flush()

    assert client_gerant.get("/auth/me").status_code == 401


def test_deconnexion_efface_la_session(client_gerant: TestClient) -> None:
    assert client_gerant.get("/auth/me").status_code == 200

    reponse = client_gerant.post("/auth/logout")

    assert reponse.status_code == 204
    assert get_settings().session_cookie_name not in client_gerant.cookies
    assert client_gerant.get("/auth/me").status_code == 401


# --- Rôles ---------------------------------------------------------------------------------


@pytest.mark.parametrize("chemin", ["/devis", "/factures"])
def test_mecanicien_refuse_sur_devis_et_factures(
    client_mecanicien: TestClient, chemin: str
) -> None:
    reponse = client_mecanicien.get(chemin)

    assert reponse.status_code == 403
    assert reponse.json() == {
        "code": "interdit",
        "message": "Accès refusé pour votre rôle.",
        "champs": {},
    }


@pytest.mark.parametrize(
    ("chemin", "attendu"),
    [
        ("/devis", {"elements": [], "total": 0, "page": 1, "taille": 50}),
        ("/factures", {"elements": [], "total": 0, "page": 1, "taille": 50}),
    ],
)
def test_gerant_accede_aux_devis_et_factures(
    client_gerant: TestClient, chemin: str, attendu: object
) -> None:
    reponse = client_gerant.get(chemin)

    assert reponse.status_code == 200
    assert reponse.json() == attendu


# --- CSRF ----------------------------------------------------------------------------------


def test_post_sans_jeton_csrf_refuse(client: TestClient, gerant: Utilisateur) -> None:
    reponse = _login(client, gerant.email)

    assert reponse.status_code == 403
    assert reponse.json() == {
        "code": "csrf_invalide",
        "message": "Jeton de sécurité manquant ou invalide. Rechargez la page.",
        "champs": {},
    }


def test_post_avec_un_jeton_different_du_cookie_refuse(
    client_anonyme: TestClient, gerant: Utilisateur
) -> None:
    client_anonyme.headers[get_settings().csrf_header_name] = "jeton-invente"

    assert _login(client_anonyme, gerant.email).status_code == 403


def test_deconnexion_sans_jeton_csrf_refusee(client_gerant: TestClient) -> None:
    del client_gerant.headers[get_settings().csrf_header_name]

    assert client_gerant.post("/auth/logout").status_code == 403
    assert client_gerant.get("/auth/me").status_code == 200


def test_get_csrf_pose_un_cookie_lisible_et_le_conserve(client: TestClient) -> None:
    premiere = client.get("/auth/csrf")
    cookie = premiere.headers["set-cookie"]
    jeton = premiere.json()["jeton"]

    assert cookie.startswith(f"{get_settings().csrf_cookie_name}={jeton}")
    assert "HttpOnly" not in cookie
    assert "samesite=lax" in cookie.lower()
    assert len(jeton) >= 43  # 32 octets en base64 url
    assert client.get("/auth/csrf").json()["jeton"] == jeton


# --- Briques de sécurité -------------------------------------------------------------------


def test_hachage_argon2id() -> None:
    h = hacher("un-mot-de-passe-long")

    assert h.startswith("$argon2id$")
    assert verifier(h, "un-mot-de-passe-long")
    assert not verifier(h, "autre")
    assert not verifier("pas-un-hash", "autre")


def test_jeton_de_session_aller_retour_et_expiration() -> None:
    settings = get_settings()
    maintenant = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
    jeton = creer_jeton_session(7, Role.MECANICIEN, maintenant, settings)

    session = lire_jeton_session(jeton, maintenant, settings)
    assert session is not None
    assert (session.utilisateur_id, session.role) == (7, Role.MECANICIEN)
    plus_tard = maintenant.replace(hour=18, minute=1)
    assert lire_jeton_session(jeton, plus_tard, settings) is None
    assert lire_jeton_session(jeton + "x", maintenant, settings) is None


def test_heure_formatee_a_paris() -> None:
    assert formater_heure(datetime(2026, 11, 2, 14, 2, tzinfo=UTC)) == f"15{NBSP}h{NBSP}02"
    assert formater_heure(datetime(2026, 7, 1, 7, 5, tzinfo=UTC)) == f"9{NBSP}h{NBSP}05"


# --- Comptes et jeu de démonstration -------------------------------------------------------


def _reglages_demo():  # type: ignore[no-untyped-def]
    return get_settings().model_copy(
        update={
            "demo_password_gerant": "demo-gerant-motdepasse",
            "demo_password_mecanicien": "demo-meca-motdepasse",
        }
    )


def test_seed_cree_les_comptes_de_demo_et_reste_idempotent(db: Session) -> None:
    premier = semer(db, _reglages_demo())
    nadia = db.scalars(select(Utilisateur).where(Utilisateur.email == "nadia@garage.test")).one()
    nadia.tentatives_echouees = 5
    nadia.bloque_jusqu_a = datetime(2099, 1, 1, tzinfo=UTC)
    db.flush()
    second = semer(db, _reglages_demo())
    # 4 comptes, 8 véhicules, 10 ordres de travail et 3 rendez-vous à venir de la journée,
    # 6 devis (dont celui de la Clio, sprint 4), 3 factures et leurs 3 paiements.
    assert len(premier) == len(second) == 37

    assert all(ligne.startswith("Créé") for ligne in premier)
    assert all(ligne.startswith("À jour") for ligne in second)
    total = db.scalar(select(func.count()).select_from(Utilisateur))
    assert total == 4
    db.refresh(nadia)
    assert (nadia.prenom, nadia.nom, nadia.role) == ("Nadia", "Benali", Role.GERANT)
    # Relancer le seed débloque un compte de démonstration bloqué.
    assert (nadia.tentatives_echouees, nadia.bloque_jusqu_a) == (0, None)
    assert verifier(nadia.mot_de_passe_hash, "demo-gerant-motdepasse")
    mecaniciens = db.scalars(
        select(Utilisateur.email).where(Utilisateur.role == Role.MECANICIEN)
    ).all()
    assert sorted(mecaniciens) == ["karim@garage.test", "lucas@garage.test", "sophie@garage.test"]


def test_seed_refuse_sans_mots_de_passe(db: Session) -> None:
    reglages = get_settings().model_copy(update={"demo_password_gerant": ""})

    with pytest.raises(SeedImpossibleError):
        semer(db, reglages)


def test_creation_de_compte_exige_douze_caracteres_et_un_e_mail_libre(db: Session) -> None:
    with pytest.raises(CompteInvalideError, match="12 caractères"):
        creer_utilisateur(
            db,
            email="a@garage.test",
            prenom="A",
            nom="A",
            role=Role.MECANICIEN,
            mot_de_passe="court",
        )
    creer_utilisateur(
        db, email="a@garage.test", prenom="A", nom="A", role=Role.MECANICIEN, mot_de_passe="x" * 12
    )
    with pytest.raises(CompteInvalideError, match="existe déjà"):
        creer_utilisateur(
            db, email="A@garage.test", prenom="B", nom="B", role=Role.GERANT, mot_de_passe="y" * 12
        )
