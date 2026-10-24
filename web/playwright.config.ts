import { defineConfig, devices } from "@playwright/test";

/**
 * Recette de bout en bout (sprint 4) : les parcours tournent contre la pile Docker de
 * développement déjà lancée (docker compose up -d, migrations et seed). Ils ne font pas
 * partie de la CI GitHub (pas de pile Docker là-bas) : voir le README, « Tests ».
 *
 * - E2E_BASE_URL : adresse de l'interface (http://localhost:3000 par défaut) ;
 * - PW_CHROMIUM_PATH : exécutable Chromium à utiliser si « npx playwright install chromium »
 *   n'est pas possible (machine sans réseau), par exemple
 *   C:\Users\…\AppData\Local\ms-playwright\chromium_headless_shell-1234\chrome-headless-shell-win64\chrome-headless-shell.exe.
 */
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  // Le serveur de développement compile chaque page à sa première visite.
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "fr-FR",
    timezoneId: "Europe/Paris",
    viewport: { width: 1280, height: 900 },
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    navigationTimeout: 90_000,
    actionTimeout: 30_000,
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [{ name: "chromium" }],
});
