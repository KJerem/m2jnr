import type { Metadata } from "next";
import { RequireRole } from "@/components/session/RequireRole";

export const metadata: Metadata = { title: "Factures" };

// Page réservée au gérant ; la liste des factures arrive au sprint 3 (story S4.3).
export default function Factures() {
  return (
    <RequireRole roles={["gerant"]}>
      <header className="page-head">
        <div>
          <h1 className="display">Factures</h1>
          <p className="caption sub">Les factures émises apparaîtront ici.</p>
        </div>
      </header>
      <section className="panel">
        <p className="empty">Aucune facture pour l&apos;instant.</p>
      </section>
    </RequireRole>
  );
}
