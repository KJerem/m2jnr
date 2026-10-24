import { Button, ButtonLink } from "./Button";

export interface PaginationProps {
  page: number;
  taille: number;
  total: number;
  /** Lien vers une page donnée, par exemple (p) => `/clients?page=${p}`. */
  lien: (page: number) => string;
  /** Nom des éléments au pluriel pour le résumé, par exemple « clients ». */
  libelle: string;
}

export function Pagination({ page, taille, total, lien, libelle }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / taille));
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="caption" aria-live="polite">
        Page {Math.min(page, pages)} sur {pages} · {total} {libelle}
      </span>
      <div className="actions">
        {page > 1 ? (
          <ButtonLink href={lien(page - 1)} size="sm" rel="prev">
            Précédent
          </ButtonLink>
        ) : (
          <Button size="sm" disabled>
            Précédent
          </Button>
        )}
        {page < pages ? (
          <ButtonLink href={lien(page + 1)} size="sm" rel="next">
            Suivant
          </ButtonLink>
        ) : (
          <Button size="sm" disabled>
            Suivant
          </Button>
        )}
      </div>
    </nav>
  );
}
