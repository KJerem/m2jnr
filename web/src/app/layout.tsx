import type { Metadata, Viewport } from "next";
import { Barlow, Barlow_Semi_Condensed, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";
import { themeInitScript } from "@/components/layout/ThemeToggle";
import { Providers } from "@/components/session/Providers";
import "@/styles/tokens.css";
import "@/styles/etabli.css";
import "@/styles/app.css";

const barlow = Barlow({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-barlow", display: "swap" });
const barlowCondensed = Barlow_Semi_Condensed({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-barlow-condensed", display: "swap" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], weight: ["500", "600"], variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Établi", template: "%s · Établi" },
  description: "Gestion de garage automobile : clients, véhicules, atelier, devis et factures.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" className={`${barlow.variable} ${barlowCondensed.variable} ${jetbrains.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
