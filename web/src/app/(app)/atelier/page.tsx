import type { Metadata } from "next";
import { Kanban } from "@/components/atelier/Kanban";

export const metadata: Metadata = { title: "Suivi atelier" };

export default function PageAtelier() {
  return <Kanban />;
}
