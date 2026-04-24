import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const standaloneDir = path.join(root, ".next", "standalone");
const standaloneServer = path.join(standaloneDir, "server.js");

if (!existsSync(standaloneServer)) {
  process.exit(0);
}

const standaloneNextDir = path.join(standaloneDir, ".next");
mkdirSync(standaloneNextDir, { recursive: true });

const staticSource = path.join(root, ".next", "static");
const staticTarget = path.join(standaloneNextDir, "static");
if (existsSync(staticSource)) {
  rmSync(staticTarget, { recursive: true, force: true });
  cpSync(staticSource, staticTarget, { recursive: true });
}

const publicSource = path.join(root, "public");
const publicTarget = path.join(standaloneDir, "public");
if (existsSync(publicSource)) {
  rmSync(publicTarget, { recursive: true, force: true });
  cpSync(publicSource, publicTarget, { recursive: true });
}
