"""Schémas de la recherche du gérant (story S1.3)."""

from datetime import datetime

from pydantic import BaseModel

from app.models.ordre_travail import StatutOT
from app.services.recherche import Resultats


class ClientTrouve(BaseModel):
    id: int
    nom: str
    prenom: str | None
    telephone: str
    nb_vehicules: int


class Proprietaire(BaseModel):
    id: int
    nom: str
    prenom: str | None


class VehiculeTrouve(BaseModel):
    id: int
    immatriculation: str
    marque: str
    modele: str
    proprietaire: Proprietaire


class OrdreTrouve(BaseModel):
    id: int
    numero: str
    statut: StatutOT
    immatriculation: str
    marque: str
    modele: str


class ClientFacture(BaseModel):
    nom: str
    prenom: str | None


class FactureTrouvee(BaseModel):
    id: int
    numero: str
    emise_le: datetime
    total_ttc_centimes: int
    # Client tel qu'il figure sur la facture (copie figée à l'émission).
    client: ClientFacture


class RechercheSortie(BaseModel):
    q: str
    clients: list[ClientTrouve]
    vehicules: list[VehiculeTrouve]
    ordres: list[OrdreTrouve]
    factures: list[FactureTrouvee]


def sortie_recherche(q: str, resultats: Resultats) -> RechercheSortie:
    return RechercheSortie(
        q=q,
        clients=[
            ClientTrouve(
                id=t.client.id,
                nom=t.client.nom,
                prenom=t.client.prenom,
                telephone=t.client.telephone,
                nb_vehicules=t.nb_vehicules,
            )
            for t in resultats.clients
        ],
        vehicules=[
            VehiculeTrouve(
                id=v.id,
                immatriculation=v.immatriculation,
                marque=v.marque,
                modele=v.modele,
                proprietaire=Proprietaire(id=v.client.id, nom=v.client.nom, prenom=v.client.prenom),
            )
            for v in resultats.vehicules
        ],
        ordres=[
            OrdreTrouve(
                id=o.id,
                numero=o.numero,
                statut=o.statut,
                immatriculation=o.vehicule.immatriculation,
                marque=o.vehicule.marque,
                modele=o.vehicule.modele,
            )
            for o in resultats.ordres
        ],
        factures=[
            FactureTrouvee(
                id=f.id,
                numero=f.numero,
                emise_le=f.emise_le,
                total_ttc_centimes=f.total_ttc_centimes,
                client=ClientFacture.model_validate(f.client_fige),
            )
            for f in resultats.factures
        ],
    )
