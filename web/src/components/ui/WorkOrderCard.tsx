import Link from "next/link";
import { Plate } from "./Plate";
import { StatusBadge, type BadgeStatus } from "./StatusBadge";

export interface WorkOrderCardProps {
  /** Numéro de l'ordre de travail, par exemple « OT-2026-001 ». */
  reference: string;
  plate: string;
  /** Marque et modèle, par exemple « Peugeot 308 SW ». */
  vehicle: string;
  client: string;
  status: BadgeStatus;
  mechanic?: string;
  tasksDone?: number;
  tasksTotal?: number;
  /** Restitution promise, par exemple « Prêt 17 h 30 ». */
  due?: string;
  /** Heure promise dépassée : affichée en danger. */
  late?: boolean;
  /** Client sur place ou véhicule prioritaire : bande jaune et badge Urgent. */
  priority?: boolean;
  href?: string;
}

export function WorkOrderCard({ reference, plate, vehicle, client, status, mechanic, tasksDone = 0, tasksTotal = 0, due, late, priority, href }: WorkOrderCardProps) {
  const pct = tasksTotal > 0 ? Math.round((tasksDone / tasksTotal) * 100) : 0;
  const body = (
    <>
      <div className="et-wo-head">
        <span className="et-wo-ref">{reference}</span>
        <span className="et-wo-badges">
          {priority ? <StatusBadge status="urgent" /> : null}
          <StatusBadge status={status} />
        </span>
      </div>
      <div className="et-wo-vehicle">
        <Plate number={plate} />
        <span className="et-wo-model">{vehicle}</span>
      </div>
      <div className="et-wo-meta">
        <span>
          Client <strong>{client}</strong>
        </span>
        <span>{mechanic ?? "Non affecté"}</span>
      </div>
      {tasksTotal > 0 ? (
        <div className="et-progress" role="progressbar" aria-valuemin={0} aria-valuemax={tasksTotal} aria-valuenow={tasksDone} aria-label="Travaux réalisés">
          <div className="et-progress-bar" style={{ width: `${pct}%` }} />
        </div>
      ) : null}
      <div className="et-wo-foot">
        <span>{tasksTotal > 0 ? `${tasksDone} / ${tasksTotal} travaux` : "Aucun travail planifié"}</span>
        {due ? <span className={`et-wo-due${late ? " et-wo-late" : ""}`}>{due}</span> : null}
      </div>
    </>
  );
  const className = `et-wo${priority ? " et-wo-priority" : ""}`;
  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <article className={className}>{body}</article>
  );
}
