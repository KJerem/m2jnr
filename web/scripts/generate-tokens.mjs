// Génère src/styles/tokens.css à partir de design/tokens.json (design system Établi).
// Thème clair par défaut, thème sombre via prefers-color-scheme ou data-theme="dark".
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const tokens = JSON.parse(readFileSync(join(root, "design/tokens.json"), "utf8"));

const light = [];
const dark = [];

function push(name, value) {
  if (typeof value === "string") {
    light.push(`  --${name}: ${value};`);
    return;
  }
  light.push(`  --${name}: ${value.light};`);
  if (value.dark && value.dark !== value.light) dark.push(`  --${name}: ${value.dark};`);
}

for (const t of tokens.color.tokens) push(t.name, t.value);
for (const t of tokens.shadow.tokens) push(t.name, t.value);
for (const t of tokens.spacing.tokens) push(t.name, t.value);
for (const t of tokens.radius.tokens) push(t.name, t.value);
for (const [name, value] of Object.entries(tokens.type.families)) light.push(`  --font-${name}: ${value};`);

const css = `/* Établi — généré depuis design/tokens.json par scripts/generate-tokens.mjs. Ne pas éditer. */
:root {
  color-scheme: light;
${light.join("\n")}
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
${dark.map((l) => "  " + l).join("\n")}
  }
}

:root[data-theme="dark"] {
  color-scheme: dark;
${dark.join("\n")}
}
`;

writeFileSync(join(root, "src/styles/tokens.css"), css);
console.log(`tokens.css : ${light.length} variables, ${dark.length} surcharges sombres.`);
