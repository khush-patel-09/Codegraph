let network = null;
let currentRiskCategory = "functions";

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function setHealth(ok, message) {
  const el = document.getElementById("health");
  el.textContent = message;
  el.className = "pill " + (ok ? "ok" : "err");
}

async function loadHealth() {
  try {
    await api("/api/health");
    setHealth(true, "Neo4j connected");
  } catch (err) {
    setHealth(false, "Neo4j offline");
  }
}

async function loadStats() {
  try {
    const s = await api("/api/stats");
    document.getElementById("stat-files").textContent = s.files ?? 0;
    document.getElementById("stat-functions").textContent = s.functions ?? 0;
    document.getElementById("stat-calls").textContent = s.calls ?? 0;
    document.getElementById("stat-imports").textContent = s.imports ?? 0;
  } catch (_) {
    /* graph may be empty */
  }
}

function renderGraph(data) {
  const container = document.getElementById("graph");
  const nodes = new vis.DataSet(
    data.nodes.map((n) => ({
      id: n.id,
      label: n.type === "File" ? n.file : n.name,
      group: n.type,
      title: n.type === "File" ? n.file : `${n.name}\n${n.file}`,
    }))
  );
  const edges = new vis.DataSet(
    data.edges.map((e, i) => ({
      id: i,
      from: e.source,
      to: e.target,
      label: e.rel,
      arrows: "to",
      font: { size: 10, color: "#8fa3bf" },
      color: { color: "#4a607a" },
    }))
  );

  const options = {
    physics: { stabilization: true },
    groups: {
      File: { color: { background: "#2a4a6b", border: "#5b9cff" }, shape: "box" },
      Function: { color: { background: "#2a3d32", border: "#3ddc97" }, shape: "ellipse" },
    },
    interaction: { hover: true },
  };

  if (network) network.destroy();
  network = new vis.Network(container, { nodes, edges }, options);
}

async function loadGraph() {
  try {
    const data = await api("/api/graph");
    if (!data.nodes || data.nodes.length === 0) {
      document.getElementById("graph").innerHTML =
        '<p style="padding:1rem;color:#8fa3bf">No graph yet. Index a project first.</p>';
      return;
    }
    renderGraph(data);
  } catch (err) {
    document.getElementById("graph").innerHTML =
      `<p style="padding:1rem;color:#ff6b6b">${err.message}</p>`;
  }
}

async function loadRisk() {
  const out = document.getElementById("risk-result");
  out.innerHTML = "<p>Loading risk analysis...</p>";
  try {
    const path = currentRiskCategory === "files" ? "/api/risk/files" : "/api/risk/functions";
    const items = await api(path);
    if (!items || items.length === 0) {
      out.innerHTML = "<p>No risk data available.</p>";
      return;
    }
    if (currentRiskCategory === "files") {
      out.innerHTML = items
        .map(
          (f) =>
            `<div class="item risk-card">` +
            `<div class="risk-badge ${f.level.toLowerCase()}">${f.level} (${f.risk_score})</div>` +
            `<strong>${f.path}</strong>` +
            `<div class="sub-text">${f.importers_count} importers • ${f.function_count} functions • ${f.churn} commits</div>` +
            `</div>`
        )
        .join("");
    } else {
      out.innerHTML = items
        .map(
          (fn) =>
            `<div class="item risk-card">` +
            `<div class="risk-badge ${fn.level.toLowerCase()}">${fn.level} (${fn.risk_score})</div>` +
            `<strong>${fn.name}</strong> <span class="file-text">in ${fn.file}</span>` +
            `<div class="sub-text">${fn.in_degree} callers • ${fn.blast_radius} dependents • ${fn.line_count} LOC</div>` +
            `</div>`
        )
        .join("");
    }
  } catch (err) {
    out.innerHTML = `<p style="color:#ff6b6b">${err.message}</p>`;
  }
}

document.getElementById("index-btn").addEventListener("click", async () => {
  const path = document.getElementById("index-path").value.trim();
  const reset = document.getElementById("index-reset").checked;
  const out = document.getElementById("index-result");

  if (!path) {
    out.textContent = "Enter a folder path.";
    return;
  }

  out.textContent = "Indexing...";
  try {
    const result = await api("/api/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, reset }),
    });
    out.textContent = `Indexed ${result.indexed_files} files from ${result.path}`;
    await loadStats();
    await loadGraph();
    await loadRisk();
  } catch (err) {
    out.textContent = err.message;
  }
});

document.getElementById("impact-btn").addEventListener("click", async () => {
  const name = document.getElementById("impact-name").value.trim();
  const file = document.getElementById("impact-file").value.trim();
  const out = document.getElementById("impact-result");

  if (!name) {
    out.innerHTML = "<p>Enter a function name.</p>";
    return;
  }

  out.innerHTML = "<p>Analyzing...</p>";
  try {
    const params = new URLSearchParams({ name });
    if (file) params.set("file", file);
    const result = await api(`/api/impact/function?${params}`);

    if (result.affected.length === 0) {
      out.innerHTML = `<p>No callers found for <strong>${name}</strong>.</p>`;
      return;
    }

    const target = file ? `${file}::${name}` : name;
    out.innerHTML = `<p>Changing <strong>${target}</strong> may affect:</p>` +
      result.affected
        .map(
          (row) =>
            `<div class="item" style="margin-left:${(row.depth - 1) * 16}px">` +
            `<strong>${row.function}</strong> in ${row.file} (hop ${row.depth})</div>`
        )
        .join("");
  } catch (err) {
    out.innerHTML = `<p>${err.message}</p>`;
  }
});

document.getElementById("similar-btn").addEventListener("click", async () => {
  const name = document.getElementById("similar-name").value.trim();
  const out = document.getElementById("similar-result");

  if (!name) {
    out.innerHTML = "<p>Enter a function name.</p>";
    return;
  }

  out.innerHTML = "<p>Searching ML vector space...</p>";
  try {
    const params = new URLSearchParams({ name });
    const result = await api(`/api/similar?${params}`);

    if (!result.similar || result.similar.length === 0) {
      out.innerHTML = `<p>No similar functions found for <strong>${name}</strong>.</p>`;
      return;
    }

    out.innerHTML = result.similar
      .map(
        (s) =>
          `<div class="item sim-card">` +
          `<div class="sim-score">Match: ${(s.similarity_score * 100).toFixed(1)}%</div>` +
          `<strong>${s.name}</strong> <span class="file-text">in ${s.file}</span>` +
          `${s.docstring ? `<div class="docstring">"${s.docstring}"</div>` : ""}` +
          `</div>`
      )
      .join("");
  } catch (err) {
    out.innerHTML = `<p style="color:#ff6b6b">${err.message}</p>`;
  }
});

document.getElementById("risk-fn-btn").addEventListener("click", (e) => {
  currentRiskCategory = "functions";
  document.getElementById("risk-fn-btn").className = "active";
  document.getElementById("risk-file-btn").className = "secondary";
  loadRisk();
});

document.getElementById("risk-file-btn").addEventListener("click", (e) => {
  currentRiskCategory = "files";
  document.getElementById("risk-file-btn").className = "active";
  document.getElementById("risk-fn-btn").className = "secondary";
  loadRisk();
});

document.getElementById("refresh-graph").addEventListener("click", () => {
  loadGraph();
  loadStats();
  loadRisk();
});

loadHealth();
loadStats();
loadGraph();
loadRisk();
