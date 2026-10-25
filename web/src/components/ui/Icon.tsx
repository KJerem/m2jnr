/** Icônes au trait de 1,5 px (recommandation du design system), toujours accompagnées d'un libellé. */
const PATHS = {
  dashboard: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  wrench: "M14.5 5.5a4 4 0 0 0-5.2 5.2L4 16l4 4 5.3-5.3a4 4 0 0 0 5.2-5.2l-2.6 2.6-2.8-.6-.6-2.8z",
  kanban: "M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v13h-4z",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14a6 6 0 0 1 3.5 6",
  file: "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
  search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.5 15.5 20 20",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  plus: "M12 5v14M5 12h14",
  check: "M5 12.5l4.5 4.5L19 7.5",
  // Badge d'employé : comptes de l'équipe (story S8.2).
  badge: "M4 6h16v13H4zM9 3h6v4H9zM9.5 13a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6.5 17a3 3 0 0 1 6 0M14.5 11h3M14.5 15h3",
  close: "M6 6l12 12M18 6 6 18",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
