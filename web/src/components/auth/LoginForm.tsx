"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { SESSION_KEY } from "@/components/session/useSession";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { ApiError, apiFetch } from "@/lib/api";
import type { SessionReponse } from "@/lib/session";

export function LoginForm({ suivant }: { suivant: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);

  async function soumettre(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErreur(null);
    if (!email.trim() || !motDePasse) {
      setErreur("Saisissez votre e-mail et votre mot de passe.");
      return;
    }
    setEnvoi(true);
    try {
      const session = await apiFetch<SessionReponse>("/auth/login", {
        method: "POST",
        body: { email: email.trim(), mot_de_passe: motDePasse },
        redirigerSi401: false,
      });
      client.setQueryData(SESSION_KEY, session);
      router.replace(suivant);
      router.refresh();
    } catch (cause) {
      setErreur(cause instanceof ApiError ? cause.message : "Connexion impossible. Réessayez.");
      setMotDePasse("");
      setEnvoi(false);
    }
  }

  return (
    <form className="stack" onSubmit={soumettre} noValidate aria-describedby="connexion-erreur">
      <div id="connexion-erreur" role="alert" className={erreur ? "callout callout-danger" : undefined}>
        {erreur}
      </div>
      <TextField
        label="E-mail"
        type="email"
        name="email"
        autoComplete="username"
        inputMode="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <TextField
        label="Mot de passe"
        type="password"
        name="mot_de_passe"
        autoComplete="current-password"
        required
        value={motDePasse}
        onChange={(e) => setMotDePasse(e.target.value)}
      />
      <Button type="submit" variant="primary" block loading={envoi}>
        {envoi ? "Connexion…" : "Se connecter"}
      </Button>
    </form>
  );
}
