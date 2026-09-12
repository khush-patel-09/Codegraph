// Codegraph Studio Controller — Light Theme & Apple Design System
let network = null;
let graphNodes = new vis.DataSet();
let graphEdges = new vis.DataSet();
let allRawNodes = [];
let allRawEdges = [];
let activeFilters = { File: true, Function: true, Class: true };
let currentRiskTab = 'functions';
let physicsEnabled = true;

// Utility API Helper
async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText || 'API Error');
  return data;
}

// Toast Notifications (Clean, no emojis)
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast-bubble';
  if (type === 'error') {
    toast.style.borderColor = 'rgba(197, 48, 38, 0.4)';
    toast.style.color = '#C53026';
  } else if (type === 'success') {
    toast.style.borderColor = 'rgba(139, 154, 110, 0.5)';
    toast.style.color = '#53643B';
  }
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(6px)';
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

// Health & Stats Initialization
async function initHealthAndStats() {
  const pill = document.getElementById('connection-pill');
  const text = document.getElementById('connection-text');
  try {
    const health = await api('/api/health');
    pill.className = 'status-indicator connected';
    text.textContent = 'Neo4j Connected';
  } catch (err) {
    pill.className = 'status-indicator';
    text.textContent = 'Neo4j Offline';
  }

  try {
    const s = await api('/api/stats');
    document.getElementById('stat-files').textContent = s.files ?? 0;
    document.getElementById('stat-functions').textContent = s.functions ?? 0;
    document.getElementById('stat-classes').textContent = s.classes ?? 0;
    document.getElementById('stat-calls').textContent = s.calls ?? 0;
    document.getElementById('stat-imports').textContent = s.imports ?? 0;
  } catch (_) {}
}

// Node & Edge Styles matched to the light palette
function buildNodeStyle(n) {
  const isHighRisk = (n.in_degree || 0) >= 3 || (n.churn || 0) >= 5;
  
  if (n.type === 'File') {
    return {
      id: n.id,
      label: n.file || n.label,
      group: 'File',
      shape: 'box',
      margin: 8,
      color: {
        background: '#EAE2D6',
        border: '#848F83',
        highlight: { background: '#DFD5C5', border: '#576156' }
      },
      font: { color: '#1C211B', face: '-apple-system, BlinkMacSystemFont, "Inter"', size: 11, bold: true },
      borderWidth: 1.2,
      shadow: { enabled: true, color: 'rgba(0, 0, 0, 0.04)', size: 4, x: 0, y: 1 }
    };
  } else if (n.type === 'Class') {
    return {
      id: n.id,
      label: n.name || n.label,
      group: 'Class',
      shape: 'diamond',
      size: 18,
      color: {
        background: '#D9D0C1',
        border: '#786F60',
        highlight: { background: '#C8BEAE', border: '#5A5245' }
      },
      font: { color: '#1C211B', face: '-apple-system, BlinkMacSystemFont, "Inter"', size: 11, bold: true },
      borderWidth: 1.2,
      shadow: { enabled: true, color: 'rgba(0, 0, 0, 0.04)', size: 4, x: 0, y: 1 }
    };
  } else {
    // Function
    const borderColor = isHighRisk ? '#C53026' : '#68774F';
    const bgColor = isHighRisk ? '#FCE8E6' : '#8B9A6E';
    const textColor = isHighRisk ? '#C53026' : '#1C211B';
    return {
      id: n.id,
      label: n.name || n.label,
      group: 'Function',
      shape: 'dot',
      size: 11 + Math.min(12, (n.in_degree || 0) * 2),
      color: {
        background: bgColor,
        border: borderColor,
        highlight: { background: '#7A895F', border: '#4E5A3A' }
      },
      font: { color: textColor, face: '-apple-system, BlinkMacSystemFont, "Inter"', size: 11 },
      borderWidth: isHighRisk ? 2 : 1.2,
      shadow: { enabled: true, color: isHighRisk ? 'rgba(197, 48, 38, 0.15)' : 'rgba(0, 0, 0, 0.04)', size: 4, x: 0, y: 1 }
    };
  }
}

function buildEdgeStyle(e, i) {
  let color = '#9BA59B';
  let dashes = false;
  
  if (e.rel === 'CALLS') {
    color = '#7A895F';
  } else if (e.rel === 'IMPORTS') {
    color = '#64748B';
    dashes = [3, 3];
  } else if (e.rel === 'INHERITS_FROM') {
    color = '#8F8270';
    dashes = [2, 2];
  }

  return {
    id: i,
    from: e.source,
    to: e.target,
    label: e.rel,
    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
    color: { color, highlight: '#1C211B' },
    font: { color: '#687268', size: 9, face: 'JetBrains Mono', strokeWidth: 0 },
    dashes: dashes,
    smooth: { type: 'cubicBezier', roundness: 0.25 }
  };
}

async function loadStudioGraph() {
  const container = document.getElementById('studio-graph');
  try {
    const data = await api('/api/graph?limit=300');
    allRawNodes = data.nodes || [];
    allRawEdges = data.edges || [];

    if (allRawNodes.length === 0) {
      container.innerHTML = `
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:#576156;gap:0.75rem;">
          <p style="font-size:1rem;font-weight:600;color:#1C211B;">No Graph Data</p>
          <p style="font-size:0.85rem;">Index a codebase to visualize dependencies and call graphs.</p>
          <button class="btn btn-primary btn-sm" onclick="document.getElementById('open-index-modal-btn').click()">Index Sample Codebase</button>
        </div>`;
      return;
    }

    container.innerHTML = '';
    const formattedNodes = allRawNodes.map(buildNodeStyle);
    const formattedEdges = allRawEdges.map(buildEdgeStyle);

    graphNodes = new vis.DataSet(formattedNodes);
    graphEdges = new vis.DataSet(formattedEdges);

    const options = {
      physics: {
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
          gravitationalConstant: -32,
          centralGravity: 0.007,
          springLength: 75,
          springConstant: 0.09,
          damping: 0.85
        },
        stabilization: { iterations: 100 }
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        zoomView: true,
        dragView: true
      }
    };

    network = new vis.Network(container, { nodes: graphNodes, edges: graphEdges }, options);

    network.on('click', async (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        openNodeInspector(nodeId);
      }
    });

  } catch (err) {
    container.innerHTML = `<div style="padding:1.5rem;color:#C53026;">Failed to load graph: ${err.message}</div>`;
  }
}

// Node Inspector Drawer
async function openNodeInspector(nodeId) {
  const drawer = document.getElementById('inspector-drawer');
  drawer.classList.remove('collapsed');

  try {
    const data = await api(`/api/node?id=${nodeId}`);
    
    document.getElementById('drawer-name').textContent = data.name || data.file || 'Component';
    document.getElementById('drawer-file').textContent = data.file || '';
    
    const label = (data.labels && data.labels[0]) || 'FUNCTION';
    const typeBadge = document.getElementById('drawer-type');
    typeBadge.textContent = label.toUpperCase();

    // Metrics
    document.getElementById('drawer-in-degree').textContent = (data.callers ? data.callers.length : 0);
    document.getElementById('drawer-loc').textContent = data.line_count || 0;
    document.getElementById('drawer-churn').textContent = data.churn || 0;
    document.getElementById('drawer-args-count').textContent = data.args ? data.args.length : 0;

    // Docstring
    const docSection = document.getElementById('drawer-docstring-section');
    if (data.docstring) {
      docSection.style.display = 'block';
      document.getElementById('drawer-docstring').textContent = data.docstring;
    } else {
      docSection.style.display = 'none';
    }

    // Code Snippet
    const codeSection = document.getElementById('drawer-code-section');
    if (data.snippet) {
      codeSection.style.display = 'block';
      document.getElementById('drawer-snippet').innerHTML = `<code>${escapeHtml(data.snippet)}</code>`;
    } else {
      codeSection.style.display = 'none';
    }

    // Setup Quick Simulate Button
    document.getElementById('drawer-simulate-impact-btn').onclick = () => {
      document.querySelector('[data-tab="impact-view"]').click();
      document.getElementById('sim-input-name').value = data.name;
      if (data.file) document.getElementById('sim-input-file').value = data.file;
      document.getElementById('run-simulation-btn').click();
    };

    // Callers List
    const callersList = document.getElementById('drawer-callers-list');
    callersList.innerHTML = '';
    if (data.callers && data.callers.length > 0) {
      data.callers.forEach(c => {
        const chip = document.createElement('span');
        chip.className = 'relation-chip';
        chip.textContent = `${c.name} (${c.file})`;
        chip.onclick = () => focusNodeByName(c.name, c.file);
        callersList.appendChild(chip);
      });
      document.getElementById('drawer-callers-section').style.display = 'block';
    } else {
      document.getElementById('drawer-callers-section').style.display = 'none';
    }

    // Callees List
    const calleesList = document.getElementById('drawer-callees-list');
    calleesList.innerHTML = '';
    if (data.callees && data.callees.length > 0) {
      data.callees.forEach(c => {
        const chip = document.createElement('span');
        chip.className = 'relation-chip';
        chip.textContent = `${c.name} (${c.file})`;
        chip.onclick = () => focusNodeByName(c.name, c.file);
        calleesList.appendChild(chip);
      });
      document.getElementById('drawer-callees-section').style.display = 'block';
    } else {
      document.getElementById('drawer-callees-section').style.display = 'none';
    }

  } catch (err) {
    showToast(`Could not load component details: ${err.message}`, 'error');
  }
}

function focusNodeByName(name, file) {
  const node = allRawNodes.find(n => n.name === name || (file && n.file === file));
  if (node && network) {
    network.focus(node.id, { scale: 1.2, animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
    network.selectNodes([node.id]);
    openNodeInspector(node.id);
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Blast Radius Simulator Tab Controller
async function executeImpactSimulation() {
  const name = document.getElementById('sim-input-name').value.trim();
  const file = document.getElementById('sim-input-file').value.trim();
  const depth = document.getElementById('sim-input-depth').value;
  const summaryBox = document.getElementById('sim-summary-container');
  const resultsBox = document.getElementById('sim-results-list');

  if (!name) {
    showToast('Please enter a target function or file name', 'error');
    return;
  }

  summaryBox.innerHTML = '<p style="color:var(--text-secondary);">Calculating propagation paths...</p>';
  resultsBox.innerHTML = '';

  try {
    const params = new URLSearchParams({ name, depth });
    if (file) params.set('file', file);
    const res = await api(`/api/impact/function?${params}`);

    if (!res.affected || res.affected.length === 0) {
      summaryBox.innerHTML = `
        <div style="background:var(--risk-low-bg);border:1px solid var(--risk-low-border);padding:0.75rem 1rem;border-radius:6px;">
          <strong style="color:var(--risk-low-text);">Low Impact:</strong> No downstream callers identified for <code>${escapeHtml(name)}</code>.
        </div>`;
      resultsBox.innerHTML = '<p style="color:var(--text-muted);font-size:0.82rem;">Zero downstream callers impacted.</p>';
      return;
    }

    const maxHop = Math.max(...res.affected.map(a => a.depth));
    summaryBox.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:0.4rem;">
        <div style="display:flex;justify-content:space-between;">
          <span>Target Component:</span>
          <strong style="font-family:var(--font-mono);">${escapeHtml(name)}</strong>
        </div>
        <div style="display:flex;justify-content:space-between;">
          <span>Affected Callers:</span>
          <strong style="color:#C53026;">${res.affected.length} components</strong>
        </div>
        <div style="display:flex;justify-content:space-between;">
          <span>Max Propagation Depth:</span>
          <strong>${maxHop} hops</strong>
        </div>
      </div>`;

    resultsBox.innerHTML = `
      <table class="apple-table">
        <thead>
          <tr>
            <th>Hop Depth</th>
            <th>Impacted Function</th>
            <th>File Location</th>
            <th style="text-align:right;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${res.affected.map(row => `
            <tr>
              <td><span class="risk-tag ${row.depth === 1 ? 'high' : row.depth === 2 ? 'medium' : 'low'}">Hop ${row.depth}</span></td>
              <td style="font-weight:600;font-family:var(--font-mono);">${escapeHtml(row.function)}</td>
              <td style="color:var(--text-secondary);font-family:var(--font-mono);">${escapeHtml(row.file)}</td>
              <td style="text-align:right;">
                <button class="btn btn-secondary btn-sm" onclick="focusNodeByName('${escapeHtml(row.function)}', '${escapeHtml(row.file)}')">Focus</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>`;

    showToast(`Simulation complete: ${res.affected.length} affected components found`, 'success');
  } catch (err) {
    summaryBox.innerHTML = `<p style="color:#C53026;">Error: ${err.message}</p>`;
  }
}

// Risk Tab Controller
async function loadRiskData() {
  const container = document.getElementById('risk-content-container');
  container.innerHTML = '<p style="padding:1.25rem;color:var(--text-muted);">Computing risk matrix...</p>';

  try {
    const endpoint = currentRiskTab === 'files' ? '/api/risk/files?limit=25' : '/api/risk/functions?limit=25';
    const items = await api(endpoint);

    if (!items || items.length === 0) {
      container.innerHTML = '<p style="padding:1.25rem;color:var(--text-muted);">No risk data found.</p>';
      return;
    }

    if (currentRiskTab === 'functions') {
      container.innerHTML = `
        <table class="apple-table">
          <thead>
            <tr>
              <th>Risk Tier</th>
              <th>Function</th>
              <th>File</th>
              <th>Callers</th>
              <th>Blast Radius</th>
              <th>LOC</th>
              <th>Churn</th>
              <th>Score</th>
              <th style="text-align:right;">Inspect</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(fn => `
              <tr>
                <td><span class="risk-tag ${fn.level.toLowerCase()}">${fn.level}</span></td>
                <td style="font-weight:600;font-family:var(--font-mono);">${escapeHtml(fn.name)}</td>
                <td style="color:var(--text-secondary);font-family:var(--font-mono);">${escapeHtml(fn.file)}</td>
                <td style="font-family:var(--font-mono);">${fn.in_degree}</td>
                <td style="font-family:var(--font-mono);">${fn.blast_radius}</td>
                <td style="font-family:var(--font-mono);">${fn.line_count}</td>
                <td style="font-family:var(--font-mono);">${fn.churn}</td>
                <td style="font-weight:600;font-family:var(--font-mono);">${fn.risk_score}</td>
                <td style="text-align:right;">
                  <button class="btn btn-secondary btn-sm" onclick="focusNodeByName('${escapeHtml(fn.name)}', '${escapeHtml(fn.file)}')">View</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>`;
    } else {
      container.innerHTML = `
        <table class="apple-table">
          <thead>
            <tr>
              <th>Risk Tier</th>
              <th>File Path</th>
              <th>Importers</th>
              <th>Functions</th>
              <th>Git Churn</th>
              <th>Score</th>
              <th style="text-align:right;">Inspect</th>
            </tr>
          </thead>
          <tbody>
            ${items.map(f => `
              <tr>
                <td><span class="risk-tag ${f.level.toLowerCase()}">${f.level}</span></td>
                <td style="font-weight:600;font-family:var(--font-mono);">${escapeHtml(f.path)}</td>
                <td style="font-family:var(--font-mono);">${f.importers_count}</td>
                <td style="font-family:var(--font-mono);">${f.function_count}</td>
                <td style="font-family:var(--font-mono);">${f.churn}</td>
                <td style="font-weight:600;font-family:var(--font-mono);">${f.risk_score}</td>
                <td style="text-align:right;">
                  <button class="btn btn-secondary btn-sm" onclick="focusNodeByName(null, '${escapeHtml(f.path)}')">View</button>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>`;
    }
  } catch (err) {
    container.innerHTML = `<p style="padding:1.25rem;color:#C53026;">Error: ${err.message}</p>`;
  }
}

// ML Similarity Controller
async function executeSimilaritySearch() {
  const name = document.getElementById('similarity-input-name').value.trim();
  const topK = document.getElementById('similarity-topk').value;
  const container = document.getElementById('similarity-results-container');

  if (!name) {
    showToast('Enter a function name for similarity comparison', 'error');
    return;
  }

  container.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;">Calculating vector similarity...</p>';

  try {
    const res = await api(`/api/similar?name=${encodeURIComponent(name)}&top_k=${topK}`);
    
    if (!res.similar || res.similar.length === 0) {
      container.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;">No matching functions found for <strong>${escapeHtml(name)}</strong>.</p>`;
      return;
    }

    container.innerHTML = res.similar.map(s => {
      const matchPct = (s.similarity_score * 100).toFixed(1);
      return `
        <div class="match-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <div style="font-weight:600;font-family:var(--font-mono);font-size:0.9rem;">${escapeHtml(s.name)}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);">${escapeHtml(s.file)}</div>
            </div>
            <span class="risk-tag low">${matchPct}% Match</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width: ${matchPct}%;"></div></div>
          ${s.docstring ? `<p style="font-size:0.75rem;color:var(--text-secondary);background:var(--bg-surface-tertiary);padding:0.4rem 0.6rem;border-radius:4px;">${escapeHtml(s.docstring)}</p>` : ''}
          ${s.snippet ? `
            <div class="code-box" style="max-height:110px;">
              <pre class="code-box-pre" style="font-size:0.7rem;max-height:100px;"><code>${escapeHtml(s.snippet)}</code></pre>
            </div>` : ''}
          <div style="display:flex;justify-content:flex-end;">
            <button class="btn btn-secondary btn-sm" onclick="focusNodeByName('${escapeHtml(s.name)}', '${escapeHtml(s.file)}')">View in Graph</button>
          </div>
        </div>`;
    }).join('');

    showToast(`Found ${res.similar.length} similar functions`, 'success');
  } catch (err) {
    container.innerHTML = `<p style="color:#C53026;">Error: ${err.message}</p>`;
  }
}

// AI & MCP Hub
async function loadMcpHub() {
  try {
    const info = await api('/api/mcp/info');
    const list = document.getElementById('mcp-tools-list');
    list.innerHTML = info.tools.map(t => `
      <div style="background:var(--bg-surface-tertiary);padding:0.5rem 0.75rem;border-radius:6px;border:1px solid var(--border-hairline);">
        <code style="color:var(--text-primary);font-size:0.78rem;font-weight:600;">${t.name}</code>
        <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:0.15rem;">${t.description}</div>
      </div>
    `).join('');
  } catch (_) {}
}

function setModalPath(p) {
  document.getElementById('modal-index-path').value = p;
}

// Event Listeners Setup
document.addEventListener('DOMContentLoaded', () => {
  initHealthAndStats();
  loadStudioGraph();

  // Segmented Tabs Switching
  document.querySelectorAll('.segmented-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.segmented-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(v => v.classList.remove('active'));
      
      btn.classList.add('active');
      const targetView = document.getElementById(btn.dataset.tab);
      if (targetView) targetView.classList.add('active');

      if (btn.dataset.tab === 'risk-view') loadRiskData();
      else if (btn.dataset.tab === 'mcp-view') loadMcpHub();
      else if (btn.dataset.tab === 'graph-view' && network) {
        setTimeout(() => network.fit(), 100);
      }
    });
  });

  // Graph Search Input
  document.getElementById('graph-search').addEventListener('input', (e) => {
    const term = e.target.value.trim().toLowerCase();
    if (!term) return;
    const match = allRawNodes.find(n => (n.name && n.name.toLowerCase().includes(term)) || (n.file && n.file.toLowerCase().includes(term)));
    if (match && network) {
      network.focus(match.id, { scale: 1.2, animation: { duration: 400 } });
      network.selectNodes([match.id]);
    }
  });

  // Filter Chips (File, Function, Class)
  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const type = chip.dataset.type;
      activeFilters[type] = !activeFilters[type];
      chip.classList.toggle('active');

      const visibleNodeIds = new Set(
        allRawNodes
          .filter(n => activeFilters[n.type])
          .map(n => n.id)
      );

      const filteredNodes = allRawNodes
        .filter(n => visibleNodeIds.has(n.id))
        .map(buildNodeStyle);

      const filteredEdges = allRawEdges
        .filter(e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
        .map(buildEdgeStyle);

      graphNodes.clear();
      graphEdges.clear();
      graphNodes.add(filteredNodes);
      graphEdges.add(filteredEdges);
    });
  });

  // Physics Toggle
  document.getElementById('physics-toggle-btn').addEventListener('click', () => {
    physicsEnabled = !physicsEnabled;
    network.setOptions({ physics: { enabled: physicsEnabled } });
    document.getElementById('physics-toggle-btn').textContent = physicsEnabled ? 'Freeze' : 'Unfreeze';
    showToast(physicsEnabled ? 'Physics enabled' : 'Physics frozen');
  });

  // Refresh Graph Button
  document.getElementById('refresh-graph-btn').addEventListener('click', () => {
    initHealthAndStats();
    loadStudioGraph();
    showToast('Graph reloaded');
  });

  // Close Drawer
  document.getElementById('close-drawer-btn').addEventListener('click', () => {
    document.getElementById('inspector-drawer').classList.add('collapsed');
  });

  // Copy Snippet
  document.getElementById('copy-snippet-btn').addEventListener('click', () => {
    const code = document.getElementById('drawer-snippet').textContent;
    navigator.clipboard.writeText(code);
    showToast('Source code copied', 'success');
  });

  // Copy MCP Config
  document.getElementById('copy-mcp-config-btn').addEventListener('click', () => {
    const config = document.getElementById('mcp-json-config').textContent;
    navigator.clipboard.writeText(config);
    showToast('Configuration copied', 'success');
  });

  // Simulation Slider & Button
  document.getElementById('sim-input-depth').addEventListener('input', (e) => {
    document.getElementById('depth-val').textContent = e.target.value;
  });
  document.getElementById('run-simulation-btn').addEventListener('click', executeImpactSimulation);

  // Risk Tab Switching
  document.getElementById('risk-tab-fn').addEventListener('click', () => {
    currentRiskTab = 'functions';
    document.getElementById('risk-tab-fn').className = 'btn btn-primary btn-sm';
    document.getElementById('risk-tab-file').className = 'btn btn-secondary btn-sm';
    loadRiskData();
  });
  document.getElementById('risk-tab-file').addEventListener('click', () => {
    currentRiskTab = 'files';
    document.getElementById('risk-tab-file').className = 'btn btn-primary btn-sm';
    document.getElementById('risk-tab-fn').className = 'btn btn-secondary btn-sm';
    loadRiskData();
  });

  // Similarity Search
  document.getElementById('run-similarity-btn').addEventListener('click', executeSimilaritySearch);

  // Cypher Run Button inside Studio
  document.getElementById('studio-cypher-btn').addEventListener('click', async () => {
    const q = document.getElementById('studio-cypher-input').value.trim();
    const out = document.getElementById('studio-cypher-output');
    if (!q) return;
    out.style.display = 'block';
    out.textContent = 'Executing query...';
    try {
      const res = await api('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
      });
      out.textContent = JSON.stringify(res, null, 2);
    } catch (err) {
      out.textContent = 'Error: ' + err.message;
    }
  });

  // Modal Handling
  const modal = document.getElementById('index-modal');
  document.getElementById('open-index-modal-btn').addEventListener('click', () => modal.classList.add('active'));
  document.getElementById('close-index-modal-btn').addEventListener('click', () => modal.classList.remove('active'));
  document.getElementById('cancel-index-btn').addEventListener('click', () => modal.classList.remove('active'));

  document.getElementById('submit-index-btn').addEventListener('click', async () => {
    const path = document.getElementById('modal-index-path').value.trim();
    const reset = document.getElementById('modal-index-reset').checked;
    if (!path) {
      showToast('Please specify a directory path', 'error');
      return;
    }

    modal.classList.remove('active');
    showToast(`Indexing ${path}...`);

    try {
      const res = await api('/api/index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, reset })
      });

      showToast(`Indexed ${res.indexed_files} files from ${res.path}`, 'success');
      await initHealthAndStats();
      await loadStudioGraph();
    } catch (err) {
      showToast(`Indexing failed: ${err.message}`, 'error');
    }
  });
});
