"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";
import { SESSION_KEY } from "@/components/session/useSession";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { ApiError, apiFetch } from "@/lib/api";
import type { SessionReponse } from "@/lib/session";

/**
 * Champs non contrôlés lus au moment de l'envoi : une saisie ou un remplissage automatique
 * faits avant le chargement complet de la page ne sont pas perdus. `method="post"` évite que
 * le mot de passe passe dans l'URL si le formulaire part avant que le script soit prêt.
 */
export function LoginForm({ suivant }: { suivant: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const motDePasseRef = useRef<HTMLInputElement>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErreur(null);
    const donnees = new FormData(event.currentTarget);
    const email = String(donnees.get("email") ?? "").trim();
    const motDePasse = String(donnees.get("mot_de_passe") ?? "");
    if (!email || !motDePasse) {
      setErreur("Saisissez votre e-mail et votre mot de passe.");
      return;
    }
    setEnvoi(true);
    try {
      const session = await apiFetch<SessionReponse>("/auth/login", {
        method: "POST",
        body: { email, mot_de_passe: motDePasse },
        redirigerSi401: false,
      });
      client.setQueryData(SESSION_KEY, session);
      router.replace(suivant);
      router.refresh();
    } catch (cause) {
      setErreur(cause instanceof ApiError ? cause.message : "Connexion impossible. Réessayez.");
      if (motDePasseRef.current) {
        motDePasseRef.current.value = "";
        motDePasseRef.current.focus();
      }
      setEnvoi(false);
    }
  }

  return (
    <form className="stack" method="post" onSubmit={soumettre} noValidate aria-describedby="connexion-erreur">
      <div id="connexion-erreur" role="alert" className={erreur ? "callout callout-danger" : undefined}>
        {erreur}
      </div>
      <TextField label="E-mail" type="email" name="email" autoComplete="username" inputMode="email" required />
      <TextField ref={motDePasseRef} label="Mot de passe" type="password" name="mot_de_passe" autoComplete="current-password" required />
      <Button type="submit" variant="primary" block loading={envoi}>
        {envoi ? "Connexion…" : "Se connecter"}
      </Button>
    </form>
  );
}
