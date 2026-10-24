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

/** Boutons en taille md (44 px) : la liste est aussi utilisée sur tablette (cibles tactiles). */
export function Pagination({ page, taille, total, lien, libelle }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / taille));
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="caption" aria-live="polite">
        Page {Math.min(page, pages)} sur {pages} · {total} {libelle}
      </span>
      <div className="actions">
        {page > 1 ? (
          <ButtonLink href={lien(page - 1)} rel="prev">
            Précédent
          </ButtonLink>
        ) : (
          <Button disabled>
            Précédent
          </Button>
        )}
        {page < pages ? (
          <ButtonLink href={lien(page + 1)} rel="next">
            Suivant
          </ButtonLink>
        ) : (
          <Button disabled>
            Suivant
          </Button>
        )}
      </div>
    </nav>
  );
}
