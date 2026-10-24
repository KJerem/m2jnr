import { WorkOrderCard } from "@/components/ui/WorkOrderCard";
import { nomComplet } from "@/lib/format";
import { echeance, modele, type OrdreResume } from "@/lib/ordres";
import { BADGE_OT } from "@/lib/statuts";

/** Carte d'atelier d'un OT (composant WorkOrderCard du design system). */
export function CarteOrdre({ ordre, href }: { ordre: OrdreResume; href?: string }) {
  return (
    <WorkOrderCard
      reference={ordre.numero}
      plate={ordre.vehicule.immatriculation}
      vehicle={modele(ordre.vehicule)}
      client={nomComplet(ordre.client)}
      status={BADGE_OT[ordre.statut]}
      mechanic={ordre.mecanicien?.nom}
      tasksDone={ordre.taches_terminees}
      tasksTotal={ordre.taches_total}
      due={ordre.en_retard ? `${echeance(ordre) ?? "Prêt"} · en retard` : echeance(ordre)}
      late={ordre.en_retard}
      priority={ordre.prioritaire}
      href={href ?? `/ordres/${ordre.id}`}
    />
  );
}
