import type { Metadata } from "next";
import Link from "next/link";
import { LoginForm } from "@/components/auth/LoginForm";
import { cheminDeRetour, PAGE_INSCRIPTION } from "@/lib/session";

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
          <p className="caption">
            Nouveau garage ou nouveau gérant : <Link href={PAGE_INSCRIPTION}>Créer un compte gérant</Link>. Un compte demandé s&apos;ouvre une fois validé par un gérant du garage.
          </p>
        </div>
      </div>
    </main>
  );
}
