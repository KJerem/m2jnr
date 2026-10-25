"""Revue du sprint 2 — requêtes simultanées sur un même OT ou un même véhicule.

Ces tests valident réellement leurs transactions sur deux connexions (et non dans la
transaction annulée de la fixture `db`) : c'est la seule façon de vérifier un verrou
SELECT … FOR UPDATE. Les données créées sont supprimées à la fin de chaque test.
"""

import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import (
    Client,
    Compteur,
    OrdreTravail,
    Role,
    StatutOT,
    Utilisateur,
    Vehicule,
)
from app.routers import ordres as routes_ordres
from app.schemas.ordre import OrdreEntree, OrdreModification
from app.services import ordres as service
from app.services import transitions

ANNEE = 2092
MAINTENANT = datetime(2026, 11, 2, 13, 47, tzinfo=UTC)
KILOMETRAGE_INITIAL = 97_340


def nouvelle_session(engine: Engine) -> Session:
    """Mêmes options que la session d'une requête (app.db.SessionLocal)."""
    return Session(engine, autoflush=False, expire_on_commit=False)


@dataclass(frozen=True)
class Donnees:
    gerant_id: int
    mecanicien_id: int
    vehicule_id: int


@pytest.fixture
def donnees(engine: Engine) -> Iterator[Donnees]:
    with nouvelle_session(engine) as s:
        gerant = Utilisateur(
            email="gerant.concurrence@garage.test",
            prenom="Nadia",
            nom="Concurrence",
            role=Role.GERANT,
            mot_de_passe_hash="x",
        )
        mecanicien = Utilisateur(
            email="meca.concurrence@garage.test",
            prenom="Karim",
            nom="Concurrence",
            role=Role.MECANICIEN,
            mot_de_passe_hash="x",
        )
        client = Client(nom="Concurrence", prenom="Claire", telephone="0612483075")
        s.add_all([gerant, mecanicien, client])
        s.flush()
        vehicule = Vehicule(
            client_id=client.id,
            immatriculation="ZZ-092-ZZ",
            marque="Volkswagen",
            modele="Golf 7",
            kilometrage=KILOMETRAGE_INITIAL,
        )
        s.add(vehicule)
        s.commit()
        ids = Donnees(gerant.id, mecanicien.id, vehicule.id)
        client_id = client.id
    yield ids
    with engine.begin() as c:
        c.execute(delete(OrdreTravail).where(OrdreTravail.vehicule_id == ids.vehicule_id))
        c.execute(delete(Compteur).where(Compteur.annee == ANNEE))
        c.execute(delete(Vehicule).where(Vehicule.id == ids.vehicule_id))
        c.execute(delete(Client).where(Client.id == client_id))
        c.execute(delete(Utilisateur).where(Utilisateur.id.in_([ids.gerant_id, ids.mecanicien_id])))


def ouvrir(engine: Engine, d: Donnees, **champs: Any) -> int:
    """OT validé en base, avec une tâche terminée et passé « En cours »."""
    with nouvelle_session(engine) as s:
        gerant = s.get_one(Utilisateur, d.gerant_id)
        entree = OrdreEntree.model_validate(
            {
                "vehicule_id": d.vehicule_id,
                "demande_client": "Sonde de concurrence.",
                "taches": [{"libelle": "A", "duree_prevue_minutes": 30}],
                **champs,
            }
        )
        ordre = service.creer_ordre(s, entree, gerant, MAINTENANT, ANNEE)
        transitions.changer_statut(ordre, StatutOT.EN_COURS, gerant, MAINTENANT)
        transitions.terminer_tache(ordre, ordre.taches[0].id, gerant, MAINTENANT)
        s.commit()
        return ordre.id


def en_parallele(
    engine: Engine, premiere: Callable[[Session], None], seconde: Callable[[Session], Any]
) -> tuple[bool, list[Any]]:
    """`premiere` s'exécute et garde sa transaction ouverte ; `seconde` démarre dans un autre
    fil. Renvoie (la seconde attendait-elle la première ?, [résultat ou exception])."""
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


def ajout_de_tache(ordre_id: int, d: Donnees) -> Callable[[Session], Any]:
    def _put(s: Session) -> Any:
        ordre = s.get_one(OrdreTravail, ordre_id)
        entree = OrdreModification.model_validate(
            {
                "demande_client": "Sonde de concurrence.",
                "taches": [
                    {"id": t.id, "libelle": t.libelle, "duree_prevue_minutes": 30}
                    for t in ordre.taches
                ]
                + [{"libelle": "B ajoutée", "duree_prevue_minutes": 30}],
            }
        )
        s.expunge_all()
        gerant = s.get_one(Utilisateur, d.gerant_id)
        return routes_ordres.modifier(ordre_id, entree, s, gerant, MAINTENANT)

    return _put


# --- PUT /ordres/{id} contre un changement de statut ----------------------------------------


def test_modification_attend_le_passage_a_pret_et_refuse_la_nouvelle_tache(
    engine: Engine, donnees: Donnees
) -> None:
    ordre_id = ouvrir(engine, donnees)

    def passer_a_pret(s: Session) -> None:
        ordre = service.obtenir_ordre(s, ordre_id, verrouiller=True)
        meca = s.get_one(Utilisateur, donnees.mecanicien_id)
        transitions.changer_statut(ordre, StatutOT.TERMINE, meca, MAINTENANT)
        s.flush()

    attendait, issue = en_parallele(engine, passer_a_pret, ajout_de_tache(ordre_id, donnees))

    assert attendait, "le PUT doit attendre le verrou de l'OT"
    assert isinstance(issue[0], AppError)
    assert (issue[0].status_code, issue[0].code) == (409, "ordre_pret")
    with nouvelle_session(engine) as s:
        ordre = s.get_one(OrdreTravail, ordre_id)
        assert ordre.statut == StatutOT.TERMINE
        assert [t.terminee for t in ordre.taches] == [True]


def test_modification_attend_la_livraison_et_refuse_de_modifier_un_ot_livre(
    engine: Engine, donnees: Donnees
) -> None:
    ordre_id = ouvrir(engine, donnees)
    with nouvelle_session(engine) as s:
        ordre = service.obtenir_ordre(s, ordre_id, verrouiller=True)
        gerant = s.get_one(Utilisateur, donnees.gerant_id)
        transitions.changer_statut(ordre, StatutOT.TERMINE, gerant, MAINTENANT)
        s.commit()

    def livrer(s: Session) -> None:
        ordre = service.obtenir_ordre(s, ordre_id, verrouiller=True)
        gerant = s.get_one(Utilisateur, donnees.gerant_id)
        transitions.changer_statut(ordre, StatutOT.LIVRE, gerant, MAINTENANT)
        s.flush()

    def modifier_la_demande(s: Session) -> Any:
        gerant = s.get_one(Utilisateur, donnees.gerant_id)
        entree = OrdreModification.model_validate({"demande_client": "Modifiée trop tard."})
        return routes_ordres.modifier(ordre_id, entree, s, gerant, MAINTENANT)

    attendait, issue = en_parallele(engine, livrer, modifier_la_demande)

    assert attendait
    assert isinstance(issue[0], AppError)
    assert (issue[0].status_code, issue[0].code) == (409, "ordre_livre")
    with nouvelle_session(engine) as s:
        assert s.get_one(OrdreTravail, ordre_id).demande_client == "Sonde de concurrence."


def test_suppression_d_une_tache_pendant_qu_on_la_coche_sans_erreur_500(
    engine: Engine, donnees: Donnees
) -> None:
    ordre_id = ouvrir(
        engine,
        donnees,
        taches=[
            {"libelle": "A", "duree_prevue_minutes": 30},
            {"libelle": "B", "duree_prevue_minutes": 30},
        ],
    )
    with nouvelle_session(engine) as s:
        tache_a, tache_b = (t.id for t in s.get_one(OrdreTravail, ordre_id).taches)

    def supprimer_b(s: Session) -> None:
        gerant = s.get_one(Utilisateur, donnees.gerant_id)
        entree = OrdreModification.model_validate(
            {
                "demande_client": "Sonde de concurrence.",
                "taches": [{"id": tache_a, "libelle": "A", "duree_prevue_minutes": 30}],
            }
        )
        routes_ordres.modifier(ordre_id, entree, s, gerant, MAINTENANT)

    def cocher_b(s: Session) -> Any:
        meca = s.get_one(Utilisateur, donnees.mecanicien_id)
        return routes_ordres.terminer_tache(ordre_id, tache_b, s, meca, MAINTENANT)

    attendait, issue = en_parallele(engine, supprimer_b, cocher_b)

    assert attendait
    assert isinstance(issue[0], AppError)
    assert (issue[0].status_code, issue[0].code) == (404, "introuvable")


# --- Deux ouvertures simultanées sur un même véhicule ---------------------------------------


def test_deux_ouvertures_simultanees_ne_font_pas_reculer_le_compteur(
    engine: Engine, donnees: Donnees
) -> None:
    def ouvrir_avec(kilometrage: int) -> Callable[[Session], Any]:
        def _creer(s: Session) -> Any:
            gerant = s.get_one(Utilisateur, donnees.gerant_id)
            entree = OrdreEntree.model_validate(
                {
                    "vehicule_id": donnees.vehicule_id,
                    "demande_client": f"Sonde {kilometrage} km.",
                    "kilometrage_entree": kilometrage,
                }
            )
            return service.creer_ordre(s, entree, gerant, MAINTENANT, ANNEE)

        return _creer

    attendait, issue = en_parallele(
        engine,
        ouvrir_avec(KILOMETRAGE_INITIAL + 80),
        ouvrir_avec(KILOMETRAGE_INITIAL + 70),
    )

    assert attendait
    # La seconde lit le compteur validé par la première : 70 km de plus que l'ancien relevé,
    # mais 10 km de moins que le nouveau → refusée, sur le champ.
    assert isinstance(issue[0], AppError)
    assert issue[0].status_code == 422
    assert set(issue[0].champs) == {"kilometrage_entree"}
    with nouvelle_session(engine) as s:
        assert s.get_one(Vehicule, donnees.vehicule_id).kilometrage == KILOMETRAGE_INITIAL + 80
