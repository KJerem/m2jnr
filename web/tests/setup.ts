import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// findBy… et waitFor attendent 1 s par défaut : sur une machine chargée (suite complète en
// parallèle, Docker Desktop), le premier rendu d'un fichier dépasse parfois ce délai.
configure({ asyncUtilTimeout: 5_000 });

afterEach(() => {
  cleanup();
});
