"use client";

import { useQuery } from "@tanstack/react-query";
import { CarteOrdre } from "@/components/ordres/CarteOrdre";
import { useSession } from "@/components/session/useSession";
import { TableauDeBord } from "@/components/tableau-de-bord/TableauDeBord";
import { apiFetch } from "@/lib/api";
import type { Page } from "@/lib/clients";
import { prenom, trierCartes, type OrdreResume } from "@/lib/ordres";

/** « Mes travaux » : OT affectés au mécanicien et pas encore livrés, vers la vue tablette. */
export function MesTravaux({ mecanicienId, nom }: { mecanicienId: number; nom: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["ordres", "mes-travaux", mecanicienId],
    queryFn: ({ signal }) =>
      apiFetch<Page<OrdreResume>>(`/ordres?mecanicien_id=${mecanicienId}&statut=a_faire&statut=en_cours&statut=termine&taille=100`, { signal }),
    refetchInterval: 60_000,
  });

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Mes travaux</h1>
          <p className="caption sub">Bonjour {prenom(nom)}. Touchez une carte pour ouvrir la vue tablette.</p>
        </div>
      </header>
      {isPending ? (
        <p className="muted" role="status">
          Chargement de vos travaux…
        </p>
      ) : isError ? (
        <p className="callout callout-danger" role="alert">
          {error.message}
        </p>
      ) : data.elements.length === 0 ? (
        <p className="panel empty">Aucun travail ne vous est affecté pour l&apos;instant.</p>
      ) : (
        <ul className="cartes-grille">
          {trierCartes(data.elements).map((ordre) => (
            <li key={ordre.id}>
              <CarteOrdre ordre={ordre} href={`/ordres/${ordre.id}/tablette`} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** Accueil : « Mes travaux » pour le mécanicien, tableau de bord de l'atelier pour le gérant. */
export function Accueil() {
  const { utilisateur } = useSession();
  if (!utilisateur) return null;
  if (utilisateur.role === "mecanicien") return <MesTravaux mecanicienId={utilisateur.id} nom={utilisateur.nom_affiche} />;
  return <TableauDeBord />;
}
