/**
 * Client de l'API : le navigateur n'appelle que /api/* (même origine, relayé par Next vers FastAPI).
 *
 * - JSON en entrée et en sortie ;
 * - jeton CSRF recopié du cookie dans l'en-tête X-CSRF-Token pour POST, PUT, PATCH et DELETE
 *   (demandé à /api/auth/csrf s'il manque, et redemandé une fois si l'API le refuse) ;
 * - erreurs levées en ApiError {status, code, message, champs, details} au format de l'API ;
 * - 401 hors de la page de connexion : retour à /connexion?suivant=<page courante>.
 */
import { CSRF_COOKIE, CSRF_HEADER, PAGE_CONNEXION } from "./session";

const BASE = "/api";
const METHODES_NON_SURES = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly champs: Record<string, string>;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, champs: Record<string, string> = {}, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.champs = champs;
    this.details = details;
  }
}

export interface ApiOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  /** Corps envoyé en JSON. */
  body?: unknown;
  signal?: AbortSignal;
  /** Faux pour gérer soi-même un 401 (formulaire de connexion). Vrai par défaut. */
  redirigerSi401?: boolean;
}

export function lireCookie(nom: string): string | null {
  if (typeof document === "undefined") return null;
  for (const morceau of document.cookie.split(";")) {
    const [cle, ...valeur] = morceau.trim().split("=");
    if (cle === nom) return decodeURIComponent(valeur.join("="));
  }
  return null;
}

async function obtenirJetonCsrf(renouveler = false): Promise<string> {
  const existant = renouveler ? null : lireCookie(CSRF_COOKIE);
  if (existant) return existant;
  const reponse = await fetch(`${BASE}/auth/csrf`, { credentials: "same-origin", cache: "no-store" });
  const corps = (await reponse.json().catch(() => ({}))) as { jeton?: string };
  return lireCookie(CSRF_COOKIE) ?? corps.jeton ?? "";
}

async function erreurDepuisReponse(reponse: Response): Promise<ApiError> {
  const corps = (await reponse.json().catch(() => null)) as Record<string, unknown> | null;
  if (!corps || typeof corps !== "object") {
    return new ApiError(reponse.status, "erreur", "Le serveur a renvoyé une erreur. Réessayez.");
  }
  const { code, message, champs, ...details } = corps;
  return new ApiError(
    reponse.status,
    typeof code === "string" ? code : "erreur",
    typeof message === "string" ? message : "Le serveur a renvoyé une erreur. Réessayez.",
    champs && typeof champs === "object" ? (champs as Record<string, string>) : {},
    details,
  );
}

function redirigerVersConnexion() {
  if (typeof window === "undefined") return;
  const { pathname, search } = window.location;
  if (pathname === PAGE_CONNEXION) return;
  const suivant = encodeURIComponent(`${pathname}${search}`);
  // Hors composant (pas de routeur) ; un rechargement complet vide aussi le cache de la session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`${PAGE_CONNEXION}?suivant=${suivant}`);
}

export async function apiFetch<T>(chemin: string, options: ApiOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const nonSure = METHODES_NON_SURES.has(method);

  async function envoyer(renouvelerJeton: boolean): Promise<Response> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (nonSure) headers[CSRF_HEADER] = await obtenirJetonCsrf(renouvelerJeton);
    return fetch(`${BASE}${chemin}`, {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal,
    });
  }

  let reponse: Response;
  try {
    reponse = await envoyer(false);
    if (nonSure && reponse.status === 403) {
      const erreur = await erreurDepuisReponse(reponse.clone());
      if (erreur.code === "csrf_invalide") reponse = await envoyer(true);
    }
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "reseau", "Connexion au serveur impossible. Vérifiez le réseau et réessayez.");
  }

  if (!reponse.ok) {
    const erreur = await erreurDepuisReponse(reponse);
    if (reponse.status === 401 && options.redirigerSi401 !== false) redirigerVersConnexion();
    throw erreur;
  }
  if (reponse.status === 204) return undefined as T;
  return (await reponse.json()) as T;
}
