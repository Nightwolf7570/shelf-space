#!/usr/bin/env node
/**
 * Cross-platform launcher for the Shelf Space FastAPI web UI.
 *
 * Runs the app through the project virtualenv's Python if one exists (.venv),
 * otherwise falls back to whatever `python`/`python3` is on PATH. Invoked via
 * `npm run dev`. Extra args after `--` are forwarded to uvicorn, e.g.
 * `npm run dev -- --port 9000`.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const projectRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";

const venvPython = isWindows
  ? join(projectRoot, ".venv", "Scripts", "python.exe")
  : join(projectRoot, ".venv", "bin", "python");

const python = existsSync(venvPython)
  ? venvPython
  : isWindows
  ? "python"
  : "python3";

if (!existsSync(venvPython)) {
  console.warn(
    "[dev] No .venv found — using system Python. " +
      "Create one with: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt"
  );
}

const port = process.env.PORT || "8000";
const args = [
  "-m",
  "uvicorn",
  "web.app:app",
  "--reload",
  "--port",
  port,
  ...process.argv.slice(2), // forward any extra CLI args
];

console.log(`[dev] ${python} ${args.join(" ")}`);

const child = spawn(python, args, {
  cwd: projectRoot,
  stdio: "inherit",
});

child.on("exit", (code) => process.exit(code ?? 0));
child.on("error", (err) => {
  console.error("[dev] Failed to start the web app:", err.message);
  process.exit(1);
});
