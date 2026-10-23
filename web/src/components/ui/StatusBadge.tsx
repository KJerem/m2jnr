import type { ReactNode } from "react";

/** Clés de statut du design system Établi. */
export type BadgeStatus = "attente" | "diagnostic" | "en-cours" | "pieces" | "pret" | "livre" | "urgent";

const STATUS: Record<BadgeStatus, { label: string; dot: "fill" | "ring" | "diamond" }> = {
  attente: { label: "En attente", dot: "ring" },
  diagnostic: { label: "Diagnostic", dot: "fill" },
  "en-cours": { label: "En cours", dot: "fill" },
  pieces: { label: "Attente pièces", dot: "ring" },
  pret: { label: "Prêt", dot: "fill" },
  livre: { label: "Livré", dot: "ring" },
  urgent: { label: "Urgent", dot: "diamond" },
};

export interface StatusBadgeProps {
  status: BadgeStatus;
  /** Remplace le libellé par défaut. */
  children?: ReactNode;
}

/** Pastille + mot : la couleur n'est jamais le seul indice (forme de la pastille différente). */
export function StatusBadge({ status, children }: StatusBadgeProps) {
  const s = STATUS[status] ?? STATUS.attente;
  const dot = ["et-dot", s.dot === "ring" && "et-dot-ring", s.dot === "diamond" && "et-dot-diamond"].filter(Boolean).join(" ");
  return (
    <span className={`et-status et-status-${status}`}>
      <span className={dot} aria-hidden="true" />
      {children ?? s.label}
    </span>
  );
}
