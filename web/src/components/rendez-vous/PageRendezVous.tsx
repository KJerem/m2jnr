"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { rafraichirApresOrdre } from "@/components/ordres/actions";
import { cleOrdre, useVehicules } from "@/components/ordres/donnees";
import { Button } from "@/components/ui/Button";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import { formatDateCourte, formatHeure } from "@/lib/format";
import { modele, type OrdreDetail } from "@/lib/ordres";
import { formatCreneau, formatJour, grouperParJour, type Pont, type RendezVous, type RendezVousEntree } from "@/lib/rendezvous";
import { BADGE_OT, LIBELLE_OT } from "@/lib/statuts";
import { RendezVousForm } from "./RendezVousForm";

export function usePonts() {
  return useQuery({
    queryKey: ["ponts"],
    queryFn: ({ signal }) => apiFetch<Pont[]>("/ponts", { signal }),
    staleTime: 10 * 60_000,
  });
}

function creerRendezVous(entree: RendezVousEntree) {
  return apiFetch<RendezVous>("/rendez-vous", { method: "POST", body: entree });
}

/** Rendez-vous (gérant) : prise de rendez-vous et liste à venir, groupée par jour. */
export function PageRendezVous() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const notifier = useToast();
  const vehicules = useVehicules();
  const ponts = usePonts();
  const liste = useQuery({
    queryKey: ["rendez-vous", "a-venir"],
    queryFn: ({ signal }) => apiFetch<RendezVous[]>("/rendez-vous", { signal }),
  });
  const ouvrir = useMutation({
    mutationFn: (rdv: RendezVous) => apiFetch<OrdreDetail>(`/rendez-vous/${rdv.id}/ordre`, { method: "POST" }),
    onSuccess: (ordre) => {
      queryClient.setQueryData(cleOrdre(ordre.id), ordre);
      void rafraichirApresOrdre(queryClient);
      notifier({ type: "success", message: `${ordre.numero} ouvert.` });
      router.push(`/ordres/${ordre.id}`);
    },
    onError: (erreur) => notifier({ type: "error", message: erreur.message }),
  });

  const erreurFormulaire = vehicules.error ?? ponts.error;

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Rendez-vous</h1>
          <p className="caption sub">Un créneau par pont : deux rendez-vous ne se chevauchent jamais sur le même pont.</p>
        </div>
      </header>

      <section className="panel" aria-labelledby="titre-nouveau-rdv">
        <div className="panel-head">
          <h2 id="titre-nouveau-rdv">Nouveau rendez-vous</h2>
        </div>
        <div className="panel-body">
          {erreurFormulaire ? (
            <p className="callout callout-danger" role="alert">
              {erreurFormulaire.message}
            </p>
          ) : !vehicules.data || !ponts.data ? (
            <p className="muted" role="status">
              Chargement du formulaire…
            </p>
          ) : (
            <RendezVousForm
              vehicules={vehicules.data}
              ponts={ponts.data}
              envoyer={creerRendezVous}
              onSucces={(rdv) => {
                void queryClient.invalidateQueries({ queryKey: ["rendez-vous"] });
                void queryClient.invalidateQueries({ queryKey: ["planning"] });
                notifier({ type: "success", message: `Rendez-vous enregistré : ${formatDateCourte(rdv.debut)} à ${formatHeure(rdv.debut)}, ${rdv.pont.nom}.` });
              }}
            />
          )}
        </div>
      </section>

      <section className="panel" aria-labelledby="titre-liste-rdv">
        <div className="panel-head">
          <h2 id="titre-liste-rdv">À venir</h2>
          <Link href="/planning">Voir le planning du jour</Link>
        </div>
        {liste.isPending ? (
          <p className="empty" role="status">
            Chargement des rendez-vous…
          </p>
        ) : liste.isError ? (
          <p className="empty danger-text" role="alert">
            {liste.error.message}
          </p>
        ) : liste.data.length === 0 ? (
          <p className="empty">Aucun rendez-vous à venir.</p>
        ) : (
          <div className="rdv-jours">
            {grouperParJour(liste.data).map((groupe) => (
              <section key={groupe.jour} aria-labelledby={`jour-${groupe.jour}`} className="rdv-jour">
                <h3 id={`jour-${groupe.jour}`} className="rdv-jour-titre">
                  {formatJour(groupe.jour)}
                </h3>
                <ul className="rdv-liste">
                  {groupe.rendezVous.map((rdv) => (
                    <li key={rdv.id} className="rdv-ligne">
                      <span className="rdv-creneau num">{formatCreneau(rdv.debut, rdv.fin)}</span>
                      <span className="rdv-pont">{rdv.pont.nom}</span>
                      <Plate number={rdv.vehicule.immatriculation} />
                      <span className="rdv-texte">
                        <span className="strong">{modele(rdv.vehicule)}</span>
                        <span className="caption">{rdv.motif}</span>
                      </span>
                      <span className="rdv-action">
                        {rdv.ordre ? (
                          <Link href={`/ordres/${rdv.ordre.id}`} className="row nowrap table-link">
                            <span className="mono">{rdv.ordre.numero}</span>
                            <StatusBadge status={BADGE_OT[rdv.ordre.statut]}>{LIBELLE_OT[rdv.ordre.statut]}</StatusBadge>
                          </Link>
                        ) : (
                          <Button loading={ouvrir.isPending && ouvrir.variables?.id === rdv.id} onClick={() => ouvrir.mutate(rdv)}>
                            Ouvrir l&apos;ordre de travail
                            <span className="sr-only">
                              {" "}
                              du {formatJour(groupe.jour)} à {formatHeure(rdv.debut)} ({rdv.vehicule.immatriculation})
                            </span>
                          </Button>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
