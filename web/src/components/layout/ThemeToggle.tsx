"use client";

import { useSyncExternalStore } from "react";
import { Icon } from "@/components/ui/Icon";

type Theme = "light" | "dark";
const STORAGE_KEY = "etabli-theme";
const MEDIA = "(prefers-color-scheme: dark)";

function currentTheme(): Theme {
  const forced = document.documentElement.dataset.theme;
  if (forced === "light" || forced === "dark") return forced;
  return window.matchMedia(MEDIA).matches ? "dark" : "light";
}

/** Le thème est un état externe (attribut data-theme et préférence système) : on s'y abonne. */
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const media = window.matchMedia(MEDIA);
  media.addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", onChange);
  };
}

/** Bascule clair/sombre ; le choix est mémorisé par navigateur (confort, pas une donnée métier). */
export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);

  function toggle() {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* stockage indisponible : le thème reste valable pour la session */
    }
  }

  const label = theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre";
  return (
    <button type="button" className="et-btn et-btn-sm" onClick={toggle} aria-label={label} title={label}>
      <Icon name={theme === "dark" ? "sun" : "moon"} />
      <span className="theme-label">{theme === "dark" ? "Thème clair" : "Thème sombre"}</span>
    </button>
  );
}

/** Script inline exécuté avant le rendu pour éviter le flash de thème. */
export const themeInitScript = `try{var t=localStorage.getItem("${STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
