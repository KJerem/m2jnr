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
}

/** Menu selon le rôle : le mécanicien ne voit ni les clients en écriture, ni les factures. */
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Tableau de bord", icon: "dashboard", roles: ["gerant", "mecanicien"] },
  { href: "/planning", label: "Planning atelier", icon: "calendar", roles: ["gerant", "mecanicien"] },
  { href: "/atelier", label: "Suivi atelier", icon: "kanban", roles: ["gerant", "mecanicien"] },
  { href: "/ordres", label: "Ordres de travail", icon: "wrench", roles: ["gerant", "mecanicien"] },
  { href: "/rendez-vous", label: "Rendez-vous", icon: "clock", roles: ["gerant"] },
  { href: "/clients", label: "Clients & véhicules", icon: "users", roles: ["gerant"] },
  { href: "/factures", label: "Factures", icon: "file", roles: ["gerant"] },
];

export function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
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
          <Link key={item.href} href={item.href} aria-current={isActive(pathname, item.href) ? "page" : undefined} title={item.label}>
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
