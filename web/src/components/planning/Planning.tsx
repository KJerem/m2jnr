"use client";

import { useQuery } from "@tanstack/react-query";
import { CarteOrdre } from "@/components/ordres/CarteOrdre";
import { ButtonLink } from "@/components/ui/Button";
import { Plate } from "@/components/ui/Plate";
import { StatusBadge, type BadgeStatus } from "@/components/ui/StatusBadge";
import { apiFetch } from "@/lib/api";
import { nomComplet } from "@/lib/format";
import { formatDureeHM, modele } from "@/lib/ordres";
import { decalerJour, formatCreneau, formatJour, libelleReport, type ElementPlanning, type Planning as DonneesPlanning, type PontPlanning, type RendezVous } from "@/lib/rendezvous";
import { aujourdHui } from "@/lib/vehicules";

export function usePlanning(jour: string) {
  return useQuery({
    queryKey: ["planning", jour],
    queryFn: ({ signal }) => apiFetch<DonneesPlanning>(`/planning?jour=${jour}`, { signal }),
    refetchInterval: 60_000,
  });
}

const LEGENDE: BadgeStatus[] = ["attente", "en-cours", "pret", "livre", "urgent"];

/** Rendez-vous sans ordre de travail ouvert : créneau, plaque, modèle, motif. */
export function CarteRendezVous({ rdv }: { rdv: RendezVous }) {
  return (
    <article className="carte-rdv">
      <p className="carte-rdv-creneau num">{formatCreneau(rdv.debut, rdv.fin)}</p>
      <div className="row">
        <Plate number={rdv.vehicule.immatriculation} />
        <span className="et-wo-model">{modele(rdv.vehicule)}</span>
      </div>
      <p className="caption">
        {rdv.motif} · {nomComplet(rdv.client)}
      </p>
      <p className="caption">Rendez-vous, ordre de travail pas encore ouvert</p>
    </article>
  );
}

/** Créneau du planning : la carte de l'OT s'il est ouvert, sinon le rendez-vous ; un report rappelle son jour d'origine. */
export function ElementDuPlanning({ element, lienTablette }: { element: ElementPlanning; lienTablette?: boolean }) {
  if (element.type === "ordre" && element.ordre) {
    const { debut, fin } = element.rendez_vous;
    return (
      <div className="stack-xs">
        <p className="carte-rdv-creneau num">{element.report ? libelleReport(element.rendez_vous) : formatCreneau(debut, fin)}</p>
        <CarteOrdre ordre={element.ordre} href={lienTablette ? `/ordres/${element.ordre.id}/tablette` : undefined} />
      </div>
    );
  }
  return <CarteRendezVous rdv={element.rendez_vous} />;
}

function mecaniciens(pont: PontPlanning): string | null {
  const noms = [...new Set(pont.elements.flatMap((e) => (e.ordre?.mecanicien ? [e.ordre.mecanicien.nom] : [])))];
  return noms.length ? noms.join(", ") : null;
}

function Charge({ pont }: { pont: PontPlanning }) {
  const pct = Math.min(100, Math.round((pont.charge_minutes / pont.capacite_minutes) * 100));
  const texte = `${formatDureeHM(pont.charge_minutes)} / ${formatDureeHM(pont.capacite_minutes)}`;
  const depasse = pont.charge_minutes > pont.capacite_minutes;
  return (
    <div className="planning-charge">
      <span className={`num${depasse ? " danger-text strong" : ""}`}>
        {texte}
        {depasse ? " · surchargé" : null}
      </span>
      <div className="et-progress" role="progressbar" aria-label={`Charge du ${pont.nom}`} aria-valuemin={0} aria-valuemax={pont.capacite_minutes} aria-valuenow={Math.min(pont.charge_minutes, pont.capacite_minutes)} aria-valuetext={texte}>
        <div className={`et-progress-bar${depasse ? " planning-surcharge" : ""}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Planning atelier du jour (maquette 3), en lecture seule : « À planifier » puis un pont par colonne. */
export function Planning({ jour }: { jour: string }) {
  const { data, isPending, isError, error } = usePlanning(jour);
  const aujourdhui = aujourdHui();

  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Planning atelier</h1>
          <p className="caption sub">Rendez-vous et ordres de travail par pont, jour par jour.</p>
        </div>
        <nav className="planning-nav" aria-label="Changer de jour">
          <ButtonLink href={`/planning?jour=${decalerJour(jour, -1)}`} aria-label="Jour précédent">
            ‹
          </ButtonLink>
          <ButtonLink href="/planning" aria-current={jour === aujourdhui ? "date" : undefined}>
            Aujourd&apos;hui
          </ButtonLink>
          <ButtonLink href={`/planning?jour=${decalerJour(jour, 1)}`} aria-label="Jour suivant">
            ›
          </ButtonLink>
          <h2 className="planning-jour" aria-live="polite">
            {formatJour(jour)}
          </h2>
        </nav>
      </header>

      <section aria-labelledby="titre-legende" className="planning-legende">
        <h2 id="titre-legende" className="label">
          Légende
        </h2>
        <ul className="row">
          {LEGENDE.map((s) => (
            <li key={s}>
              <StatusBadge status={s} />
            </li>
          ))}
        </ul>
      </section>

      {isPending ? (
        <p className="muted" role="status">
          Chargement du planning…
        </p>
      ) : isError ? (
        <p className="callout callout-danger" role="alert">
          {error.message}
        </p>
      ) : (
        <div className="planning" role="region" aria-label="Colonnes du planning" tabIndex={0}>
          <section className="planning-colonne" aria-labelledby="col-a-planifier">
            <div className="planning-tete">
              <h3 id="col-a-planifier">À planifier</h3>
              <span className="caption">{data.a_planifier.length} OT</span>
            </div>
            {data.a_planifier.length === 0 ? (
              <p className="kanban-vide">Tout est planifié.</p>
            ) : (
              <ul className="kanban-cartes">
                {data.a_planifier.map((o) => (
                  <li key={o.id}>
                    <CarteOrdre ordre={o} />
                  </li>
                ))}
              </ul>
            )}
          </section>
          {data.ponts.map((pont) => {
            const equipe = mecaniciens(pont);
            return (
              <section key={pont.id} className="planning-colonne" aria-labelledby={`col-pont-${pont.id}`}>
                <div className="planning-tete">
                  <h3 id={`col-pont-${pont.id}`}>{pont.nom}</h3>
                  {equipe ? <span className="caption">{equipe}</span> : null}
                </div>
                <Charge pont={pont} />
                {pont.elements.length === 0 ? (
                  <p className="kanban-vide">Aucun rendez-vous ce jour.</p>
                ) : (
                  <ul className="kanban-cartes">
                    {pont.elements.map((e) => (
                      <li key={e.rendez_vous.id}>
                        <ElementDuPlanning element={e} />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
