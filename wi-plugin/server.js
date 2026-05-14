/**
 * DVR CLI Bridge — Workflow Integration plugin client.
 *
 * Polls http://localhost:50420/inbox for tasks issued by the `dvr` CLI,
 * executes them via the DaVinci Resolve JS API, and POSTs the result back
 * to /result. The CLI tears down its temporary HTTP server as soon as it
 * receives the result.
 *
 * Protocol (see src/dvr/wi_client.py for the server side):
 *   GET  /ping   → { ok: true }
 *   GET  /inbox  → 200 { id, method, params } | 204 (no task)
 *   POST /result body { id, result } or { id, error, hint? }
 */

const BRIDGE_PORT = 50420;
const POLL_INTERVAL_MS = 400;

const dot = document.getElementById("dot");
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");

function log(line) {
  const ts = new Date().toISOString().slice(11, 19);
  logEl.textContent += `[${ts}] ${line}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

function setLive() { dot.className = "dot live"; statusEl.textContent = "Connected — task in flight"; }
function setIdle() { dot.className = "dot idle"; statusEl.textContent = "Idle — polling localhost:50420…"; }
function setError(msg) { dot.className = "dot error"; statusEl.textContent = msg; }

let resolve = null;
try {
  // WorkflowIntegration is injected by Resolve into the page context.
  resolve = WorkflowIntegration.GetResolve();
  log("Resolve bridge acquired (version " + resolve.GetVersionString() + ")");
} catch (e) {
  log("WorkflowIntegration.GetResolve() failed: " + e);
  setError("Resolve bridge unavailable");
}

// ----- task handlers -----

function withProjectTimeline(handler) {
  if (!resolve) return { error: "resolve_unavailable" };
  const pm = resolve.GetProjectManager();
  const proj = pm.GetCurrentProject();
  if (!proj) return { error: "no_project_open" };
  const tl = proj.GetCurrentTimeline();
  if (!tl) return { error: "no_timeline_selected" };
  return handler(proj, tl);
}

function tcToFrames(tc, fps) {
  // HH:MM:SS:FF
  const m = /^(\d{1,2}):(\d{2}):(\d{2})[:;](\d{1,2})$/.exec(tc.trim());
  if (!m) throw new Error("invalid timecode: " + tc);
  const fpsInt = Math.round(fps);
  const f = parseInt(m[4], 10);
  if (f >= fpsInt) throw new Error("frame >= fps: " + tc);
  return ((+m[1]) * 3600 + (+m[2]) * 60 + (+m[3])) * fpsInt + f;
}

const handlers = {
  ping: function () {
    return { result: { ok: true, version: resolve ? resolve.GetVersionString() : null } };
  },
  "timeline.cut": function (params) {
    return withProjectTimeline(function (proj, tl) {
      try {
        const fps = parseFloat(tl.GetSetting("timelineFrameRate")) || 24;
        const frame = tcToFrames(params.at, fps);
        // Note: Resolve has no public razor API. v0.2 places a marker as a
        // proxy cut signal, and the user can rip-cut via UI keyboard shortcut.
        // True razor-cut requires deeper API hooks (deferred to v0.3).
        const ok = tl.AddMarker(frame, "Red", "dvr-cut", "razor proposal", 1);
        return ok ? { result: { ok: true, frame: frame, note: "placeholder marker added; UI keyboard shortcut B + B is required for true razor cut until Resolve exposes a SplitClip API" } }
                  : { error: "AddMarker returned false (frame likely outside timeline)" };
      } catch (e) {
        return { error: String(e) };
      }
    });
  },
  "timeline.move": function (params) {
    return withProjectTimeline(function (proj, tl) {
      // Resolve JS API does not expose a clip-move primitive either.
      // v0.2 returns a structured "unsupported" payload to be honest about scope.
      return { error: "timeline.move is not yet implementable via the Workflow Integrations JS surface (deferred to v0.3)" };
    });
  }
};

// ----- poll loop -----

async function pollOnce() {
  let resp;
  try {
    resp = await fetch(`http://localhost:${BRIDGE_PORT}/inbox`, { cache: "no-store" });
  } catch (e) {
    // CLI not running; that's normal — try again later.
    setIdle();
    return;
  }
  if (resp.status === 204) { setIdle(); return; }
  if (!resp.ok) { setError("inbox responded " + resp.status); return; }

  setLive();
  const task = await resp.json();
  log("→ " + task.method + " " + JSON.stringify(task.params));

  const handler = handlers[task.method];
  let payload;
  if (!handler) {
    payload = { id: task.id, error: "unknown_method", hint: "method: " + task.method };
  } else {
    try {
      const r = handler(task.params || {});
      if (r && r.error) payload = { id: task.id, error: r.error, hint: r.hint };
      else              payload = { id: task.id, result: r ? r.result : null };
    } catch (e) {
      payload = { id: task.id, error: String(e) };
    }
  }
  log("← " + (payload.error ? "error: " + payload.error : "ok"));
  try {
    await fetch(`http://localhost:${BRIDGE_PORT}/result`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    log("POST /result failed: " + e);
  }
  setIdle();
}

setInterval(pollOnce, POLL_INTERVAL_MS);
setIdle();
log("Bridge started, polling every " + POLL_INTERVAL_MS + "ms");
