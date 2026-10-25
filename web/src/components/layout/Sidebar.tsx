"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Icon, type IconName } from "@/components/ui/Icon";
import type { Role } from "@/lib/session";
import { ThemeToggle } from "./ThemeToggle";

export type { Role };

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  roles: Role[];
  /** Autres chemins qui rendent l'entrée active (onglets d'une même page). */
  aussi?: string[];
}

/** Menu selon le rôle : le mécanicien ne voit ni les clients en écriture, ni les factures. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Tableau de bord", icon: "dashboard", roles: ["gerant", "mecanicien"] },
  { href: "/planning", label: "Planning atelier", icon: "calendar", roles: ["gerant", "mecanicien"] },
  { href: "/atelier", label: "Suivi atelier", icon: "kanban", roles: ["gerant", "mecanicien"] },
  { href: "/ordres", label: "Ordres de travail", icon: "wrench", roles: ["gerant", "mecanicien"] },
  { href: "/rendez-vous", label: "Rendez-vous", icon: "clock", roles: ["gerant"] },
  { href: "/clients", label: "Clients & véhicules", icon: "users", roles: ["gerant"], aussi: ["/vehicules"] },
  // Le mécanicien lit les véhicules et leur historique, sans fiche client (story S1.5).
  { href: "/vehicules", label: "Véhicules", icon: "plaque", roles: ["mecanicien"] },
  { href: "/devis", label: "Devis & factures", icon: "file", roles: ["gerant"], aussi: ["/factures"] },
  { href: "/employes", label: "Employés", icon: "badge", roles: ["gerant"] },
];

export function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

function itemActif(pathname: string, item: NavItem) {
  return [item.href, ...(item.aussi ?? [])].some((href) => isActive(pathname, href));
}

export function Sidebar({ role, garageName, footer }: { role: Role; garageName: string; footer?: ReactNode }) {
  const pathname = usePathname();
  return (
    <nav className="sidebar" aria-label="Navigation principale">
      <Link href="/" className="brand">
        Établi
        <small>{garageName}</small>
      </Link>
      <div className="nav">
        {NAV_ITEMS.filter((item) => item.roles.includes(role)).map((item) => (
          <Link key={item.href} href={item.href} aria-current={itemActif(pathname, item) ? "page" : undefined} title={item.label}>
            <Icon name={item.icon} size={22} />
            <span>{item.label}</span>
          </Link>
        ))}
      </div>
      <div className="sidebar-foot">
        {footer}
        <ThemeToggle />
      </div>
    </nav>
  );
}
