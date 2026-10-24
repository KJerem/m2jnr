import type { ReactNode } from "react";
import { ShellTablette } from "@/components/layout/ShellTablette";

// Vue atelier : hors de la coquille à barre latérale, pour une tablette lue à un mètre.
export default function AtelierLayout({ children }: { children: ReactNode }) {
  return <ShellTablette>{children}</ShellTablette>;
}
