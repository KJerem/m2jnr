import { formatDateCourte, formatHeure } from "@/lib/format";
import { prenom, type Historique } from "@/lib/ordres";
import { aujourdHui } from "@/lib/vehicules";

const EVENEMENT: Record<Historique["nouveau"], string> = {
  a_faire: "Véhicule déposé, ordre de travail ouvert",
  en_cours: "Intervention démarrée",
  termine: "Véhicule prêt",
  livre: "Véhicule livré au client",
};

/** Suivi de l'OT : chaque changement de statut avec son heure et son auteur. */
export function Suivi({ historique }: { historique: Historique[] }) {
  const aujourdhui = aujourdHui();
  return (
    <section className="panel" aria-labelledby="titre-suivi">
      <div className="panel-head">
        <h2 id="titre-suivi">Suivi</h2>
      </div>
      {historique.length === 0 ? (
        <p className="empty">Aucun changement enregistré.</p>
      ) : (
        <ol className="timeline">
          {historique.map((h) => {
            const jour = aujourdHui(new Date(h.change_le));
            return (
              <li key={h.id} className="timeline-etape">
                <span className="timeline-quand num">
                  <time dateTime={h.change_le}>
                    {jour === aujourdhui ? null : <span className="timeline-jour">{formatDateCourte(h.change_le)}</span>}
                    {formatHeure(h.change_le)}
                  </time>
                </span>
                <span className="timeline-quoi">
                  <span className="strong">{EVENEMENT[h.nouveau]}</span>
                  <span className="caption">par {prenom(h.utilisateur.nom)}</span>
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
