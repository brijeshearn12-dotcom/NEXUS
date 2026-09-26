// capture_demo_screens.mjs — Task 9.2 backups: real screenshots of every key demo screen.
//
// Drives a headless Edge/Chrome over the DevTools protocol through the REAL running UI (no
// mock data, no image editing) and saves one PNG per screen plus manifest.json recording the
// URL, timestamp and any console errors seen while capturing.
//
//   node scripts/capture_demo_screens.mjs --base http://localhost:3000 --out ../demo-backups/run1
//   node scripts/capture_demo_screens.mjs --base https://nexus-frontend-qtak.onrender.com --out ... --case case_100478559
//
// Options: --case <id> (default case_100478559)  --doc <document id> (default doc_<case suffix>)
//          --width 1366 --height 768  --browser <path to msedge/chrome>
//          --interactive   also capture the What-If simulation screen (POST /simulate; writes one
//                          audit-log entry on the target backend). Off by default.
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const argv = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : fallback;
};
const flag = (name) => argv.includes(`--${name}`);

const BASE = opt("base", "http://localhost:3000").replace(/\/$/, "");
const OUT = resolve(opt("out", "demo-backups"));
const CASE = opt("case", "case_100478559");
const DOC = opt("doc", `doc_${CASE.replace(/^case_/, "")}`);
const WIDTH = Number(opt("width", "1366"));
const HEIGHT = Number(opt("height", "768"));
const INTERACTIVE = flag("interactive");
const BROWSER =
  opt("browser") ||
  [
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ].find((p) => existsSync(p));

if (!BROWSER) {
  console.error("No Edge/Chrome found; pass --browser <path>.");
  process.exit(2);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// In-page helpers used by the click steps (run inside the page).
const CLICK = (re, scope = "document") =>
  `(() => { const root = ${scope}; const b = [...root.querySelectorAll('button')].find(x => ${re}.test(x.textContent.trim())); if (b) { b.click(); return true; } return false; })()`;

const screens = [
  { name: "01_command_center", url: "/command-center", wait: 7000 },
  { name: "02_corpus", url: "/corpus", wait: 7000 },
  { name: "03_case_graph", url: `/cases/${CASE}/graph`, wait: 9000 },
  { name: "04_key_individuals", steps: [CLICK("/^Key \\(\\d+\\)$/")], wait: 1500 },
  { name: "05_reasoning_trail", steps: [CLICK("/View Reasoning Trail/")], wait: 1500 },
  { name: "06_entity_inspector_provenance", steps: [CLICK("/Locate on graph/")], wait: 2500 },
  {
    name: "07_pattern_flag_trail",
    steps: [CLICK("/^Flags \\(\\d+\\)$/"), CLICK("/^Inspect Reasoning Trail/")],
    wait: 1500,
  },
  { name: "08_what_if_simulation", interactive: true, steps: [CLICK("/^Simulate Removal/")], wait: 4000 },
  { name: "09_audit_trail", steps: [CLICK("/Exit Simulation/"), CLICK("/^Audit$/")], wait: 2500 },
  { name: "10_document_entities_provenance", url: `/corpus/${DOC}/entities`, wait: 7000 },
  { name: "11_entities", url: "/entities", wait: 7000 },
  { name: "12_dashboard", url: "/dashboard", wait: 7000 },
];

async function main() {
  mkdirSync(OUT, { recursive: true });
  const profile = mkdtempSync(join(tmpdir(), "nexus-capture-"));
  const port = 9300 + Math.floor(Math.random() * 500);
  const browser = spawn(
    BROWSER,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      `--window-size=${WIDTH},${HEIGHT}`,
      "about:blank",
    ],
    { stdio: "ignore" }
  );

  let pageWs;
  for (let i = 0; i < 60 && !pageWs; i++) {
    await sleep(500);
    try {
      const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      pageWs = targets.find((t) => t.type === "page")?.webSocketDebuggerUrl;
    } catch {
      /* browser still starting */
    }
  }
  if (!pageWs) throw new Error("Could not connect to the headless browser.");

  const ws = new WebSocket(pageWs);
  await new Promise((r, j) => {
    ws.onopen = r;
    ws.onerror = j;
  });
  let nextId = 1;
  const pending = new Map();
  const consoleErrors = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    } else if (msg.method === "Runtime.exceptionThrown") {
      consoleErrors.push(msg.params.exceptionDetails?.exception?.description?.split("\n")[0] || "exception");
    } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      consoleErrors.push(String(msg.params.args?.[0]?.value ?? "console.error").slice(0, 200));
    }
  };
  const send = (method, params = {}) =>
    new Promise((r) => {
      const id = nextId++;
      pending.set(id, r);
      ws.send(JSON.stringify({ id, method, params }));
    });

  await send("Runtime.enable");
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });

  const manifest = { base: BASE, case: CASE, viewport: `${WIDTH}x${HEIGHT}`, interactive: INTERACTIVE, screens: [] };
  for (const s of screens) {
    if (s.interactive && !INTERACTIVE) {
      manifest.screens.push({ name: s.name, skipped: "needs --interactive (writes an audit entry)" });
      continue;
    }
    const before = consoleErrors.length;
    if (s.url) await send("Page.navigate", { url: BASE + s.url });
    for (const step of s.steps || []) {
      const res = await send("Runtime.evaluate", { expression: step, returnByValue: true });
      if (res.result?.result?.value === false) manifest.screens.push({ name: s.name, warning: `control not found: ${step.slice(0, 80)}` });
      await sleep(600);
    }
    await sleep(s.wait);
    const shot = await send("Page.captureScreenshot", { format: "png" });
    const file = `${s.name}.png`;
    writeFileSync(join(OUT, file), Buffer.from(shot.result.data, "base64"));
    const url = (await send("Runtime.evaluate", { expression: "location.href", returnByValue: true })).result.result.value;
    manifest.screens.push({ name: s.name, file, url, captured_at: new Date().toISOString(), console_errors: consoleErrors.slice(before) });
    console.log(`captured ${file}${consoleErrors.length > before ? `  (${consoleErrors.length - before} console errors)` : ""}`);
  }
  writeFileSync(join(OUT, "manifest.json"), JSON.stringify(manifest, null, 2));
  ws.close();
  browser.kill();
  await sleep(500);
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {
    /* profile still locked; harmless temp folder */
  }
  console.log(`\n${manifest.screens.filter((x) => x.file).length} screenshots + manifest.json -> ${OUT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
