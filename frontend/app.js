/**
 * NEXUSOPS - MISSION CONTROL APPLICATION LOGIC
 * Graph Hacks 2026 Powered by FalkorDB
 */

let cy = null;
let currentScenario = {
  service: "payment-service",
  title: "P0 Payment Gateway Cascade: HTTP 504 Timeouts",
  metric: "18.4% error rate, redis pool saturated"
};

const PRESET_QUERIES = {
  q1: "MATCH path = (s:Service {name: 'payment-service'})<-[:DEPENDS_ON*1..3]-(impacted:Service)\nRETURN impacted.name AS service, impacted.tier AS tier, length(path) AS hops\nORDER BY hops ASC",
  q2: "MATCH (s:Service {name: 'payment-service'})<-[r:OWNS|ON_CALL_FOR]-(p:Person)\nRETURN p.name AS engineer, p.role AS role, p.slack AS slack, p.pagerduty AS pagerduty, type(r) AS relation",
  q3: "MATCH (src {name: 'payment-service'}), (dst {name: 'commit-c891a'})\nMATCH p = shortestPath((src)-[*..6]-(dst))\nRETURN [n in nodes(p) | n.name] AS causality_chain, length(p) AS hops",
  q4: "CALL algo.pageRank('Service', 'DEPENDS_ON') YIELD node, score\nRETURN node.name AS service, score\nORDER BY score DESC",
  q5: "MATCH (inc:Incident)-[:RESOLVED_BY]->(act:RemediationAction)\nRETURN inc.id AS incident, inc.title AS title, act.action_type AS action, act.description AS playbook"
};

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  initCytoscape();
  fetchSystemStatus();
  loadPresetQuery();
  loadEpisodicMemory();
});

// -------------------------------------------------------------
// 1. CYTOSCAPE GRAPH INITIALIZATION
// -------------------------------------------------------------
async function initCytoscape() {
  try {
    const res = await fetch("/api/graph/canvas");
    const data = await res.json();

    const elements = data.elements || [];

    cy = cytoscape({
      container: document.getElementById("cy"),
      elements: elements,
      style: [
        // Core Node Styling
        {
          selector: "node",
          style: {
            "label": "data(label)",
            "font-family": "Inter, sans-serif",
            "font-size": "11px",
            "font-weight": 600,
            "color": "#f1f5f9",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "background-color": "#334155",
            "border-width": 2,
            "border-color": "#64748b",
            "width": 38,
            "height": 38,
            "transition-property": "background-color, border-color, width, height, box-shadow",
            "transition-duration": "0.3s"
          }
        },
        // Type: Service
        {
          selector: "node[type = 'Service']",
          style: {
            "background-color": "#0d2b45",
            "border-color": "#00f0ff",
            "border-width": 2.5,
            "color": "#00f0ff"
          }
        },
        // Type: Infrastructure / DB
        {
          selector: "node[type = 'Infrastructure']",
          style: {
            "background-color": "#2c1a4d",
            "border-color": "#a855f7",
            "border-width": 2.5,
            "color": "#d8b4fe",
            "shape": "round-rectangle"
          }
        },
        // Type: Person / On-Call
        {
          selector: "node[type = 'Person']",
          style: {
            "background-color": "#064e3b",
            "border-color": "#10b981",
            "border-width": 2.5,
            "color": "#6ee7b7"
          }
        },
        // Type: Commit
        {
          selector: "node[type = 'Commit']",
          style: {
            "background-color": "#451a03",
            "border-color": "#f59e0b",
            "border-width": 2,
            "color": "#fcd34d",
            "shape": "diamond"
          }
        },
        // Type: Document / ADR
        {
          selector: "node[type = 'Document']",
          style: {
            "background-color": "#0c4a6e",
            "border-color": "#38bdf8",
            "border-width": 2,
            "color": "#7dd3fc",
            "shape": "tag"
          }
        },
        // Edge Styling
        {
          selector: "edge",
          style: {
            "width": 1.8,
            "line-color": "rgba(255, 255, 255, 0.12)",
            "target-arrow-color": "rgba(255, 255, 255, 0.25)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "label": "data(label)",
            "font-size": "9px",
            "font-family": "JetBrains Mono, monospace",
            "color": "#64748b",
            "text-background-color": "#0d121f",
            "text-background-opacity": 0.85,
            "text-background-padding": 2
          }
        },
        // Highlight states
        {
          selector: ".highlighted-incident",
          style: {
            "background-color": "#7f1d1d",
            "border-color": "#ef4444",
            "border-width": 4,
            "width": 48,
            "height": 48
          }
        },
        {
          selector: ".highlighted-impacted",
          style: {
            "border-color": "#f59e0b",
            "border-width": 3,
            "background-color": "#451a03"
          }
        },
        {
          selector: ".highlighted-edge",
          style: {
            "line-color": "#ef4444",
            "target-arrow-color": "#ef4444",
            "width": 3.5
          }
        },
        {
          selector: ".causality-edge",
          style: {
            "line-color": "#00f0ff",
            "target-arrow-color": "#00f0ff",
            "width": 3.5
          }
        }
      ],
      layout: {
        name: "concentric",
        concentric: function(node) {
          const type = node.data("type");
          if (type === "Service") return 3;
          if (type === "Infrastructure") return 2;
          return 1;
        },
        levelWidth: () => 1,
        padding: 50,
        animate: true,
        animationDuration: 800
      }
    });

    // Node click inspector listener
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      openNodeDrawer(node.data());
    });

    // Background click closes drawer
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        closeDrawer();
      }
    });

  } catch (err) {
    console.error("Failed to initialize Cytoscape canvas:", err);
  }
}

function cyFit() {
  if (cy) cy.fit(undefined, 40);
}

function cyReset() {
  if (cy) {
    cy.elements().removeClass("highlighted-incident highlighted-impacted highlighted-edge causality-edge");
    cy.layout({
      name: "concentric",
      padding: 50,
      animate: true,
      animationDuration: 600
    }).run();
  }
}

async function reloadGraph() {
  if (cy) {
    const res = await fetch("/api/graph/canvas");
    const data = await res.json();
    cy.elements().remove();
    cy.add(data.elements || []);
    cyReset();
    fetchSystemStatus();
  }
}

// -------------------------------------------------------------
// 2. SYSTEM STATUS & METRICS
// -------------------------------------------------------------
async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    const badge = document.getElementById("dbStatusBadge");
    const text = document.getElementById("dbStatusText");

    if (data.is_connected) {
      badge.className = "status-badge status-live";
      text.innerText = data.mode;
    } else {
      badge.className = "status-badge status-embedded";
      text.innerText = data.mode;
    }

    document.getElementById("metricNodes").innerText = data.total_nodes || "--";
    document.getElementById("metricEdges").innerText = data.total_edges || "--";
    document.getElementById("metricLatency").innerText = "2.1 ms";

    if (data.host) document.getElementById("cfgHost").value = data.host;
    if (data.port) document.getElementById("cfgPort").value = data.port;
  } catch (e) {
    console.warn("Status fetch failed:", e);
  }
}

// -------------------------------------------------------------
// 3. MULTI-AGENT INCIDENT SIMULATION
// -------------------------------------------------------------
function triggerScenario(service, title, metric) {
  currentScenario = { service, title, metric };
  document.querySelectorAll(".btn-scenario").forEach(btn => btn.classList.remove("active"));
  event.currentTarget.classList.add("active");

  if (cy) {
    cy.elements().removeClass("highlighted-incident highlighted-impacted highlighted-edge causality-edge");
    const targetNode = cy.getElementById(service);
    if (targetNode.length) {
      targetNode.addClass("highlighted-incident");
      cy.animate({
        center: { eles: targetNode },
        zoom: 1.4,
        duration: 500
      });
    }
  }
}

async function runSimulateIncident() {
  const btn = document.getElementById("runIncidentBtn");
  const feed = document.getElementById("agentFeed");
  const timing = document.getElementById("deliberationTiming");

  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i> Swarm Deliberating...`;
  if (window.lucide) lucide.createIcons();

  switchTab("deliberation");
  feed.innerHTML = `
    <div class="feed-placeholder">
      <div class="status-dot spin" style="width:18px;height:18px;background:var(--cyan-primary);"></div>
      <p>Multi-Agent Swarm connecting to FalkorDB multigraph...</p>
    </div>
  `;

  try {
    const res = await fetch("/api/incident/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service: currentScenario.service,
        alert_title: currentScenario.title,
        metric_value: currentScenario.metric
      })
    });
    const incident = await res.json();

    // Render chronology
    timing.innerText = `Resolved in ${incident.total_deliberation_ms} ms (${incident.severity})`;
    feed.innerHTML = "";

    incident.timeline.forEach((step, idx) => {
      const card = document.createElement("div");
      card.className = "agent-step-card";
      card.style.animationDelay = `${idx * 150}ms`;

      card.innerHTML = `
        <div class="step-meta">
          <span class="step-agent-name"><i data-lucide="bot"></i> ${step.agent}</span>
          <span class="step-latency">${step.duration_ms} ms</span>
        </div>
        <div class="step-findings">${step.findings}</div>
        <div class="step-cypher-block">${step.cypher_query}</div>
      `;
      feed.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();

    // Visual Graph Highlights
    if (cy) {
      cy.elements().removeClass("highlighted-incident highlighted-impacted highlighted-edge causality-edge");
      const target = cy.getElementById(incident.service);
      if (target.length) target.addClass("highlighted-incident");

      // Highlight impacted services in amber
      incident.summary.blast_radius_services.forEach(svc => {
        const n = cy.getElementById(svc);
        if (n.length) n.addClass("highlighted-impacted");
      });

      // Highlight causality shortest path in cyan
      const commitNode = cy.getElementById("commit-c891a");
      if (commitNode.length) commitNode.addClass("highlighted-impacted");

      cy.fit(undefined, 40);
    }

    // Refresh memory list since new memory node was committed
    loadEpisodicMemory();
    fetchSystemStatus();

  } catch (err) {
    feed.innerHTML = `<div class="modal-alert error">Error simulating incident: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="zap"></i> Launch Multi-Agent Triage`;
    if (window.lucide) lucide.createIcons();
  }
}

// -------------------------------------------------------------
// 4. QUICK GRAPH TOOLS ACTIONS
// -------------------------------------------------------------
async function runToolBlastRadius() {
  switchTab("cypher");
  document.getElementById("querySelect").value = "q1";
  loadPresetQuery();
  runCustomCypher();
}

async function runToolPageRank() {
  switchTab("cypher");
  document.getElementById("querySelect").value = "q4";
  loadPresetQuery();
  runCustomCypher();
}

async function runToolShortestPath() {
  switchTab("cypher");
  document.getElementById("querySelect").value = "q3";
  loadPresetQuery();
  runCustomCypher();
}

async function runToolOwnership() {
  switchTab("cypher");
  document.getElementById("querySelect").value = "q2";
  loadPresetQuery();
  runCustomCypher();
}

// -------------------------------------------------------------
// 5. EPISODIC MEMORY (Track 2)
// -------------------------------------------------------------
async function loadEpisodicMemory(kw = "") {
  const container = document.getElementById("memoryList");
  try {
    const res = await fetch("/api/tools/recall_memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: kw })
    });
    const data = await res.json();
    const list = data.past_resolutions || [];

    if (list.length === 0) {
      container.innerHTML = `<div class="table-empty">No memory nodes matching keyword "${kw}".</div>`;
      return;
    }

    container.innerHTML = "";
    list.forEach(item => {
      const card = document.createElement("div");
      card.className = "memory-card";
      card.innerHTML = `
        <div class="memory-card-header">
          <span class="memory-id">${item.incident_id}</span>
          <span class="pill pill-${item.severity === 'P0' ? 'p0' : 'p1'}">${item.severity}</span>
        </div>
        <div class="memory-title">${item.title}</div>
        <div class="memory-action">
          <strong>Playbook:</strong> ${item.action_description}
        </div>
        <div style="font-size:0.68rem;color:var(--text-dim);font-family:var(--font-mono)">
          Ref: ${item.playbook_ref || 'Autonomously Committed'}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = `<div class="table-empty">Failed to load memory: ${err.message}</div>`;
  }
}

function searchMemory() {
  const val = document.getElementById("memorySearchInput").value.trim();
  loadEpisodicMemory(val);
}

// -------------------------------------------------------------
// 6. CYPHER SANDBOX
// -------------------------------------------------------------
function loadPresetQuery() {
  const sel = document.getElementById("querySelect").value;
  document.getElementById("cypherInput").value = PRESET_QUERIES[sel] || "";
}

async function runCustomCypher() {
  const query = document.getElementById("cypherInput").value.trim();
  const timeBadge = document.getElementById("cypherExecTime");
  const tableWrap = document.getElementById("cypherResultsTable");

  if (!query) return;

  timeBadge.innerText = "Executing...";
  tableWrap.innerHTML = `<div class="table-empty">Running Cypher traversal against FalkorDB...</div>`;

  try {
    const res = await fetch("/api/cypher/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query })
    });
    const data = await res.json();

    timeBadge.innerText = `${data.execution_time_ms} ms (${data.mode})`;

    if (!data.success) {
      tableWrap.innerHTML = `<div class="modal-alert error">Error: ${data.error}</div>`;
      return;
    }

    const headers = data.header || [];
    const rows = data.result_set || [];

    if (rows.length === 0) {
      tableWrap.innerHTML = `<div class="table-empty">Query executed successfully (0 rows returned).</div>`;
      return;
    }

    let html = `<table class="results-table"><thead><tr>`;
    headers.forEach(h => html += `<th>${h}</th>`);
    html += `</tr></thead><tbody>`;

    rows.forEach(r => {
      html += `<tr>`;
      r.forEach(cell => {
        const val = typeof cell === 'object' ? JSON.stringify(cell) : cell;
        html += `<td>${val}</td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table>`;

    tableWrap.innerHTML = html;
  } catch (err) {
    tableWrap.innerHTML = `<div class="modal-alert error">Cypher execution failed: ${err.message}</div>`;
  }
}

// -------------------------------------------------------------
// 7. UI TABS & DRAWERS
// -------------------------------------------------------------
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

  if (tabId === "deliberation") {
    document.getElementById("tabDeliberation").classList.add("active");
    document.getElementById("viewDeliberation").classList.add("active");
  } else if (tabId === "memory") {
    document.getElementById("tabMemory").classList.add("active");
    document.getElementById("viewMemory").classList.add("active");
  } else if (tabId === "cypher") {
    document.getElementById("tabCypher").classList.add("active");
    document.getElementById("viewCypher").classList.add("active");
  }
}

function openNodeDrawer(data) {
  const drawer = document.getElementById("nodeDrawer");
  const title = document.getElementById("drawerTitle");
  const content = document.getElementById("drawerContent");

  title.innerText = `${data.type}: ${data.label}`;
  content.innerHTML = "";

  const props = data.properties || {};
  Object.keys(props).forEach(k => {
    if (k !== "id" && k !== "label" && props[k]) {
      const row = document.createElement("div");
      row.className = "drawer-prop-row";
      row.innerHTML = `
        <span class="prop-label">${k}</span>
        <span class="prop-val">${props[k]}</span>
      `;
      content.appendChild(row);
    }
  });

  drawer.classList.remove("hidden");
}

function closeDrawer() {
  document.getElementById("nodeDrawer").classList.add("hidden");
}

// -------------------------------------------------------------
// 8. DATABASE MODAL & CONNECTION RE-TRY
// -------------------------------------------------------------
function openDbModal() {
  document.getElementById("dbModal").classList.remove("hidden");
  document.getElementById("dbModalAlert").classList.add("hidden");
}

function closeDbModal() {
  document.getElementById("dbModal").classList.add("hidden");
}

async function saveDbConnection() {
  const host = document.getElementById("cfgHost").value.trim();
  const port = parseInt(document.getElementById("cfgPort").value.trim());
  const username = document.getElementById("cfgUser").value.trim();
  const password = document.getElementById("cfgPassword").value.trim();
  const alertBox = document.getElementById("dbModalAlert");

  alertBox.className = "modal-alert";
  alertBox.innerText = "Connecting & verifying against FalkorDB Cloud...";
  alertBox.classList.remove("hidden");

  try {
    const res = await fetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ host, port, username, password })
    });
    const status = await res.json();

    if (status.is_connected) {
      alertBox.className = "modal-alert success";
      alertBox.innerText = `Connected successfully to ${status.mode}!`;
      setTimeout(() => {
        closeDbModal();
        fetchSystemStatus();
        reloadGraph();
      }, 1000);
    } else {
      alertBox.className = "modal-alert error";
      alertBox.innerText = `FalkorDB Auth: ${status.connection_error || 'Check password'}. Continuing in Embedded Mode.`;
      fetchSystemStatus();
    }
  } catch (err) {
    alertBox.className = "modal-alert error";
    alertBox.innerText = `Network error: ${err.message}`;
  }
}
