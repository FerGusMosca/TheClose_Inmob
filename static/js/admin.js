// static/js/admin.js
// SSE-powered pipeline UI — connects to /admin/stream and reacts to events

const STEPS = ["scrape_argenprop", "scrape_zonaprop", "insert", "embed"];

// ── SSE connection ────────────────────────────────────────────────────────────

let evtSource = null;

function connectSSE() {
    evtSource = new EventSource("/admin/stream");

    evtSource.addEventListener("init", e => {
        const states = JSON.parse(e.data);
        Object.entries(states).forEach(([step, state]) => applyState(step, state));
    });

    evtSource.addEventListener("state", e => {
        const d = JSON.parse(e.data);
        applyState(d.step, d);
    });

    evtSource.addEventListener("log", e => {
        const d = JSON.parse(e.data);
        appendLog(d.step, d.line, d.ts);
    });

    evtSource.onerror = () => {
        appendLog("system", "Connection lost — reconnecting...", now());
        setTimeout(connectSSE, 3000);
    };
}

// ── State rendering ───────────────────────────────────────────────────────────

function applyState(step, state) {
    const card    = document.getElementById(`card-${step}`);
    const meta    = document.getElementById(`meta-${step}`);
    const btn     = document.getElementById(`btn-${step}`);
    const bar     = document.getElementById(`bar-${step}`);

    if (!card) return;

    // Card class
    card.classList.remove("running", "done", "error");
    if (state.status !== "idle") card.classList.add(state.status);

    // Meta text
    if (meta) {
        let txt = state.message || "";
        if (state.count > 0) txt += ` (${state.count})`;
        if (state.ended_at) {
            const d = new Date(state.ended_at);
            txt += ` · ${d.toLocaleTimeString("es-AR")}`;
        }
        meta.textContent = txt || "Ready";
    }

    // Button
    if (btn) {
        btn.disabled = state.status === "running";
        btn.classList.toggle("running", state.status === "running");
        btn.innerHTML = state.status === "running"
            ? '<span class="btn-icon">⏳</span> Running…'
            : '<span class="btn-icon">▶</span> Run';
    }

    // Progress bar
    if (bar) {
        bar.className = "progress-bar";
        if (state.status === "running") bar.classList.add("running");
        if (state.status === "done")    bar.classList.add("done");
        if (state.status === "error")   bar.classList.add("error");
        if (state.status === "idle")    bar.style.width = "0%";
    }

    // Global status indicator
    updateGlobalStatus();
}

function updateGlobalStatus() {
    const dot   = document.getElementById("global-dot");
    const label = document.getElementById("global-label");
    const cards = STEPS.map(s => document.getElementById(`card-${s}`));

    if (cards.some(c => c && c.classList.contains("running"))) {
        dot.className   = "status-dot running";
        label.textContent = "Running";
    } else if (cards.some(c => c && c.classList.contains("error"))) {
        dot.className   = "status-dot error";
        label.textContent = "Error";
    } else if (cards.every(c => c && c.classList.contains("done"))) {
        dot.className   = "status-dot done";
        label.textContent = "All done";
    } else {
        dot.className   = "status-dot";
        label.textContent = "Idle";
    }
}

// ── Log console ───────────────────────────────────────────────────────────────

function appendLog(step, line, ts) {
    const body = document.getElementById("log-body");

    let cls = "log-line--info";
    if (line.startsWith("ERROR") || line.includes("error"))  cls = "log-line--error";
    else if (line.startsWith("Warning") || line.includes("warn")) cls = "log-line--warn";
    else if (line.includes("done") || line.includes("OK") || line.includes("complete")) cls = "log-line--ok";

    const div = document.createElement("div");
    div.className = `log-line ${cls}`;
    div.textContent = `[${ts || now()}] [${step}] ${line}`;
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
}

function clearLog() {
    const body = document.getElementById("log-body");
    body.innerHTML = '<div class="log-line log-line--system">── Log cleared ──</div>';
}

function now() {
    return new Date().toLocaleTimeString("es-AR");
}

// ── Action handlers ───────────────────────────────────────────────────────────

async function runScrape(portal) {
    const prefix       = portal === "argenprop" ? "ap" : "zp";
    const neighborhood = document.getElementById(`${prefix}-neighborhood`).value;
    const max_pages    = parseInt(document.getElementById(`${prefix}-pages`).value) || 3;

    appendLog("system", `Starting ${portal} scrape — ${neighborhood} · ${max_pages} pages`, now());

    const res = await fetch(`/admin/scrape/${portal}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ neighborhood, max_pages }),
    });
    const data = await res.json();
    if (!data.ok) appendLog("system", `Could not start: ${data.msg}`, now());
}

async function runInsert() {
    const portals = [];
    if (document.getElementById("ins-argenprop").checked) portals.push("argenprop");
    if (document.getElementById("ins-zonaprop").checked)  portals.push("zonaprop");

    if (!portals.length) {
        appendLog("system", "Select at least one portal", now());
        return;
    }

    appendLog("system", `Starting insert — portals: ${portals.join(", ")}`, now());

    const res = await fetch("/admin/insert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ portals }),
    });
    const data = await res.json();
    if (!data.ok) appendLog("system", `Could not start: ${data.msg}`, now());
}

async function runEmbed() {
    appendLog("system", "Starting embedding generation…", now());
    const res  = await fetch("/admin/embed", { method: "POST" });
    const data = await res.json();
    if (!data.ok) appendLog("system", `Could not start: ${data.msg}`, now());
}

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", connectSSE);