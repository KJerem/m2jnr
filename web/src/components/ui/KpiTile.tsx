import type { ReactNode } from "react";

export interface KpiTileProps {
  label: string;
  value: ReactNode;
  unit?: string;
  /** Ligne de comparaison courte, par exemple « +3 vs hier ». */
  delta?: string;
  /** good = succès, bad = danger, flat = discret. */
  trend?: "good" | "bad" | "flat";
  /** Bande jaune signal pour le seul chiffre qui demande de l'attention. */
  highlight?: boolean;
}

export function KpiTile({ label, value, unit, delta, trend = "flat", highlight }: KpiTileProps) {
  return (
    <div className={`et-kpi${highlight ? " et-kpi-signal" : ""}`}>
      <span className="et-kpi-label">{label}</span>
      <span className="et-kpi-value">
        {value}
        {unit ? <span className="et-kpi-unit">{unit}</span> : null}
      </span>
      {delta ? <span className={`et-kpi-delta et-kpi-${trend}`}>{delta}</span> : null}
    </div>
  );
}
