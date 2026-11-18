#!/usr/bin/env node
/**
 * control-keelway.mjs — Isolated end-to-end verification CLI for Keelway (`/app`, `/v1/*`, `cli.py`, SQLite WAL).
 */

import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runBrowserSubcommand, withCdpPage } from "./lib/cdp-browser.mjs";

const REAL_SCRIPT_PATH = fs.realpathSync(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(path.dirname(REAL_SCRIPT_PATH), "../../../..");
const DEFAULT_STATE_DIR = path.join(os.tmpdir(), "keelway-verify-default");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function die(message, extra = {}, code = 1) {
  console.error(JSON.stringify({ ok: false, error: message, ...extra }, null, 2));
  process.exit(code);
}

function parseFlags(argv) {
  const flags = {};
  const positional = [];
  let passthrough = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--") {
      passthrough = argv.slice(i + 1);
      break;
    }
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(arg);
    }
  }
  return { flags, positional, passthrough };
}

function resolveStateDir(flags) {
  const raw = flags["state-dir"] || process.env.KEELWAY_VERIFY_STATE_DIR || DEFAULT_STATE_DIR;
  const resolved = path.resolve(String(raw));
  const forbidden = [os.homedir(), path.join(os.homedir(), ".keelway"), REPO_ROOT, path.join(REPO_ROOT, ".keelway")];
  if (forbidden.includes(resolved)) {
    die(`Refusing unsafe --state-dir '${resolved}': must be an isolated scratch directory.`);
  }
  return resolved;
}

function writeOutIfRequested(outPath, content, isBinary = false) {
  if (!outPath) return null;
  const resolved = path.resolve(String(outPath));
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  if (isBinary) fs.writeFileSync(resolved, content);
  else fs.writeFileSync(resolved, typeof content === "string" ? content : JSON.stringify(content, null, 2) + "\n", "utf8");
  return resolved;
}

function isPidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function terminatePid(pid, timeoutMs = 3500) {
  if (!isPidAlive(pid)) return { pid, terminated: false, reason: "already_exited" };
  try {
    process.kill(pid, "SIGTERM");
  } catch {
    return { pid, terminated: true };
  }
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!isPidAlive(pid)) return { pid, terminated: true, signal: "SIGTERM" };
    await sleep(100);
  }
  try {
    process.kill(pid, "SIGKILL");
  } catch {
    // exited cleanly
  }
  await sleep(100);
  return { pid, terminated: !isPidAlive(pid), signal: "SIGKILL" };
}

function findPythonBin() {
  const candidates = [
    process.env.KEELWAY_PYTHON,
    path.join(REPO_ROOT, ".venv/bin/python"),
    path.resolve(REPO_ROOT, "../kora-ai.nosync/.venv/bin/python"),
    path.resolve(REPO_ROOT, "../.venv/bin/python"),
    "python3",
  ].filter(Boolean);
  for (const bin of candidates) {
    const check = spawnSync(bin, ["-c", "import uvicorn, fastapi, sqlite3; print('OK')"], { encoding: "utf8" });
    if (check.status === 0 && (check.stdout || "").includes("OK")) return bin;
  }
  die("Could not locate a Python interpreter with uvicorn + fastapi installed. Set KEELWAY_PYTHON.");
}

function findChromeBin() {
  const candidates = [
    process.env.KEELWAY_CHROME_BIN,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ].filter(Boolean);
  for (const cacheRoot of [path.join(os.homedir(), "Library/Caches/ms-playwright"), path.join(os.homedir(), ".cache/ms-playwright")]) {
    if (!fs.existsSync(cacheRoot)) continue;
    for (const entry of fs.readdirSync(cacheRoot).filter((n) => n.startsWith("chromium-")).sort().reverse()) {
      candidates.push(
        path.join(cacheRoot, entry, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        path.join(cacheRoot, entry, "chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        path.join(cacheRoot, entry, "chrome-linux/chrome"),
      );
    }
  }
  for (const bin of candidates) if (fs.existsSync(bin)) return bin;
  for (const name of ["google-chrome", "chromium", "chromium-browser"]) {
    const which = spawnSync("which", [name], { encoding: "utf8" });
    if (which.status === 0 && which.stdout.trim()) return which.stdout.trim();
  }
  die("Could not locate Chrome/Chromium binary for headless CDP verification. Set KEELWAY_CHROME_BIN.");
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const addr = srv.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      srv.close(() => resolve(port));
    });
  });
}

function buildIsolatedEnv(inst) {
  return {
    ...process.env,
    HOME: inst.homeDir,
    PYTHONPATH: inst.repoRoot,
    KEELWAY_API_TOKEN: inst.token,
    KEELWAY_RUNTIME_DB_PATH: inst.runtimeDbPath,
    DATABASE_URL: `sqlite+aiosqlite:///${inst.coreDbPath}`,
    PYTHONUNBUFFERED: "1",
  };
}

function loadInstance(stateDir) {
  const metaPath = path.join(stateDir, "instance.json");
  if (!fs.existsSync(metaPath)) die(`No active verification instance at '${metaPath}'. Run 'control-keelway launch' first.`);
  return JSON.parse(fs.readFileSync(metaPath, "utf8"));
}

async function cmdLaunch(flags) {
  const stateDir = resolveStateDir(flags);
  const metaPath = path.join(stateDir, "instance.json");
  if (fs.existsSync(metaPath)) {
    const prev = JSON.parse(fs.readFileSync(metaPath, "utf8"));
    if (isPidAlive(prev.serverPid) || isPidAlive(prev.chromePid)) {
      die(`State dir '${stateDir}' already holds a live instance (serverPid=${prev.serverPid}, port=${prev.port}). Run cleanup first.`);
    }
  }
  const distIndex = path.join(REPO_ROOT, "core/dev_app_dist/index.html");
  if (!fs.existsSync(distIndex)) die(`Missing prebuilt dev-app bundle at '${distIndex}'. Run '(cd dev-app && npm run build)'.`);

  const pythonBin = findPythonBin();
  const chromeBin = findChromeBin();
  const port = flags.port ? Number(flags.port) : await findFreePort();
  const token = `kw_verify_${crypto.randomBytes(16).toString("hex")}`;
  const homeDir = path.join(stateDir, "home");
  const workspaceDir = path.join(stateDir, "workspace");
  const chromeProfileDir = path.join(stateDir, "chrome-profile");
  const logsDir = path.join(stateDir, "logs");
  for (const dir of [path.join(homeDir, ".keelway"), path.join(workspaceDir, ".keelway"), chromeProfileDir, logsDir]) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const inst = {
    repoRoot: REPO_ROOT,
    stateDir,
    homeDir,
    workspaceDir,
    chromeProfileDir,
    runtimeDbPath: path.join(homeDir, ".keelway/platform_runtime.db"),
    coreDbPath: path.join(homeDir, ".keelway/keelway.db"),
    port,
    apiBaseUrl: `http://127.0.0.1:${port}`,
    appUrl: `http://127.0.0.1:${port}/app?token=${token}`,
    token,
    pythonBin,
    chromeBin,
    serverPid: null,
    chromePid: null,
    cdpHttpUrl: null,
    startedAt: new Date().toISOString(),
  };

  const uvicornLogFd = fs.openSync(path.join(logsDir, "uvicorn.log"), "a");
  const chromeLogFd = fs.openSync(path.join(logsDir, "chrome.log"), "a");

  try {
    const srv = spawn(pythonBin, ["-m", "uvicorn", "core.main:app", "--host", "127.0.0.1", "--port", String(port)], {
      cwd: workspaceDir,
      env: buildIsolatedEnv(inst),
      detached: true,
      stdio: ["ignore", uvicornLogFd, uvicornLogFd],
    });
    srv.unref();
    inst.serverPid = srv.pid;

    const readyDeadline = Date.now() + 20000;
    let ready = false;
    while (Date.now() < readyDeadline) {
      if (!isPidAlive(inst.serverPid)) throw new Error(`uvicorn exited prematurely. Check ${path.join(logsDir, "uvicorn.log")}`);
      try {
        const [hRes, wRes, aRes] = await Promise.all([
          fetch(`${inst.apiBaseUrl}/health`),
          fetch(`${inst.apiBaseUrl}/v1/platform/workspaces`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(inst.appUrl),
        ]);
        if (hRes.ok && wRes.ok && aRes.ok) {
          const wsPayload = await wRes.json();
          const appHtml = await aRes.text();
          if (Array.isArray(wsPayload.workspaces) && wsPayload.workspaces.length > 0 && appHtml.includes("/app/assets/")) {
            ready = true;
            break;
          }
        }
      } catch {
        // booting
      }
      await sleep(200);
    }
    if (!ready) throw new Error("Timed out waiting for FastAPI + SQLite WAL + /app readiness.");

    const chrome = spawn(
      chromeBin,
      [
        "--headless=new",
        "--remote-debugging-port=0",
        `--user-data-dir=${chromeProfileDir}`,
        "--window-size=1440,900",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        inst.appUrl,
      ],
      { detached: true, stdio: ["ignore", chromeLogFd, chromeLogFd] },
    );
    chrome.unref();
    inst.chromePid = chrome.pid;

    const activePortFile = path.join(chromeProfileDir, "DevToolsActivePort");
    const cdpDeadline = Date.now() + 12000;
    while (Date.now() < cdpDeadline) {
      if (fs.existsSync(activePortFile)) {
        const lines = fs.readFileSync(activePortFile, "utf8").trim().split(/\r?\n/);
        if (lines[0] && Number(lines[0]) > 0) {
          inst.cdpHttpUrl = `http://127.0.0.1:${Number(lines[0])}`;
          break;
        }
      }
      await sleep(150);
    }
    if (!inst.cdpHttpUrl) throw new Error("Headless Chrome did not write DevToolsActivePort.");

    const domDeadline = Date.now() + 12000;
    let hydrated = false;
    while (Date.now() < domDeadline) {
      try {
        const mounted = await withCdpPage(inst, ({ evalJson }) =>
          evalJson(`Boolean(document.querySelector('[aria-label="Unified workspace bar"]'))`),
        );
        if (mounted) {
          hydrated = true;
          break;
        }
      } catch {
        // hydrating
      }
      await sleep(200);
    }
    if (!hydrated) throw new Error("React /app shell did not mount '[aria-label=\"Unified workspace bar\"]'.");

    fs.writeFileSync(metaPath, JSON.stringify(inst, null, 2) + "\n", "utf8");
    console.log(
      JSON.stringify(
        {
          ok: true,
          stateDir: inst.stateDir,
          port: inst.port,
          apiBaseUrl: inst.apiBaseUrl,
          appUrl: `http://127.0.0.1:${inst.port}/app?token=<redacted>`,
          serverPid: inst.serverPid,
          chromePid: inst.chromePid,
          runtimeDbPath: inst.runtimeDbPath,
        },
        null,
        2,
      ),
    );
  } catch (err) {
    if (inst.chromePid) await terminatePid(inst.chromePid);
    if (inst.serverPid) await terminatePid(inst.serverPid);
    die(`Launch failed: ${err.message}`, { stateDir });
  } finally {
    fs.closeSync(uvicornLogFd);
    fs.closeSync(chromeLogFd);
  }
}

async function cmdDoctor(flags) {
  const stateDir = resolveStateDir(flags);
  const inst = loadInstance(stateDir);
  const checks = {
    serverPidAlive: isPidAlive(inst.serverPid),
    chromePidAlive: isPidAlive(inst.chromePid),
    isolatedRuntimeDb: inst.runtimeDbPath.startsWith(inst.stateDir) && fs.existsSync(inst.runtimeDbPath),
    authGateOwnedByUs: false,
    overviewReady: false,
    browserHydrated: false,
    pageTitle: null,
    activeWorkspace: null,
  };
  try {
    const [unauth, authed] = await Promise.all([
      fetch(`${inst.apiBaseUrl}/v1/platform/overview`),
      fetch(`${inst.apiBaseUrl}/v1/platform/overview`, { headers: { Authorization: `Bearer ${inst.token}` } }),
    ]);
    checks.authGateOwnedByUs = unauth.status === 401 && authed.status === 200;
    checks.overviewReady = authed.status === 200;
  } catch (err) {
    checks.httpError = err.message;
  }
  if (checks.chromePidAlive) {
    try {
      const ui = await withCdpPage(inst, ({ evalJson }) =>
        evalJson(`({
          hydrated: Boolean(document.querySelector('[aria-label="Unified workspace bar"]')),
          title: document.title,
          workspace: document.querySelector('[aria-label="Active workspace switcher"]')?.value || null
        })`),
      );
      checks.browserHydrated = Boolean(ui?.hydrated);
      checks.pageTitle = ui?.title || null;
      checks.activeWorkspace = ui?.workspace || null;
    } catch (err) {
      checks.cdpError = err.message;
    }
  }
  const healthy =
    checks.serverPidAlive &&
    checks.chromePidAlive &&
    checks.isolatedRuntimeDb &&
    checks.authGateOwnedByUs &&
    checks.overviewReady &&
    checks.browserHydrated;
  console.log(JSON.stringify({ ok: healthy, healthy, stateDir, port: inst.port, checks }, null, 2));
  process.exit(healthy ? 0 : 1);
}

async function cmdCli(flags, passthrough) {
  if (!passthrough.length) die("cli requires arguments after '--', e.g.: control-keelway cli -- vault list --json");
  const inst = loadInstance(resolveStateDir(flags));
  const proc = spawnSync(inst.pythonBin, [path.join(inst.repoRoot, "cli.py"), ...passthrough], {
    cwd: inst.workspaceDir,
    env: buildIsolatedEnv(inst),
    encoding: "utf8",
  });
  let parsedJson = null;
  try {
    parsedJson = JSON.parse((proc.stdout || "").trim());
  } catch {
    parsedJson = null;
  }
  const payload = {
    ok: proc.status === 0,
    exitCode: proc.status,
    argv: ["cli.py", ...passthrough],
    stdout: proc.stdout || "",
    stderr: proc.stderr || "",
    ...(parsedJson !== null ? { json: parsedJson } : {}),
  };
  const savedTo = writeOutIfRequested(flags.out, payload, false);
  console.log(JSON.stringify({ ...payload, ...(savedTo ? { out: savedTo } : {}) }, null, 2));
  process.exit(proc.status ?? 1);
}

async function cmdApi(flags) {
  const inst = loadInstance(resolveStateDir(flags));
  const method = String(flags.method || "GET").toUpperCase();
  const reqPath = String(flags.path || "/v1/platform/overview");
  const headers = { Authorization: `Bearer ${inst.token}` };
  if (flags.role) headers["X-Keelway-Role"] = String(flags.role);
  if (flags.actor) headers["X-Keelway-Actor"] = String(flags.actor);
  if (flags.body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${inst.apiBaseUrl}${reqPath}`, {
    method,
    headers,
    body: flags.body ? String(flags.body) : undefined,
  });
  const raw = await res.text();
  let body = raw;
  try {
    body = JSON.parse(raw);
  } catch {
    // text/SSE
  }
  const payload = { ok: res.ok, status: res.status, method, path: reqPath, body };
  const savedTo = writeOutIfRequested(flags.out, payload, false);
  console.log(JSON.stringify({ ...payload, ...(savedTo ? { out: savedTo } : {}) }, null, 2));
  process.exit(res.ok ? 0 : 1);
}

async function cmdDbQuery(flags) {
  const sql = String(flags.sql || "").trim();
  if (!sql) die("db-query requires --sql <SELECT ...>.");
  if (!/^(select|with|pragma)\b/i.test(sql)) die("db-query is strictly read-only: query must begin with SELECT, WITH, or PRAGMA.");
  const inst = loadInstance(resolveStateDir(flags));
  const pySnippet = [
    "import json, sqlite3, sys",
    "db_path, query = sys.argv[1], sys.argv[2]",
    "conn = sqlite3.connect(db_path, timeout=10.0)",
    "conn.row_factory = sqlite3.Row",
    "conn.execute('PRAGMA query_only = ON')",
    "cur = conn.execute(query)",
    "rows = [{k: (v.hex() if isinstance(v, (bytes, bytearray)) else v) for k, v in dict(r).items()} for r in cur.fetchall()]",
    "print(json.dumps({'rowCount': len(rows), 'rows': rows}))",
    "conn.close()",
  ].join("; ");
  const proc = spawnSync(inst.pythonBin, ["-c", pySnippet, inst.runtimeDbPath, sql], { encoding: "utf8" });
  if (proc.status !== 0) die("Read-only SQLite query failed", { stderr: proc.stderr, sql });
  const result = { ok: true, runtimeDbPath: inst.runtimeDbPath, sql, ...JSON.parse(proc.stdout.trim()) };
  const savedTo = writeOutIfRequested(flags.out, result, false);
  console.log(JSON.stringify({ ...result, ...(savedTo ? { out: savedTo } : {}) }, null, 2));
}

async function cmdCleanup(flags) {
  const stateDir = resolveStateDir(flags);
  const metaPath = path.join(stateDir, "instance.json");
  const stopped = [];
  if (fs.existsSync(metaPath)) {
    const inst = JSON.parse(fs.readFileSync(metaPath, "utf8"));
    if (inst.chromePid) stopped.push(await terminatePid(inst.chromePid));
    if (inst.serverPid) stopped.push(await terminatePid(inst.serverPid));
  }
  if (fs.existsSync(stateDir)) fs.rmSync(stateDir, { recursive: true, force: true });
  console.log(JSON.stringify({ ok: true, action: "cleanup", stateDirRemoved: !fs.existsSync(stateDir), stateDir, stopped }, null, 2));
}

const { flags, positional, passthrough } = parseFlags(process.argv.slice(2));
const command = positional[0];

switch (command) {
  case "launch":
    await cmdLaunch(flags);
    break;
  case "doctor":
    await cmdDoctor(flags);
    break;
  case "browser":
    await runBrowserSubcommand(positional[1], loadInstance(resolveStateDir(flags)), flags, { die, writeOutIfRequested });
    break;
  case "cli":
    await cmdCli(flags, passthrough);
    break;
  case "api":
    await cmdApi(flags);
    break;
  case "db-query":
    await cmdDbQuery(flags);
    break;
  case "cleanup":
    await cmdCleanup(flags);
    break;
  default:
    die("Usage: control-keelway <launch|doctor|browser|cli|api|db-query|cleanup> [--state-dir <DIR>] ...");
}
