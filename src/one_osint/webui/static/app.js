// one-osint web UI - vanilla JS, no dependencies
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const health = $("#health");
async function checkHealth() {
  try {
    const r = await fetch("/health");
    if (!r.ok) throw new Error(r.status);
    health.textContent = "● online";
    health.className = "status ok";
  } catch (e) {
    health.textContent = "● offline";
    health.className = "status err";
  }
}
checkHealth();
setInterval(checkHealth, 15000);

const form = $("#form");
const live = $("#live");
const events = $("#events");
const progress = $("#progress");
const tbody = $("#investigations tbody");
const report = $("#report");
const reportId = $("#report_id");
const reportBody = $("#report_body");

function appendEvent(ev) {
  const li = document.createElement("li");
  li.className = ev.type || "";
  let text = ev.type || "event";
  if (ev.module) text += " · " + ev.module;
  if (ev.target) text += " · " + ev.target;
  if (ev.type === "module_done") {
    if (ev.findings !== undefined) text += " · findings=" + ev.findings;
    if (ev.summary) text += " · " + ev.summary;
    if (ev.duration !== undefined) text += " · " + ev.duration.toFixed(1) + "s";
    if (ev.error) { li.classList.add("failed"); text += " · ERROR: " + ev.error; }
  }
  li.textContent = text;
  events.prepend(li);
  progress.textContent = ev.type === "investigation_done" ? "done" : "running";
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const target = $("#target").value.trim();
  if (!target) return;
  const modules = $("#modules").value.split(",").map(s => s.trim()).filter(Boolean);
  const body = {
    target,
    modules: modules.length ? modules : null,
    allow_loud: $("#allow_loud").checked,
    allow_opt_in: $("#allow_opt_in").checked,
    tor: $("#tor").checked,
  };
  events.innerHTML = "";
  live.hidden = false;
  progress.textContent = "starting…";
  try {
    const r = await fetch("/api/investigate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const t = await r.text();
      progress.textContent = "error: " + t;
      return;
    }
    const j = await r.json();
    const wsProto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${wsProto}://${location.host}/ws/investigate/${j.investigation_id}`);
    ws.onmessage = (m) => {
      try {
        const ev = JSON.parse(m.data);
        appendEvent(ev);
      } catch (e) { /* ignore */ }
    };
    ws.onclose = () => loadHistory();
  } catch (e) {
    progress.textContent = "error: " + e.message;
  }
});

async function loadHistory() {
  const r = await fetch("/api/investigations?limit=50");
  if (!r.ok) return;
  const rows = await r.json();
  tbody.innerHTML = "";
  for (const inv of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${inv.id.slice(0, 8)}</code></td>
      <td>${escapeHtml(inv.target)}</td>
      <td>${inv.input_type}</td>
      <td class="status ${inv.status}">${inv.status}</td>
      <td>${(inv.created_at || "").slice(0, 19)}</td>
      <td><button data-id="${inv.id}">view</button></td>`;
    tr.querySelector("button").onclick = () => showReport(inv.id, "md");
    tbody.appendChild(tr);
  }
}
$("#refresh").onclick = loadHistory;
loadHistory();
setInterval(loadHistory, 10000);

async function showReport(id, fmt) {
  reportId.textContent = id.slice(0, 8);
  report.hidden = false;
  $$(".actions button").forEach(b => b.classList.toggle("active", b.dataset.fmt === fmt));
  if (fmt === "json") {
    const r = await fetch("/api/report/" + id);
    const j = await r.json();
    reportBody.textContent = JSON.stringify(j, null, 2);
  } else {
    const r = await fetch("/api/report/" + id + "/export?format=" + fmt);
    reportBody.textContent = await r.text();
  }
}
$$(".actions button").forEach(b => b.onclick = () => {
  const id = reportId.dataset.fullId || reportId.textContent;
  // use full id from last shown — recover from text by matching first 8 chars
  showReportByShort(b.dataset.fmt, reportId.textContent);
});

async function showReportByShort(fmt, short) {
  // resolve full id from history
  const r = await fetch("/api/investigations?limit=200");
  const rows = await r.json();
  const full = rows.find(x => x.id.startsWith(short));
  if (full) { reportId.dataset.fullId = full.id; return showReport(full.id, fmt); }
  if (full) reportId.dataset.fullId = full.id;
  return showReport(short, fmt);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
