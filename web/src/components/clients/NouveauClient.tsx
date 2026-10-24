"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { Client, ClientEntree } from "@/lib/clients";
import { ClientForm } from "./ClientForm";

export function creerClient(entree: ClientEntree, confirmerDoublon: boolean) {
  return apiFetch<Client>(`/clients${confirmerDoublon ? "?confirmer_doublon=true" : ""}`, { method: "POST", body: entree });
}

export function NouveauClient() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return (
    <>
      <header className="page-head">
        <div>
          <p className="breadcrumb">
            <Link href="/clients">Clients</Link> / Nouveau
          </p>
          <h1 className="display">Nouveau client</h1>
        </div>
      </header>
      <section className="panel">
        <div className="panel-body">
          <ClientForm
            mode="creation"
            envoyer={creerClient}
            onSucces={(client) => {
              void queryClient.invalidateQueries({ queryKey: ["clients"] });
              void queryClient.invalidateQueries({ queryKey: ["recherche"] });
              router.push(`/clients/${client.id}`);
            }}
            onAnnuler={() => router.push("/clients")}
          />
        </div>
      </section>
    </>
  );
}
