import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";

// Sprint 0 : gabarit seul. Le rôle viendra de la session à partir de la story S8.1.
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <a href="#contenu" className="skip-link">
        Aller au contenu
      </a>
      <div className="shell">
        <Sidebar role="gerant" garageName="Garage Établi" />
        <main id="contenu" className="main" tabIndex={-1}>
          {children}
        </main>
      </div>
    </>
  );
}
