// ESLint flat configuration for the web host. Next 16 carries no `next lint`
// command; `npm run lint` runs ESLint directly over this configuration, so the
// reading runs the same way on a developer's shell and in CI, with no prompt.
//
// The contract below was set on 2026-11-06 from the first full reading of the
// web (212 findings), each change stated with its reason rather than painted
// over a red result:
// - react/no-unescaped-entities is off: this host renders people's text, and
//   an apostrophe or a quote in JSX text is content, not a defect (145 sites).
// - The React 19 compiler-era hook rules read as warnings: they teach a shape
//   the code predates (35 setState-in-effect, 6 purity, 1 refs, 1 immutability
//   sites on that day); each site is work, counted here until it is absorbed.
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,
  {
    rules: {
      "react/no-unescaped-entities": "off",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
    },
  },
  globalIgnores([".next/**", "out/**", "node_modules/**", "coverage/**", "playwright-report/**", "test-results/**"]),
]);
