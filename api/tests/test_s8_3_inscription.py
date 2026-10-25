"""Story S8.3 — inscription autonome d'un gérant, validée par un gérant actif."""

import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Role, StatutCompte, Utilisateur
from app.schemas.utilisateur import InscriptionEntree
from app.security.hachage import verifier
from app.services import inscription
from tests.conftest import MOT_DE_PASSE_TEST, Horloge, MakeUser

MOT_DE_PASSE = "une phrase de passe solide"
MESSAGE_NEUTRE = (
    "Demande enregistrée. Un gérant du garage doit valider votre compte avant votre première"
    " connexion."
)


def _demande(**champs: Any) -> dict[str, Any]:
    return {
        "prenom": "Inès",
        "nom": "Morel",
        "email": "ines.morel@exemple.test",
        "mot_de_passe": MOT_DE_PASSE,
        **champs,
    }


def _login(c: TestClient, email: str, mot_de_passe: str = MOT_DE_PASSE):  # type: ignore[no-untyped-def]
    return c.post("/auth/login", json={"email": email, "mot_de_passe": mot_de_passe})


def _compte(db: Session, email: str) -> Utilisateur | None:
    return db.scalars(select(Utilisateur).where(Utilisateur.email == email)).one_or_none()


# --- Premier compte du garage ------------------------------------------------------------------


def test_etat_de_l_inscription_public(client: TestClient, make_user: MakeUser) -> None:
    assert client.get("/auth/inscription").json() == {"premier_compte": True}
    make_user(Role.GERANT)
    assert client.get("/auth/inscription").json() == {"premier_compte": False}


def test_un_gerant_desactive_ne_compte_pas_comme_installe(
    client: TestClient, make_user: MakeUser
) -> None:
    make_user(Role.GERANT, actif=False)
    make_user(Role.MECANICIEN)

    assert client.get("/auth/inscription").json() == {"premier_compte": True}


def test_premiere_inscription_active_gerant_et_connecte(
    horloge: Horloge, client_anonyme: TestClient, db: Session
) -> None:
    reponse = client_anonyme.post("/auth/register", json=_demande())

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["compte_actif"] is True
    assert corps["utilisateur"]["role"] == "gerant"
    assert corps["utilisateur"]["nom_affiche"] == "Inès Morel"
    assert "$argon2" not in reponse.text and MOT_DE_PASSE not in reponse.text
    assert get_settings().session_cookie_name in reponse.headers["set-cookie"]
    assert client_anonyme.get("/auth/me").json()["utilisateur"]["email"] == (
        "ines.morel@exemple.test"
    )
    ines = _compte(db, "ines.morel@exemple.test")
    assert ines is not None
    assert (ines.statut, ines.role, ines.valide_le) == (
        StatutCompte.ACTIF,
        Role.GERANT,
        horloge.maintenant,
    )
    assert ines.mot_de_passe_hash.startswith("$argon2id$")


# --- Demandes suivantes : en attente de validation ------------------------------------------------


def test_inscription_suivante_en_attente_avec_message_neutre(
    gerant: Utilisateur, client_anonyme: TestClient, db: Session
) -> None:
    reponse = client_anonyme.post("/auth/register", json=_demande())

    assert reponse.status_code == 202
    assert reponse.json() == {"compte_actif": False, "message": MESSAGE_NEUTRE, "utilisateur": None}
    assert "set-cookie" not in reponse.headers or (
        get_settings().session_cookie_name not in reponse.headers["set-cookie"]
    )
    assert client_anonyme.get("/auth/me").status_code == 401
    ines = _compte(db, "ines.morel@exemple.test")
    assert ines is not None
    assert (ines.statut, ines.role, ines.valide_le) == (StatutCompte.EN_ATTENTE, Role.GERANT, None)


def test_un_compte_en_attente_ne_se_connecte_pas(
    gerant: Utilisateur,
    client_anonyme: TestClient,
    nouveau_client: Callable[[], TestClient],
    db: Session,
) -> None:
    client_anonyme.post("/auth/register", json=_demande())
    anonyme = nouveau_client()

    # La réponse d'une adresse inconnue, avec ou sans le bon mot de passe, jamais de blocage :
    # aucun oracle pour deviner le mot de passe d'une demande en attente (revue du sprint 5).
    for mot_de_passe in ["mauvais mot de passe"] * 6 + [MOT_DE_PASSE]:
        refus = _login(anonyme, "ines.morel@exemple.test", mot_de_passe)
        assert refus.status_code == 401
        assert refus.json() == {
            "code": "identifiants_invalides",
            "message": "Identifiants invalides.",
            "champs": {},
        }
    assert anonyme.get("/auth/me").status_code == 401
    ines = _compte(db, "ines.morel@exemple.test")
    assert ines is not None
    assert (ines.tentatives_echouees, ines.bloque_jusqu_a) == (0, None)


def test_validation_en_mecanicien_puis_connexion_avec_ses_droits(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouveau_client: Callable[[], TestClient],
    db: Session,
) -> None:
    nouveau_client().post("/auth/register", json=_demande())
    ines = _compte(db, "ines.morel@exemple.test")
    assert ines is not None

    reponse = client_gerant.post(f"/utilisateurs/{ines.id}/valider", json={"role": "mecanicien"})

    assert reponse.status_code == 200
    assert (reponse.json()["statut"], reponse.json()["role"]) == ("actif", "mecanicien")
    assert reponse.json()["valide_le"] == "2026-11-02T13:47:00Z"
    db.refresh(ines)
    assert ines.valide_par == gerant.id
    session = nouveau_client()
    assert _login(session, "ines.morel@exemple.test").json()["utilisateur"]["role"] == (
        "mecanicien"
    )
    assert session.get("/clients").status_code == 403
    assert session.get("/ordres").status_code == 200


def test_validation_en_gerant(
    client_gerant: TestClient, make_user: MakeUser, nouveau_client: Callable[[], TestClient]
) -> None:
    attente = make_user(Role.GERANT, statut=StatutCompte.EN_ATTENTE)

    client_gerant.post(f"/utilisateurs/{attente.id}/valider", json={"role": "gerant"})

    session = nouveau_client()
    _login(session, attente.email, MOT_DE_PASSE_TEST)
    assert session.get("/utilisateurs").status_code == 200


def test_validation_exige_un_role(client_gerant: TestClient, make_user: MakeUser) -> None:
    attente = make_user(Role.GERANT, statut=StatutCompte.EN_ATTENTE)

    reponse = client_gerant.post(f"/utilisateurs/{attente.id}/valider", json={"role": "patron"})

    assert reponse.status_code == 422
    assert client_gerant.post(f"/utilisateurs/{attente.id}/valider", json={}).status_code == 422


def test_refus_supprime_la_demande(
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouveau_client: Callable[[], TestClient],
    db: Session,
) -> None:
    nouveau_client().post("/auth/register", json=_demande())
    ines = _compte(db, "ines.morel@exemple.test")
    assert ines is not None
    identifiant = ines.id

    reponse = client_gerant.post(f"/utilisateurs/{identifiant}/refuser")

    assert reponse.status_code == 204
    db.expire_all()
    assert _compte(db, "ines.morel@exemple.test") is None
    refus = _login(nouveau_client(), "ines.morel@exemple.test")
    assert (refus.status_code, refus.json()["message"]) == (401, "Identifiants invalides.")
    assert client_gerant.post(f"/utilisateurs/{identifiant}/refuser").status_code == 404


def test_valider_ou_refuser_un_compte_qui_n_attend_pas_409(
    client_gerant: TestClient, mecanicien: Utilisateur
) -> None:
    for action, corps in (("valider", {"role": "gerant"}), ("refuser", None)):
        reponse = client_gerant.post(f"/utilisateurs/{mecanicien.id}/{action}", json=corps)
        assert reponse.status_code == 409, action
        assert reponse.json()["code"] == "statut_incompatible"
        assert reponse.json()["message"] == "Ce compte n'attend pas de validation."


# --- Aucune information sur les adresses connues -------------------------------------------------


def test_e_mail_deja_connu_meme_reponse_et_rien_ne_change(
    gerant: Utilisateur, mecanicien: Utilisateur, client_anonyme: TestClient, db: Session
) -> None:
    nouvelle = client_anonyme.post("/auth/register", json=_demande())
    total = db.scalar(select(func.count()).select_from(Utilisateur))
    hash_avant = mecanicien.mot_de_passe_hash

    connue = client_anonyme.post(
        "/auth/register",
        json=_demande(email="MECANICIEN@garage.test", prenom="Pirate", nom="Intrus"),
    )

    assert connue.status_code == nouvelle.status_code == 202
    assert connue.json() == nouvelle.json()
    assert db.scalar(select(func.count()).select_from(Utilisateur)) == total
    db.refresh(mecanicien)
    assert (mecanicien.prenom, mecanicien.nom, mecanicien.statut, mecanicien.role) == (
        "Karim",
        "B.",
        StatutCompte.ACTIF,
        Role.MECANICIEN,
    )
    assert mecanicien.mot_de_passe_hash == hash_avant
    assert verifier(mecanicien.mot_de_passe_hash, MOT_DE_PASSE_TEST)
    assert not verifier(mecanicien.mot_de_passe_hash, MOT_DE_PASSE)


def test_s_inscrire_puis_se_connecter_ne_dit_pas_si_l_e_mail_existait(
    gerant: Utilisateur,
    mecanicien: Utilisateur,
    client_anonyme: TestClient,
    nouveau_client: Callable[[], TestClient],
) -> None:
    """Revue du sprint 5 : l'inscrit choisit le mot de passe, puis tente de se connecter avec. Une
    adresse déjà prise et une adresse libre (devenue une demande en attente) répondent pareil."""
    reponses = []
    for email in (mecanicien.email, "adresse.libre@exemple.test"):
        inscription_ = client_anonyme.post(
            "/auth/register", json=_demande(email=email, mot_de_passe="Attaquant-Connu-2027")
        )
        connexion = _login(nouveau_client(), email, "Attaquant-Connu-2027")
        reponses.append(
            (inscription_.status_code, inscription_.json(), connexion.status_code, connexion.json())
        )

    assert reponses[0] == reponses[1]
    assert reponses[0][2:] == (
        401,
        {"code": "identifiants_invalides", "message": "Identifiants invalides.", "champs": {}},
    )


def test_redemander_avec_le_meme_e_mail_ne_change_pas_la_demande(
    gerant: Utilisateur, client_anonyme: TestClient, db: Session
) -> None:
    client_anonyme.post("/auth/register", json=_demande())
    ines = _compte(db, "ines.morel@exemple.test")
    assert ines is not None
    hash_avant = ines.mot_de_passe_hash

    reponse = client_anonyme.post(
        "/auth/register", json=_demande(mot_de_passe="un autre mot de passe")
    )

    assert reponse.status_code == 202
    db.refresh(ines)
    assert ines.mot_de_passe_hash == hash_avant


@pytest.mark.parametrize(
    ("champs", "champ", "message"),
    [
        (
            {"mot_de_passe": "onze-caract"},
            "mot_de_passe",
            "Le mot de passe doit contenir au moins 12 caractères.",
        ),
        ({"email": "pas-un-e-mail"}, "email", "Adresse e-mail invalide."),
        ({"prenom": " "}, "prenom", "Champ obligatoire."),
        ({"nom": "Mo\x00rel"}, "nom", "Caractère non autorisé."),
    ],
)
def test_inscription_refusee_champ_par_champ(
    client_anonyme: TestClient, champs: dict[str, str], champ: str, message: str, db: Session
) -> None:
    reponse = client_anonyme.post("/auth/register", json=_demande(**champs))

    assert reponse.status_code == 422
    assert reponse.json()["champs"][champ] == message
    assert db.scalar(select(func.count()).select_from(Utilisateur)) == 0


def test_inscription_exige_le_jeton_csrf(client: TestClient, db: Session) -> None:
    reponse = client.post("/auth/register", json=_demande())

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "csrf_invalide"
    assert db.scalar(select(func.count()).select_from(Utilisateur)) == 0


def test_limite_des_demandes_en_attente(
    gerant: Utilisateur, mecanicien: Utilisateur, make_user: MakeUser, client_anonyme: TestClient
) -> None:
    limite = get_settings().max_comptes_en_attente
    for _ in range(limite - 1):
        make_user(Role.GERANT, statut=StatutCompte.EN_ATTENTE)
    assert client_anonyme.post("/auth/register", json=_demande()).status_code == 202

    nouvelle = client_anonyme.post("/auth/register", json=_demande(email="autre@exemple.test"))
    connue = client_anonyme.post("/auth/register", json=_demande(email=mecanicien.email))

    assert nouvelle.status_code == connue.status_code == 429
    assert nouvelle.json() == connue.json()
    assert nouvelle.json()["code"] == "trop_de_demandes"


# --- Droits ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "corps"), [("valider", {"role": "mecanicien"}), ("refuser", None)]
)
def test_mecanicien_refuse_sur_valider_et_refuser(
    client_mecanicien: TestClient,
    make_user: MakeUser,
    action: str,
    corps: dict[str, str] | None,
    db: Session,
) -> None:
    attente = make_user(Role.GERANT, statut=StatutCompte.EN_ATTENTE)

    reponse = client_mecanicien.post(f"/utilisateurs/{attente.id}/{action}", json=corps)

    assert reponse.status_code == 403
    db.refresh(attente)
    assert attente.statut == StatutCompte.EN_ATTENTE


# --- Tableau de bord ------------------------------------------------------------------------------


def test_compte_a_valider_dans_a_traiter_maintenant(
    horloge: Horloge, client_gerant: TestClient, make_user: MakeUser
) -> None:
    attente = make_user(
        Role.GERANT,
        prenom="Inès",
        nom="Morel",
        email="ines.morel@exemple.test",
        statut=StatutCompte.EN_ATTENTE,
    )

    elements = client_gerant.get("/tableau-de-bord").json()["a_traiter"]

    assert {
        "type": "compte_a_valider",
        "titre": "Compte à valider",
        "detail": "Inès Morel · ines.morel@exemple.test",
        "ordre_id": None,
        "numero": None,
        "utilisateur_id": attente.id,
    } in elements


# --- Deux premières inscriptions en même temps (deux connexions réelles) -----------------------


def nouvelle_session(engine: Engine) -> Session:
    return Session(engine, autoflush=False, expire_on_commit=False)


EMAILS_COURSE = ("premier.course@exemple.test", "second.course@exemple.test")


@pytest.fixture
def nettoyage_course(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as c:
        c.execute(delete(Utilisateur).where(Utilisateur.email.in_(EMAILS_COURSE)))


def test_deux_premieres_inscriptions_simultanees_un_seul_gerant_actif(
    engine: Engine, nettoyage_course: None
) -> None:
    settings = get_settings()
    maintenant = datetime.now(UTC)
    issue: list[Any] = []

    def entree(email: str) -> InscriptionEntree:
        return InscriptionEntree(
            prenom="Course", nom="Test", email=email, mot_de_passe=MOT_DE_PASSE
        )

    def fil_second() -> None:
        try:
            with nouvelle_session(engine) as s:
                issue.append(
                    inscription.inscrire(s, entree(EMAILS_COURSE[1]), maintenant, settings)
                )
                s.commit()
        except BaseException as exc:
            issue.append(exc)

    with nouvelle_session(engine) as s:
        premier = inscription.inscrire(s, entree(EMAILS_COURSE[0]), maintenant, settings)
        fil = threading.Thread(target=fil_second)
        fil.start()
        fil.join(timeout=0.5)
        attendait = fil.is_alive()
        s.commit()
    fil.join(timeout=10)

    assert not fil.is_alive()
    assert attendait, "la seconde inscription doit attendre le verrou des inscriptions"
    assert premier is not None
    assert issue == [None]
    with nouvelle_session(engine) as s:
        statuts = dict(
            s.execute(
                select(Utilisateur.email, Utilisateur.statut).where(
                    Utilisateur.email.in_(EMAILS_COURSE)
                )
            ).all()
        )
    assert statuts == {
        EMAILS_COURSE[0]: StatutCompte.ACTIF,
        EMAILS_COURSE[1]: StatutCompte.EN_ATTENTE,
    }
