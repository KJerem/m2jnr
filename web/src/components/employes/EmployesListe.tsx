"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ButtonLink } from "@/components/ui/Button";
import { ChampRechercheListe } from "@/components/ui/ChampRechercheListe";
import { Icon } from "@/components/ui/Icon";
import { Pagination } from "@/components/ui/Pagination";
import { useFiltresAdresse } from "@/lib/adresse";
import { ApiError, apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { lienEmployes, LIBELLE_ROLE_PLURIEL, LIBELLE_STATUT_COMPTE, libelleDerniereConnexion, lireRole, lireStatut, requeteEmployes, ROLES, STATUTS_COMPTE, type Employe, type FiltresEmployes } from "@/lib/employes";
import { numeroDePage, texteDeRecherche, type Recherche } from "@/lib/pages";
import { LIBELLE_ROLE } from "@/lib/session";
import { BadgeCompte } from "./BadgeCompte";

export const TAILLE_EMPLOYES = 20;

const lireEmployes = (p: Recherche): FiltresEmployes => ({ q: texteDeRecherche(p.q), role: lireRole(p.role), statut: lireStatut(p.statut), page: numeroDePage(p.page) });

/** Message de liste vide selon les filtres. */
export function messageAucunEmploye(filtres: FiltresEmployes): string {
  if (filtres.q) return `Aucun employé ne correspond à « ${filtres.q} ».`;
  if (filtres.role || filtres.statut) return "Aucun employé dans ce filtre.";
  return "Aucun employé pour l'instant.";
}

/**
 * Liste des comptes de l'équipe (story S8.2) : recherche (prénom, nom, e-mail), filtres par
 * rôle et par statut, comptes en attente de validation d'abord. Recherche et filtres suivent
 * l'adresse (?q=, ?role=, ?statut=) sans recharger la page et repartent de la page 1 ; le
 * retour arrière et le lien « Employés » du menu les reprennent de l'adresse.
 */
export function EmployesListe({ initial }: { initial: FiltresEmployes }) {
  const [filtres, changerFiltres] = useFiltresAdresse("/employes", initial, lireEmployes, lienEmployes);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["utilisateurs", "liste", filtres],
    queryFn: ({ signal }) => apiFetch<Page<Employe>>(requeteEmployes(filtres, TAILLE_EMPLOYES), { signal }),
    placeholderData: keepPreviousData,
  });
  const erreurRecherche = isError && error instanceof ApiError && error.status === 422 ? (error.champs.q ?? error.message) : null;

  function changer(modif: Partial<FiltresEmployes>) {
    changerFiltres({ ...filtres, ...modif, page: 1 });
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Employés</h1>
          <p className="caption sub">Comptes de l&apos;équipe : création, rôle, accès à l&apos;application.</p>
        </div>
        <ButtonLink href="/employes/nouveau" variant="primary">
          <Icon name="plus" />
          Nouvel employé
        </ButtonLink>
      </header>

      <div className="liste-filtres">
        <ChampRechercheListe
          libelle="Rechercher un employé"
          placeholder="Prénom, nom ou e-mail"
          valeurInitiale={filtres.q}
          onRecherche={(q) => changer({ q })}
          total={data && filtres.q ? data.total : null}
          erreurServeur={erreurRecherche}
          className="recherche-liste"
        />
        <div className="chips" role="group" aria-label="Filtrer par rôle">
          <button type="button" className="chip" aria-pressed={filtres.role === null} onClick={() => changer({ role: null })}>
            Tous les rôles
          </button>
          {ROLES.map((r) => (
            <button key={r} type="button" className="chip" aria-pressed={filtres.role === r} onClick={() => changer({ role: r })}>
              {LIBELLE_ROLE_PLURIEL[r]}
            </button>
          ))}
        </div>
        <div className="chips" role="group" aria-label="Filtrer par statut">
          <button type="button" className="chip" aria-pressed={filtres.statut === null} onClick={() => changer({ statut: null })}>
            Tous les statuts
          </button>
          {STATUTS_COMPTE.map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={filtres.statut === s} onClick={() => changer({ statut: s })}>
              {LIBELLE_STATUT_COMPTE[s]}
            </button>
          ))}
        </div>
      </div>

      <section className="panel" aria-labelledby="titre-liste-employes">
        <h2 id="titre-liste-employes" className="sr-only">
          Liste des employés
        </h2>
        {isPending ? (
          <p className="empty" role="status">
            Chargement des employés…
          </p>
        ) : isError && !erreurRecherche ? (
          <p className="empty danger-text" role="alert">
            {error.message}
          </p>
        ) : !data || data.elements.length === 0 ? (
          <p className="empty">{messageAucunEmploye(filtres)}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Nom</th>
                  <th scope="col">E-mail</th>
                  <th scope="col">Rôle</th>
                  <th scope="col">Statut</th>
                  <th scope="col">Dernière connexion</th>
                </tr>
              </thead>
              <tbody>
                {data.elements.map((employe) => (
                  <tr key={employe.id}>
                    <td>
                      <Link href={`/employes/${employe.id}`} className="table-link strong">
                        {employe.nom_affiche}
                      </Link>
                    </td>
                    <td className="cellule-email">{employe.email}</td>
                    <td>{LIBELLE_ROLE[employe.role]}</td>
                    <td>
                      <BadgeCompte employe={employe} />
                    </td>
                    <td className="nowrap">{libelleDerniereConnexion(employe)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {data && data.total > 0 ? (
        <Pagination page={filtres.page} taille={TAILLE_EMPLOYES} total={data.total} libelle={data.total > 1 ? "employés" : "employé"} lien={(p) => lienEmployes({ ...filtres, page: p })} />
      ) : null}
    </>
  );
}
