import { NextResponse, type NextRequest } from "next/server";
import { PAGE_CONNEXION, SESSION_COOKIE } from "@/lib/session";

/**
 * Sans cookie de session, toute page renvoie vers /connexion (en gardant la page demandée).
 * Ce n'est qu'un aiguillage : la validité de la session et les droits sont vérifiés par l'API.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (pathname === PAGE_CONNEXION || request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }
  const url = new URL(PAGE_CONNEXION, request.url);
  if (pathname !== "/") url.searchParams.set("suivant", `${pathname}${search}`);
  return NextResponse.redirect(url);
}

export const config = {
  // Ni l'API (/api/*, protégée par FastAPI), ni tout /_next (fichiers, images, rechargement à
  // chaud du serveur de dev…), ni les fichiers statiques.
  matcher: ["/((?!api/|_next/|favicon.ico|.*\\.[a-zA-Z0-9]+$).*)"],
};
