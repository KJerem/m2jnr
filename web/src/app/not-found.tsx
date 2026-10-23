import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <main className="center-page">
      <div className="panel center-card">
        <div className="panel-body">
          <p className="label">Erreur 404</p>
          <h1>Page introuvable</h1>
          <p className="muted">Cette page n&apos;existe pas ou a été déplacée.</p>
          <ButtonLink href="/" variant="primary">
            Retour au tableau de bord
          </ButtonLink>
        </div>
      </div>
    </main>
  );
}
