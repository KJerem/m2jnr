import type { Metadata } from "next";
import { ButtonLink } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Accès refusé" };

export default function Interdit() {
  return (
    <main className="center-page">
      <div className="panel center-card">
        <div className="panel-body">
          <p className="label">Erreur 403</p>
          <h1>Accès refusé</h1>
          <p className="muted">Votre rôle ne permet pas d&apos;ouvrir cette page. Demandez au gérant si vous en avez besoin.</p>
          <ButtonLink href="/" variant="primary">
            Retour au tableau de bord
          </ButtonLink>
        </div>
      </div>
    </main>
  );
}
