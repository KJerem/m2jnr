import { StatusBadge } from "@/components/ui/StatusBadge";
import { BADGE_STATUT_COMPTE, LIBELLE_STATUT_COMPTE, libelleBlocage, type Employe } from "@/lib/employes";

/** Statut du compte (pastille + mot), suivi de « Bloqué jusqu'à 15 h 02 » après 5 essais erronés. */
export function BadgeCompte({ employe }: { employe: Pick<Employe, "statut" | "bloque_jusqu_a"> }) {
  const blocage = libelleBlocage(employe);
  return (
    <span className="badges-compte">
      <StatusBadge status={BADGE_STATUT_COMPTE[employe.statut]}>{LIBELLE_STATUT_COMPTE[employe.statut]}</StatusBadge>
      {blocage ? <StatusBadge status="urgent">{blocage}</StatusBadge> : null}
    </span>
  );
}
