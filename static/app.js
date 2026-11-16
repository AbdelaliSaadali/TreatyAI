const $ = (selector, root) => (root || document).querySelector(selector);
const $$ = (selector, root) => Array.from((root || document).querySelectorAll(selector));

const state = {
  view: "overview",
  overview: null,
  scenarios: [],
  selectedScenario: "customer-journey",
  decision: null,
  decisions: [],
  policies: [],
  benchmark: null,
  race: null,
  busy: false
};

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function number(value) { return new Intl.NumberFormat("en-US", {maximumFractionDigits:0}).format(Number(value || 0)); }
function money(value) { return number(value) + " MAD"; }
function date(value) {
  if (!value) return "—";
  try { return new Date(value).toLocaleString("en-GB", {day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"}); }
  catch (_) { return value; }
}
function badge(status) {
  const s = String(status || "neutral").toLowerCase();
  const label = s.replace(/_/g, " ");
  return '<span class="status-pill ' + esc(s) + '">' + esc(label) + '</span>';
}
function toast(message, error) {
  const node = document.createElement("div");
  node.className = "toast" + (error ? " error" : "");
  node.textContent = message;
  $("#toast-region").appendChild(node);
  setTimeout(function () { node.remove(); }, 3400);
}
async function api(path, options) {
  const response = await fetch(path, Object.assign({headers:{"Content-Type":"application/json"}}, options || {}));
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(data.detail || data.message || ("Request failed: " + response.status));
  return data;
}
function setBusy(value) {
  state.busy = value;
  $$("[data-action]").forEach(function (button) { button.disabled = value; });
}
function pageHeading(eyebrow, title, description, actions) {
  return '<div class="page-heading"><div><div class="eyebrow">' + eyebrow + '</div><h1>' + title + '</h1><p>' + description + '</p></div><div class="heading-actions">' + (actions || "") + '</div></div>';
}
function kpi(label, value, foot, tone, symbol) {
  return '<div class="kpi-card"><div class="kpi-top"><span>' + label + '</span><span class="kpi-icon ' + tone + '">' + symbol + '</span></div><div class="kpi-value">' + value + '</div><div class="kpi-foot">' + foot + '</div></div>';
}
function empty(message) { return '<div class="empty-state">' + message + '</div>'; }

function renderOverview(data) {
  const customers = data.customers || [];
  const primary = customers.find(function (c) { return c.id === "C-1042"; }) || {};
  const audit = data.audit || {};
  const rows = (data.recent_decisions || []).map(function (d) {
    return '<tr><td><span class="table-primary">' + esc(d.id) + '</span><span class="table-secondary">' + esc(d.scenario_id) + '</span></td><td>' + esc(d.customer_id) + '</td><td>' + badge(d.status) + '</td><td><span class="hash-text">' + esc((d.receipt_hash || "").slice(0,14)) + '…</span></td><td>' + date(d.created_at) + '</td><td><button class="link-button" data-open-decision="' + esc(d.id) + '">Inspect ↗</button></td></tr>';
  }).join("");
  const html = pageHeading("CONTROL PLANE / OVERVIEW", "Good decisions, in concert.", "A governance layer for autonomous agents — coordinating intent, enforcing global constraints and verifying outcomes before execution.",
    '<button class="button button-secondary" data-action data-reset>↺ Reset demo</button><button class="button button-primary" data-action data-go-decision>Open decision room <span class="button-icon">↗</span></button>') +
    '<div class="kpi-grid">' +
      kpi("Registered agents", "04", "Scoped identities · least privilege", "mint", "⌘") +
      kpi("Decisions processed", number(data.decision_count), "Persisted decision records", "blue", "◇") +
      kpi("Audit events", number(data.event_count), "Append-only hash-linked trail", "violet", "⌁") +
      kpi("Available compensation", money(primary.remaining_budget_mad), "Nadia · " + esc(primary.segment || "Premium") + " customer", "amber", "◈") +
    '</div>' +
    '<div class="dashboard-grid">' +
      '<section class="panel hero-panel"><div class="panel-header"><div><div class="panel-title">TreatyAI decision engine</div><div class="panel-subtitle">Cross-agent coordination · deterministic demo</div></div><div class="hero-status"><span class="pulse-dot"></span> OPERATIONAL</div></div>' +
      '<div class="hero-content"><div class="hero-copy">Many agents. One <span>governed outcome.</span></div><p class="hero-description">TreatyAI evaluates the combined impact of autonomous actions, resolves conflicts under hard business constraints and verifies the resulting plan before it reaches a business system.</p><div class="agent-strip"><span class="agent-chip"><i class="agent-dot cyan"></i>Service</span><span class="agent-chip"><i class="agent-dot violet"></i>Retention</span><span class="agent-chip"><i class="agent-dot amber"></i>Marketing</span><span class="agent-chip"><i class="agent-dot blue"></i>Billing</span><button class="hero-cta" data-go-decision>Run a scenario ↗</button></div></div></section>' +
      '<section class="panel"><div class="panel-header"><div><div class="panel-title">Governance health</div><div class="panel-subtitle">Runtime control checks</div></div><span class="status-pill verified">healthy</span></div>' +
      '<div class="health-list"><div class="health-row"><div class="health-check">✓</div><div><strong>Policy engine online</strong><span>9 versioned rules · hard constraints enforced</span></div></div><div class="health-row"><div class="health-check">✓</div><div><strong>Independent verifier ready</strong><span>Recomputes authorization and global invariants</span></div></div><div class="health-row"><div class="health-check">✓</div><div><strong>Transactional ledger ready</strong><span>SQLite write lock protects shared resources</span></div></div></div>' +
      '<div class="integrity-card"><div class="integrity-icon">✓</div><div><strong>Audit chain ' + (audit.valid ? "intact" : "requires review") + '</strong><span>' + number(audit.events_verified) + ' events verified · SHA-256 links</span></div><span class="integrity-status">' + (audit.valid ? "VALID" : "CHECK") + '</span></div></section>' +
    '</div>' +
    '<section class="panel table-panel"><div class="panel-header"><div><div class="panel-title">Recent decisions</div><div class="panel-subtitle">A traceable record of coordinated business actions</div></div><button class="panel-action" data-view="receipts">View all receipts →</button></div>' +
    '<div class="table-scroll"><table class="data-table"><thead><tr><th>Decision</th><th>Customer</th><th>Status</th><th>Receipt hash</th><th>Created</th><th></th></tr></thead><tbody>' + (rows || '<tr><td colspan="6">' + empty("No decisions yet. Run the flagship scenario to create the first receipt.") + '</td></tr>') + '</tbody></table></div></section>' +
    '<div class="split-grid"><section class="panel"><div class="panel-header"><div><div class="panel-title">Customer state snapshot</div><div class="panel-subtitle">Synthetic CRM record · C-1042</div></div><span class="status-pill neutral">premium</span></div><div class="panel-body"><div class="customer-line"><div class="customer-avatar">NE</div><div><strong>Nadia El Amrani</strong><span>Premium customer · Casablanca</span></div><div class="customer-budget">' + money(primary.remaining_budget_mad) + '<small>Remaining allowance</small></div></div><div class="customer-flags"><span class="' + (primary.open_critical_case ? "flag-warn" : "flag-ok") + '">' + (primary.open_critical_case ? "● Critical case open" : "● No critical case") + '</span><span class="' + (primary.marketing_consent ? "flag-ok" : "flag-warn") + '">' + (primary.marketing_consent ? "● Marketing consent active" : "● Marketing opted out") + '</span></div></div></section>' +
    '<section class="panel"><div class="panel-header"><div><div class="panel-title">System boundary</div><div class="panel-subtitle">What this prototype actually controls</div></div></div><div class="panel-body boundary-copy"><p><strong>Local simulation.</strong> Agent proposals are synthetic and no external Salesforce action is performed.</p><p>The same API contracts are designed for a future Agentforce adapter. Only actions passing through TreatyAI’s execution gate are governed.</p></div></section></div>';
  $("#app-content").innerHTML = html;
  $("#page-crumb").textContent = "Overview";
}
function renderDecision() {
  const cards = state.scenarios.map(function (s) {
    const selected = state.selectedScenario === s.id;
    return '<button class="scenario-card ' + (selected ? "selected" : "") + '" data-select-scenario="' + esc(s.id) + '"><div class="scenario-icon">' + (s.id === "customer-journey" ? "⌘" : "◈") + '</div><strong>' + esc(s.name) + '</strong><p>' + esc(s.description) + '</p><div class="scenario-meta"><span>' + esc(s.category) + '</span><i class="meta-sep"></i><span>' + s.proposals + ' proposals</span></div></button>';
  }).join("");
  const result = state.decision ? renderDecisionResult(state.decision) : '<div class="panel"><div class="panel-header"><div><div class="panel-title">Decision workspace</div><div class="panel-subtitle">Select a scenario and run the coordinator to inspect a verified plan.</div></div></div><div class="empty-state" style="padding:52px 20px"><div style="font-size:28px;margin-bottom:12px">⌁</div><strong style="display:block;color:#52645b;margin-bottom:7px">No decision loaded</strong>Choose the customer journey scenario to see agents, conflicts, constraints and the final resolution.</div></div>';
  const html = pageHeading("WORKSPACE / DECISION ROOM", "The decision room.", "Watch independent agent intentions become one verified, policy-compliant business outcome.",
    '<button class="button button-secondary" data-action data-reset>↺ Reset data</button><button class="button button-primary" data-action data-run-selected>Run selected scenario <span class="button-icon">→</span></button>') +
    '<div class="scenario-grid">' + cards + '</div>' +
    '<div class="run-bar"><div class="run-bar-copy"><strong>Prepare → Verify → Commit</strong><span>One serialized decision boundary · no model is trusted to authorize itself</span></div><div class="run-bar-actions"><button class="button button-secondary" data-action data-run-race>⚡ Run concurrency test</button><button class="button button-primary" data-action data-run-selected>Run coordination ↗</button></div></div>' +
    result +
    (state.race ? renderRace(state.race) : '') +
    '<div class="note-banner"><strong>DEMO MODE</strong><span>All agents and CRM records are simulated. The engine, policy checks, optimizer, verifier, SQLite transaction and audit receipts execute locally for real.</span></div>';
  $("#app-content").innerHTML = html;
  $("#page-crumb").textContent = "Decision room";
}
function renderDecisionResult(d) {
  const p = d.plan || {};
  const summary = d.summary || {};
  const checks = d.verification && d.verification.checks ? d.verification.checks : [];
  const outcomes = p.outcomes || [];
  const graph = d.conflict_graph || {nodes:[],edges:[]};
  return '<div class="decision-summary">' +
    '<div class="summary-tile"><span>Proposals received</span><strong>' + number(summary.proposals) + '</strong></div>' +
    '<div class="summary-tile"><span>Conflicts detected</span><strong>' + number(summary.conflicts) + '</strong></div>' +
    '<div class="summary-tile"><span>Compensation selected</span><strong>' + money(summary.compensation_mad) + '</strong></div>' +
    '<div class="summary-tile"><span>Verifier</span><strong style="font-size:15px;color:' + (d.verification.passed ? "#4c9c70" : "#c46a65") + '">' + (d.verification.passed ? "PASSED ✓" : "HALTED") + '</strong></div>' +
    '</div>' +
    '<div class="result-layout"><section class="graph-panel"><div class="panel-header"><div><div class="panel-title">Cross-agent conflict graph</div><div class="panel-subtitle">Edges represent shared constraints and action dependencies</div></div><span class="status-pill neutral">' + graph.edges.length + ' edges</span></div>' +
    '<div class="graph-canvas">' + graphSvg(graph) + '</div><div class="graph-legend"><span><i class="legend-dot" style="background:#d36d67"></i>Hard conflict</span><span><i class="legend-dot" style="background:#d6a34f"></i>Temporal dependency</span><span><i class="legend-dot" style="background:#5caa80"></i>Agent proposal</span></div></section>' +
    '<section class="panel"><div class="panel-header"><div><div class="panel-title">Resolution outcomes</div><div class="panel-subtitle">Selected actions and their rationale</div></div></div><div class="panel-body"><div class="outcome-list">' +
    outcomes.map(function (o) {
      const symbol = o.status === "approved" ? "✓" : o.status === "adjusted" ? "↘" : o.status === "deferred" ? "Ⅱ" : "×";
      return '<div class="outcome-row"><div class="outcome-icon">' + symbol + '</div><div class="outcome-copy"><strong>' + esc(o.agent_name) + ' · ' + esc(o.action_type.replace(/_/g," ")) + '</strong><span>' + esc(o.rationale) + '</span></div><div class="outcome-amount">' + (o.action_type === "issue_credit" ? money(o.approved_amount_mad) : badge(o.status)) + '</div></div>';
    }).join("") + '</div></div></section></div>' +
    '<div class="split-grid"><section class="panel"><div class="panel-header"><div><div class="panel-title">Independent verification</div><div class="panel-subtitle">Re-evaluated from the selected plan — not from the optimizer\'s explanation</div></div>' + badge(d.verification.passed ? "verified" : "halted") + '</div><div class="panel-body"><div class="verification-list">' +
    checks.map(function (c) {
      return '<div class="verification-row"><div class="verification-mark ' + (c.passed ? "" : "fail") + '">' + (c.passed ? "✓" : "×") + '</div><div><strong>' + esc(c.label) + '</strong><span>' + esc(c.detail) + '</span></div></div>';
    }).join("") + '</div></div></section>' +
    '<section class="panel"><div class="panel-header"><div><div class="panel-title">Execution receipt</div><div class="panel-subtitle">Decision ' + esc(d.decision_id || "PREVIEW") + '</div></div>' + badge(d.status) + '</div><div class="panel-body"><div class="receipt-hash">' + esc(d.receipt ? d.receipt.receipt_hash : "Receipt generated after verified commit") + '</div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px"><span class="table-secondary">Policy ' + esc(d.policy_version) + '</span><button class="link-button" data-open-receipt="' + esc(d.decision_id || "") + '">Inspect receipt ↗</button></div></div></section></div>';
}
function graphSvg(graph) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const positions = {};
  const width = 720;
  const y = 95;
  const margin = nodes.length > 2 ? 120 : 190;
  nodes.forEach(function (n, i) {
    positions[n.id] = {x: nodes.length === 1 ? 360 : margin + i * ((width - margin * 2) / (nodes.length - 1)), y:y};
  });
  let lines = "";
  edges.forEach(function (e) {
    const a = positions[e.source], b = positions[e.target];
    if (!a || !b) return;
    const color = e.severity === "critical" ? "#d36d67" : "#d7a14b";
    lines += '<path d="M' + a.x + ' ' + (a.y+3) + ' Q' + ((a.x+b.x)/2) + ' 24 ' + b.x + ' ' + (b.y+3) + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-dasharray="5 5" opacity=".85"/>';
    lines += '<text x="' + ((a.x+b.x)/2) + '" y="31" fill="' + color + '" text-anchor="middle" font-size="10" font-family="DM Mono">' + esc(e.type.replace(/_/g," ")) + '</text>';
  });
  let circles = "";
  nodes.forEach(function (n) {
    const p = positions[n.id];
    const agent = n.agent.toLowerCase();
    const color = agent.indexOf("marketing") >= 0 ? "#d7a34d" : agent.indexOf("retention") >= 0 ? "#9a8bd4" : "#5caeb5";
    circles += '<g><circle cx="' + p.x + '" cy="' + p.y + '" r="31" fill="' + color + '" fill-opacity=".12" stroke="' + color + '" stroke-width="1.5"/><circle cx="' + p.x + '" cy="' + p.y + '" r="5" fill="' + color + '"/><text x="' + p.x + '" y="' + (p.y+52) + '" text-anchor="middle" fill="#53655c" font-size="11" font-weight="600">' + esc(n.agent) + '</text><text x="' + p.x + '" y="' + (p.y+68) + '" text-anchor="middle" fill="#9aa59f" font-size="9">' + esc(n.label) + '</text></g>';
  });
  const caption = edges.length ? '<text x="360" y="202" text-anchor="middle" fill="#a0aaa4" font-size="10">Detected dependencies are evaluated against customer-wide state</text>' : '<text x="360" y="202" text-anchor="middle" fill="#a0aaa4" font-size="10">No pairwise conflicts detected</text>';
  return '<svg viewBox="0 0 720 230" role="img" aria-label="Conflict graph">' + lines + circles + caption + '</svg>';
}
function renderRace(result) {
  const results = (result.results || []).map(function (r) {
    const outcome = r.outcomes[0] || {};
    return '<div class="outcome-row"><div class="outcome-icon">⚡</div><div class="outcome-copy"><strong>' + esc(outcome.agent_id) + '</strong><span>' + esc(outcome.rationale) + (r.state_revalidation && r.state_revalidation.revalidated ? " · stale proposal revalidated" : "") + '</span></div><div class="outcome-amount">' + money(r.committed_mad) + '</div></div>';
  }).join("");
  return '<section class="panel" style="margin-top:14px"><div class="panel-header"><div><div class="panel-title">Concurrency stress test</div><div class="panel-subtitle">Two simultaneous 100 MAD requests · one shared 150 MAD budget</div></div>' + (result.no_overspend ? '<span class="status-pill verified">No overspend</span>' : '<span class="status-pill halted">Invariant failed</span>') + '</div><div class="panel-body"><div class="decision-summary"><div class="summary-tile"><span>Requested</span><strong>' + money(result.requested_total_mad) + '</strong></div><div class="summary-tile"><span>Committed</span><strong>' + money(result.committed_total_mad) + '</strong></div><div class="summary-tile"><span>Remaining</span><strong>' + money(result.remaining_budget_mad) + '</strong></div><div class="summary-tile"><span>Invariant</span><strong style="color:' + (result.no_overspend ? "#4c9c70" : "#c46a65") + '">' + (result.no_overspend ? "HELD ✓" : "FAILED") + '</strong></div></div><div class="outcome-list">' + results + '</div><div class="note-banner"><strong>WHY IT WORKS</strong><span>' + esc(result.explanation) + '</span></div></div></section>';
}
async function loadDecision() {
  if (!state.scenarios.length) {
    const data = await api("/api/scenarios");
    state.scenarios = data.scenarios || [];
  }
  renderDecision();
}
async function runScenario() {
  if (state.busy) return;
  setBusy(true);
  try {
    const result = await api("/api/scenarios/" + state.selectedScenario + "/run", {method:"POST",body:"{}"});
    state.decision = result;
    state.overview = await api("/api/overview");
    toast("Decision " + result.status + " · receipt recorded");
    renderDecision();
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}
async function runRace() {
  if (state.busy) return;
  setBusy(true);
  try {
    state.race = await api("/api/concurrency/run", {method:"POST",body:"{}"});
    state.overview = await api("/api/overview");
    toast(state.race.no_overspend ? "Concurrency invariant held" : "Concurrency invariant failed", !state.race.no_overspend);
    renderDecision();
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}
async function resetDemo() {
  if (state.busy) return;
  setBusy(true);
  try {
    await api("/api/demo/reset", {method:"POST",body:"{}"});
    state.decision = null;
    state.race = null;
    state.overview = await api("/api/overview");
    toast("Synthetic customer state reset");
    renderCurrent();
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}
async function renderReceipts() {
  const data = await api("/api/receipts?limit=50");
  const receipts = data.receipts || [];
  const html = pageHeading("GOVERNANCE / AUDIT", "Decision receipts.", "Every coordinated outcome carries a traceable record of its policy version, verification checks and execution result.",
    '<button class="button button-secondary" data-action data-verify-chain>Verify audit chain ↗</button>') +
    '<div class="kpi-grid">' +
    kpi("Receipts", number(receipts.length), "Decision records available", "mint", "▤") +
    kpi("Hash algorithm", "SHA-256", "Tamper-evident event linkage", "blue", "⌁") +
    kpi("Policy version", "1.0.0", "Versioned rule set", "violet", "◈") +
    kpi("External actions", "0", "Local simulation only", "amber", "⊘") +
    '</div><section class="panel"><div class="panel-header"><div><div class="panel-title">Auditable decision history</div><div class="panel-subtitle">Append-only records with a verifiable hash chain</div></div><span class="status-pill verified">local ledger</span></div><div class="panel-body">' +
    (receipts.length ? receipts.map(function (r) {
      return '<div class="receipt-card"><div class="receipt-top"><div><div class="receipt-id">' + esc(r.decision_id) + ' <span style="color:#a0aaa4">/ ' + esc(r.scenario_id) + '</span></div><div class="receipt-time">' + date(r.created_at) + ' · ' + esc(r.customer_id) + '</div></div>' + badge(r.status) + '</div><div class="receipt-hash">' + esc(r.receipt.receipt_hash) + '</div><div class="receipt-footer"><span class="table-secondary">' + r.summary.proposals + ' proposals · ' + r.summary.conflicts + ' conflicts · ' + money(r.summary.compensation_mad) + '</span><span><button class="link-button" data-verify-receipt="' + esc(r.decision_id) + '">Verify hash</button><button class="link-button" data-open-decision="' + esc(r.decision_id) + '">Open full decision ↗</button></span></div></div>';
    }).join("") : empty("No receipts yet. Run a scenario to create an auditable decision record.")) +
    '</div></section>';
  $("#app-content").innerHTML = html;
  $("#page-crumb").textContent = "Decision receipts";
}
async function renderPolicies() {
  const data = await api("/api/policies");
  state.policies = data.principles;
  const html = pageHeading("GOVERNANCE / POLICY REGISTRY", "Rules that don't negotiate.", "Hard constraints are evaluated by deterministic code. Agent-generated text is evidence, never authority.",
    '<span class="status-pill verified">VERSION ' + esc(data.version) + '</span>') +
    '<div class="policy-grid">' + data.principles.map(function (p) {
      return '<article class="policy-card"><div class="policy-card-top"><span class="policy-id">' + esc(p.id) + '</span><span class="policy-severity ' + (p.severity === "governance" ? "governance" : "") + '">' + esc(p.severity) + '</span></div><h3>' + esc(p.name) + '</h3><p>' + esc(p.description) + '</p></article>';
    }).join("") + '</div>' +
    '<div class="note-banner"><strong>POLICY DESIGN</strong><span>Rules are deliberately small, inspectable and deterministic. A future production deployment should version, review and test policy changes through a controlled release process.</span></div>';
  $("#app-content").innerHTML = html;
  $("#page-crumb").textContent = "Policy registry";
}
async function renderBenchmark() {
  let latest = await api("/api/bench/latest");
  state.benchmark = latest.available === false ? null : latest;
  const b = state.benchmark;
  let results = "";
  if (b) {
    const baseline = b.baseline.violation_rate_pct;
    const treaty = b.treatyai.violation_rate_pct;
    results = '<div class="bench-metrics">' +
      '<div class="bench-metric"><span>Scenarios executed</span><strong>' + number(b.cases) + '</strong><small>Deterministic test cases</small></div>' +
      '<div class="bench-metric"><span>Baseline invariant violations</span><strong style="color:#c77c68">' + number(b.baseline.invariant_violations) + '</strong><small>' + baseline + '% · budget + contact limits</small></div>' +
      '<div class="bench-metric"><span>TreatyAI invariant violations</span><strong style="color:#4b9b70">' + number(b.treatyai.invariant_violations) + '</strong><small>' + treaty + '% · independently verified</small></div>' +
      '<div class="bench-metric"><span>Safe completion</span><strong>' + b.treatyai.safe_completion_rate_pct + '%</strong><small>At least one valid action committed</small></div>' +
      '</div><section class="panel"><div class="panel-header"><div><div class="panel-title">Global invariant violations</div><div class="panel-subtitle">Naive independent approval compared with TreatyAI\'s joint optimizer and verifier · budget and contact limits</div></div></div><div class="comparison-bars"><div class="bar-row"><span class="bar-label">Independent agents</span><div class="bar-track"><div class="bar-fill" style="width:' + baseline + '%"></div></div><span class="bar-value">' + baseline + '%</span></div><div class="bar-row"><span class="bar-label">TreatyAI</span><div class="bar-track"><div class="bar-fill good" style="width:' + Math.max(1,treaty) + '%"></div></div><span class="bar-value">' + treaty + '%</span></div></div></section>' +
      '<div class="note-banner"><strong>INTERPRETATION</strong><span>' + esc(b.scope_note) + ' This is not a production benchmark or a claim about arbitrary agent systems.</span></div>';
  } else {
    results = '<section class="panel"><div class="empty-state" style="padding:50px 20px"><div style="font-size:28px;margin-bottom:12px">▥</div><strong style="display:block;color:#52645b;margin-bottom:7px">No benchmark run yet</strong>Execute TreatyBench to generate 30 reproducible synthetic scenarios and compare independent approvals with coordinated resolution.</div></section>';
  }
  const html = pageHeading("EVALUATION / TREATYBENCH", "Prove the invariant.", "A reproducible benchmark for cross-agent business conflicts — measuring safety without hiding task completion.",
    '<button class="button button-primary" data-action data-bench-run>Run 30 scenarios ↗</button>') +
    '<section class="benchmark-hero"><div><div class="eyebrow" style="color:#9ccab0">TREATYBENCH / VERSION 0.1</div><h2>Measure the outcome, not the conversation.</h2><p>Thirty synthetic enterprise cases test cumulative compensation limits, consent boundaries, critical-case precedence and safe task completion.</p></div><span class="status-pill verified">REPRODUCIBLE</span></section>' + results;
  $("#app-content").innerHTML = html;
  $("#page-crumb").textContent = "TreatyBench";
}
async function runBenchmark() {
  if (state.busy) return;
  setBusy(true);
  try {
    const result = await api("/api/bench/run", {method:"POST",body:"{}"});
    state.benchmark = result;
    toast("TreatyBench completed · " + result.cases + " cases");
    await renderBenchmark();
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); }
}
async function openDecision(id) {
  if (!id) return;
  try {
    const data = await api("/api/decisions/" + encodeURIComponent(id));
    showModal("Decision " + id, data);
  } catch (error) { toast(error.message, true); }
}
function showModal(title, data) {
  $("#modal-root").innerHTML = '<div class="modal-backdrop" data-close-modal><div class="modal" role="dialog" aria-modal="true"><div class="modal-header"><h2>' + esc(title) + '</h2><button class="modal-close" data-close-modal>×</button></div><pre>' + esc(JSON.stringify(data, null, 2)) + '</pre><button class="button button-secondary" data-copy-json>Copy JSON</button></div></div>';
  state.modalData = data;
}
async function verifyReceiptHash(id) {
  try {
    const result = await api("/api/receipts/" + encodeURIComponent(id) + "/verify");
    toast(result.valid ? "Receipt hash and audit anchor verified" : "Receipt verification failed", !result.valid);
  } catch (error) { toast(error.message, true); }
}
async function verifyChain() {
  try {
    const result = await api("/api/audit/verify");
    toast(result.valid ? "Audit chain valid · " + result.events_verified + " events verified" : "Audit chain integrity failure", !result.valid);
  } catch (error) { toast(error.message, true); }
}
async function renderCurrent() {
  if (state.view === "overview") {
    state.overview = await api("/api/overview");
    renderOverview(state.overview);
  } else if (state.view === "decision") {
    await loadDecision();
  } else if (state.view === "receipts") {
    await renderReceipts();
  } else if (state.view === "policies") {
    await renderPolicies();
  } else if (state.view === "benchmark") {
    await renderBenchmark();
  }
}
async function setView(view) {
  state.view = view;
  if (window.location.hash !== "#" + view) window.history.replaceState(null, "", "#" + view);
  $$(".nav-item").forEach(function (item) { item.classList.toggle("active", item.dataset.view === view); });
  $("#app-content").innerHTML = '<div class="loading-state"><div class="loader"></div><span>Loading ' + esc(view) + '…</span></div>';
  try { await renderCurrent(); }
  catch (error) { $("#app-content").innerHTML = '<div class="empty-state">Unable to load this view: ' + esc(error.message) + '</div>'; }
}
document.addEventListener("click", async function (event) {
  const nav = event.target.closest("[data-view]");
  if (nav) { setView(nav.dataset.view); return; }
  if (event.target.closest("[data-go-decision]")) { setView("decision"); return; }
  const select = event.target.closest("[data-select-scenario]");
  if (select) { state.selectedScenario = select.dataset.selectScenario; state.decision = null; renderDecision(); return; }
  if (event.target.closest("[data-run-selected]")) { runScenario(); return; }
  if (event.target.closest("[data-run-race]")) { runRace(); return; }
  if (event.target.closest("[data-reset]")) { resetDemo(); return; }
  if (event.target.closest("[data-bench-run]")) { runBenchmark(); return; }
  if (event.target.closest("[data-verify-chain]")) { verifyChain(); return; }
  const open = event.target.closest("[data-open-decision]");
  if (open) { openDecision(open.dataset.openDecision); return; }
  const verifyReceipt = event.target.closest("[data-verify-receipt]");
  if (verifyReceipt) { verifyReceiptHash(verifyReceipt.dataset.verifyReceipt); return; }
  const receipt = event.target.closest("[data-open-receipt]");
  if (receipt) { openDecision(receipt.dataset.openReceipt); return; }
  if (event.target.matches("[data-close-modal]")) { $("#modal-root").innerHTML = ""; return; }
  if (event.target.closest("[data-copy-json]")) {
    try { await navigator.clipboard.writeText(JSON.stringify(state.modalData, null, 2)); toast("Decision JSON copied"); }
    catch (_) { toast("Clipboard access unavailable", true); }
    return;
  }
});
$("#refresh-button").addEventListener("click", function () { renderCurrent().then(function(){toast("Workspace refreshed");}).catch(function(e){toast(e.message,true);}); });
async function boot() {
  try {
    await api("/api/health");
    state.overview = await api("/api/overview");
    state.scenarios = (await api("/api/scenarios")).scenarios;
    const requestedView = window.location.hash.replace("#", "");
    const validViews = ["overview", "decision", "receipts", "policies", "benchmark"];
    await setView(validViews.includes(requestedView) ? requestedView : "overview");
  } catch (error) {
    $("#app-content").innerHTML = '<div class="empty-state">TreatyAI API is not reachable. Start the local server with <code>./run.sh</code> and refresh this page.<br><br>' + esc(error.message) + '</div>';
  }
}
boot();
