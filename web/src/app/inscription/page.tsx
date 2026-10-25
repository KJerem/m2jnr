import type { Metadata } from "next";
import { InscriptionForm } from "@/components/auth/InscriptionForm";

export const metadata: Metadata = { title: "Créer un compte gérant" };

/** Page publique (story S8.3), ouverte sans session comme /connexion. */
export default function Inscription() {
  return (
    <main className="center-page" id="contenu">
      <div className="panel center-card">
        <div className="panel-body">
          <div className="login-brand">
            <span className="login-logo">Établi</span>
            <span className="caption">Garage Établi</span>
          </div>
          <h1>Créer un compte gérant</h1>
          <InscriptionForm />
        </div>
      </div>
    </main>
  );
}
