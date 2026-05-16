const $ = (id) => document.getElementById(id);

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

async function refreshList() {
  const items = await api("/api/investigations");
  const tbody = document.querySelector("#invList tbody");
  tbody.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.issue_key}</td>
      <td class="status-${it.status}">${it.status}</td>
      <td>${new Date(it.updated_at).toLocaleString()}</td>
      <td><button data-id="${it.id}">View</button></td>
    `;
    tr.querySelector("button").onclick = () => loadReport(it.id);
    tbody.appendChild(tr);
  }
}

function classTag(cls) {
  const map = { LIKELY_REGRESSION: "bad", LIKELY_INTENTIONAL: "good", UNCLEAR: "warn" };
  return `<span class="tag ${map[cls] || ''}">${cls}</span>`;
}

async function loadReport(id) {
  const inv = await api(`/api/investigations/${id}`);
  $("reportPanel").hidden = false;
  const meta = [`<span class="tag">${inv.issue_key}</span>`, `<span class="tag">${inv.status}</span>`];
  if (inv.report) {
    meta.push(classTag(inv.report.classification));
    meta.push(`<span class="tag">Recommend: ${inv.report.recommendation}</span>`);
    meta.push(`<span class="tag">Confidence ${inv.report.confidence}</span>`);
  }
  if (inv.error) meta.push(`<span class="tag bad">Error: ${inv.error}</span>`);
  $("reportMeta").innerHTML = meta.join(" ");
  $("reportMarkdown").textContent = inv.report ? inv.report.summary_markdown : "(report not ready yet — refresh in a moment)";
  $("reportPayload").textContent = JSON.stringify(inv, null, 2);
}

let pollTimer = null;
async function pollUntilDone(id) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const inv = await api(`/api/investigations/${id}`);
    await refreshList();
    if (inv.status === "COMPLETED" || inv.status === "FAILED") {
      clearInterval(pollTimer);
      pollTimer = null;
      $("status").textContent = `Investigation ${inv.status.toLowerCase()}.`;
      loadReport(id);
    } else {
      $("status").textContent = `Working… ${inv.status}`;
    }
  }, 1500);
}

$("analyze").onclick = async () => {
  const issueKey = $("issueKey").value.trim();
  const repos = $("repos").value.split(",").map((s) => s.trim()).filter(Boolean);
  if (!issueKey) return;
  $("status").textContent = "Submitting…";
  const inv = await api("/api/investigations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ issue_key: issueKey, repos, triggered_by: "ui" }),
  });
  $("status").textContent = `Created investigation ${inv.id}`;
  await refreshList();
  pollUntilDone(inv.id);
};

refreshList();
