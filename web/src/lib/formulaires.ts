import type { FieldValues, Path, UseFormSetError } from "react-hook-form";
import { ApiError } from "./api";

/**
 * Rattache les erreurs de validation de l'API (`champs`) aux champs du formulaire.
 * Renvoie le message général à afficher si aucune erreur n'a pu être rattachée.
 */
export function appliquerErreursApi<T extends FieldValues>(erreur: unknown, champsConnus: readonly Path<T>[], setError: UseFormSetError<T>): string | null {
  if (!(erreur instanceof ApiError)) return "Enregistrement impossible. Réessayez.";
  let rattachees = 0;
  for (const [champ, message] of Object.entries(erreur.champs)) {
    if ((champsConnus as readonly string[]).includes(champ)) {
      setError(champ as Path<T>, { type: "server", message }, { shouldFocus: rattachees === 0 });
      rattachees += 1;
    }
  }
  return rattachees > 0 ? null : erreur.message;
}
