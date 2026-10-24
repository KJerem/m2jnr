import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";

// Le rôle vient de la session (/api/auth/me) : le menu s'adapte au gérant ou au mécanicien.
export default function AppLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
