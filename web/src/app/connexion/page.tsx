import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/LoginForm";
import { cheminDeRetour } from "@/lib/session";

export const metadata: Metadata = { title: "Connexion" };

type Recherche = Record<string, string | string[] | undefined>;

export default async function Connexion({ searchParams }: { searchParams: Promise<Recherche> }) {
  const { suivant } = await searchParams;
  return (
    <main className="center-page" id="contenu">
      <div className="panel center-card">
        <div className="panel-body">
          <div className="login-brand">
            <span className="login-logo">Établi</span>
            <span className="caption">Garage Établi</span>
          </div>
          <h1>Connexion</h1>
          <p className="muted">Accès réservé à l&apos;équipe du garage.</p>
          <LoginForm suivant={cheminDeRetour(typeof suivant === "string" ? suivant : null)} />
        </div>
      </div>
    </main>
  );
}
