"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ToastProvider } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api";

/** Pas de nouvel essai pour une erreur « métier » (droits, validation, conflit) : seulement réseau ou 5xx. */
export function doitReessayer(essais: number, erreur: unknown): boolean {
  if (erreur instanceof ApiError && erreur.status > 0 && erreur.status < 500) return false;
  return essais < 2;
}

export function creerQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: doitReessayer, refetchOnWindowFocus: false, staleTime: 30_000 },
      mutations: { retry: false },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(creerQueryClient);
  return (
    <QueryClientProvider client={client}>
      <ToastProvider>{children}</ToastProvider>
    </QueryClientProvider>
  );
}
