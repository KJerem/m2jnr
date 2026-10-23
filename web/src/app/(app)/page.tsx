import { KpiTile } from "@/components/ui/KpiTile";

export default function TableauDeBord() {
  return (
    <>
      <header className="page-head">
        <div>
          <h1 className="display">Atelier</h1>
          <p className="caption sub">Le tableau de bord se remplit au fil des sprints.</p>
        </div>
      </header>
      <section className="kpis" aria-label="Indicateurs">
        <KpiTile label="Véhicules à l'atelier" value="—" />
        <KpiTile label="Prêts à restituer" value="—" />
        <KpiTile label="Rendez-vous du jour" value="—" />
      </section>
    </>
  );
}
