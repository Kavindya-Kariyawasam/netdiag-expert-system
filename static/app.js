// ---- Tab Switching --------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

let factsCache = [];
let presetsCache = [];
let categoriesCache = {};

// ---- FORWARD CHAINING ----------------------------------------------------
async function loadPresets() {
  try {
    const res = await fetch("/api/presets");
    presetsCache = await res.json();
    const container = document.getElementById("preset-chips");
    container.innerHTML = presetsCache.map((p, idx) => `
      <button type="button" class="preset-chip" data-idx="${idx}" title="${p.description || ''}">
        ⚡ ${p.name}
      </button>
    `).join("");

    container.querySelectorAll(".preset-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        container.querySelectorAll(".preset-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");

        const idx = parseInt(chip.dataset.idx, 10);
        const preset = presetsCache[idx];
        if (preset && preset.facts) {
          applyPresetFacts(preset.facts);
          triggerForwardConsultation();
        }
      });
    });
  } catch (err) {
    console.error("Failed to load presets:", err);
  }
}

function applyPresetFacts(presetFacts) {
  document.querySelectorAll("#facts-checklist select").forEach(sel => {
    const factId = sel.dataset.fact;
    if (factId in presetFacts) {
      sel.value = presetFacts[factId] ? "true" : "false";
    } else {
      sel.value = "unknown";
    }
  });
}

async function loadFacts() {
  try {
    const res = await fetch("/api/facts");
    factsCache = await res.json();
    const box = document.getElementById("facts-checklist");
    box.innerHTML = factsCache.map(f => `
      <div class="fact-row">
        <span class="fact-label">${f.question}</span>
        <select id="fact-${f.id}" data-fact="${f.id}">
          <option value="unknown">Unknown (?)</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </div>`).join("");
  } catch (err) {
    console.error("Failed to load facts:", err);
  }
}

document.getElementById("reset-forward").addEventListener("click", () => {
  document.querySelectorAll("#facts-checklist select").forEach(sel => {
    sel.value = "unknown";
  });
  document.querySelectorAll(".preset-chip").forEach(c => c.classList.remove("active"));
  document.getElementById("forward-results").innerHTML = "";
});

document.getElementById("run-forward").addEventListener("click", () => {
  triggerForwardConsultation();
});

async function triggerForwardConsultation() {
  const box = document.getElementById("forward-results");
  box.innerHTML = `<div class="consulting-loader">Analyzing symptoms with inference engine...</div>`;

  try {
    const facts = {};
    document.querySelectorAll("#facts-checklist select").forEach(sel => {
      if (sel.value !== "unknown") {
        facts[sel.dataset.fact] = (sel.value === "true");
      }
    });

    const response = await fetch("/api/forward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ facts })
    });

    if (!response.ok) {
      throw new Error(`Inference engine returned HTTP ${response.status}`);
    }

    const res = await response.json();
    let html = "";

    // 1. Confirmed Final Diagnoses
    if (res.diagnoses && res.diagnoses.length > 0) {
      html += `<h3 class="section-title">Confirmed Diagnoses (${res.diagnoses.length})</h3>`;
      html += res.diagnoses.map(d => `
        <div class="diagnosis-card confirmed">
          <div class="card-status-badge badge-confirmed">Confirmed</div>
          <h3>${d.title}</h3>
          <p class="rec"><strong>Recommended Fix:</strong> ${d.recommendation}</p>
          <details>
            <summary>How was this concluded?</summary>
            <pre>${(d.how && d.how.length ? d.how.join("\n") : "Established directly from supplied facts.")}</pre>
          </details>
        </div>`).join("");
    }

    // 2. Intermediate Hypotheses Derived
    if (res.intermediate && res.intermediate.length > 0) {
      html += `<h3 class="section-title">Derived Intermediate Findings (${res.intermediate.length})</h3>`;
      html += res.intermediate.map(item => `
        <div class="diagnosis-card intermediate">
          <div class="card-status-badge badge-intermediate">Intermediate Hypothesis</div>
          <h4>${item.title}</h4>
          <details>
            <summary>Derivation chain</summary>
            <pre>${(item.how && item.how.length ? item.how.join("\n") : "Derived by inference rules.")}</pre>
          </details>
        </div>`).join("");
    }

    // 3. Potential Causes / What to Check Next (Near Matches)
    if (res.near_matches && res.near_matches.length > 0) {
      html += `<h3 class="section-title">Potential Causes (Near Matches / Next Checks)</h3>`;
      html += `<p class="hint">The following rules partially matched your symptoms. Verifying the missing conditions will determine if these apply:</p>`;
      html += res.near_matches.map(nm => {
        // Safe extraction of missing symptoms
        let missingItems = [];
        if (Array.isArray(nm.missing_facts)) {
          missingItems = nm.missing_facts.map(m => (typeof m === 'object' && m ? (m.question || m.fact || '') : String(m)));
        } else if (Array.isArray(nm.missing)) {
          missingItems = nm.missing.map(m => (typeof m === 'object' && m ? (m.question || m.fact || '') : String(m)));
        }

        const title = nm.target_title || nm.conclusion_title || "Potential Diagnosis";
        const ratio = nm.match_ratio || `${nm.satisfied_count || 1}/${nm.total_count || 2}`;
        const ruleInfo = nm.rule_text ? `Rule ${nm.rule_id}: ${nm.rule_text}` : `Rule ${nm.rule_id}`;
        const recHtml = nm.recommendation ? `<p class="rec-note"><strong>Tentative Guidance:</strong> ${nm.recommendation}</p>` : '';

        return `
        <div class="diagnosis-card near-match">
          <div class="card-status-badge badge-near">${ratio} conditions met</div>
          <h4>${title}</h4>
          <p class="rule-ref"><em>${ruleInfo}</em></p>
          <div class="missing-checks">
            <strong>Symptoms to verify:</strong>
            <ul>
              ${missingItems.map(text => `<li>${text}</li>`).join("") || '<li>Check additional system symptoms.</li>'}
            </ul>
          </div>
          ${recHtml}
        </div>`;
      }).join("");
    }

    // 4. Fallback if no rules matched at all
    if ((!res.diagnoses || res.diagnoses.length === 0) &&
        (!res.intermediate || res.intermediate.length === 0) &&
        (!res.near_matches || res.near_matches.length === 0)) {
      html += `
        <div class="diagnosis-card negative">
          <h3>No Diagnosis or Match Found</h3>
          <p class="rec">
            No rule conditions were satisfied by the facts provided.
            Try ticking more symptoms in the checklist above, or click one of the <strong>Quick Test Presets</strong> to run a known scenario.
          </p>
        </div>`;
    }

    // 5. Rule-firing trace
    if (res.trace && res.trace.length > 0) {
      html += `
        <details class="trace-details">
          <summary>Full Rule-Firing Trace (${res.trace.length} rule(s) fired)</summary>
          <pre>${res.trace.map(t => `${t.rule_id}: ${t.text} -> [${t.conclusion}]`).join("\n")}</pre>
        </details>`;
    }

    box.innerHTML = html;
  } catch (err) {
    console.error("Forward consultation error:", err);
    box.innerHTML = `
      <div class="diagnosis-card negative">
        <h3>Error Running Consultation</h3>
        <p class="rec">An unexpected error occurred: ${err.message}. Please check your connection and try again.</p>
      </div>`;
  }
}

// ---- BACKWARD CHAINING --------------------------------------------------
async function loadCategories() {
  try {
    const res = await fetch("/api/categories");
    categoriesCache = await res.json();
    const sel = document.getElementById("category-select");
    sel.innerHTML = Object.entries(categoriesCache).map(([catKey, cat]) => `
      <option value="${catKey}">${cat.title}</option>
    `).join("");

    const updateDesc = () => {
      const val = sel.value;
      const cat = categoriesCache[val];
      document.getElementById("category-desc").textContent = cat ? cat.description : "";
    };
    sel.addEventListener("change", updateDesc);
    updateDesc();
  } catch (err) {
    console.error("Failed to load categories:", err);
  }
}

async function loadGoals() {
  try {
    const res = await fetch("/api/goals");
    const goals = await res.json();
    const sel = document.getElementById("goal-select");
    sel.innerHTML = goals.map(g => `<option value="${g.id}">${g.title}</option>`).join("");
  } catch (err) {
    console.error("Failed to load goals:", err);
  }
}

// Mode toggle: Guided Triage vs Specific Goal
document.querySelectorAll('input[name="bc-mode"]').forEach(radio => {
  radio.addEventListener("change", (e) => {
    const isCategory = e.target.value === "category";
    document.getElementById("bc-category-container").style.display = isCategory ? "block" : "none";
    document.getElementById("bc-single-container").style.display = isCategory ? "none" : "block";
  });
});

let currentSession = null;

document.getElementById("start-backward").addEventListener("click", async () => {
  const isCategory = document.querySelector('input[name="bc-mode"]:checked').value === "category";
  const resultsBox = document.getElementById("backward-results");
  const qaBox = document.getElementById("backward-qa");
  resultsBox.innerHTML = "";
  qaBox.style.display = "none";

  const payload = { known_facts: {} };
  if (isCategory) {
    payload.category = document.getElementById("category-select").value;
  } else {
    payload.goal = document.getElementById("goal-select").value;
  }

  try {
    const response = await fetch("/api/backward/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Inference engine returned HTTP ${response.status}`);
    }
    const res = await response.json();
    renderBackwardStep(res);
  } catch (err) {
    console.error("Backward start error:", err);
    resultsBox.innerHTML = `
      <div class="diagnosis-card negative">
        <h3>Error Starting Backward Consultation</h3>
        <p class="rec">${err.message}</p>
      </div>`;
  }
});

function renderBackwardStep(res) {
  currentSession = res.session_id;
  const qaBox = document.getElementById("backward-qa");
  const resultsBox = document.getElementById("backward-results");
  document.getElementById("bc-why-box").style.display = "none";

  if (res.status === "question") {
    qaBox.style.display = "block";
    document.getElementById("bc-question").textContent = res.question;
    qaBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
    return;
  }

  qaBox.style.display = "none";
  const isConfirmed = res.result === true;
  const cls = isConfirmed ? "confirmed" : "negative";
  const badgeCls = isConfirmed ? "badge-confirmed" : "badge-negative";
  const badgeText = isConfirmed ? "Confirmed" : "Not Confirmed / Ruled Out";

  let whyNotHtml = "";
  if (!isConfirmed && res.why_not && res.why_not.length > 0) {
    whyNotHtml = `
      <div class="why-not-box">
        <h4>Why this hypothesis was ruled out:</h4>
        <ul>
          ${res.why_not.map(reason => `<li>${reason}</li>`).join("")}
        </ul>
      </div>`;
  }

  resultsBox.innerHTML = `
    <div class="diagnosis-card ${cls}">
      <div class="card-status-badge ${badgeCls}">${badgeText}</div>
      <h3>${res.goal_title || "Hypothesis Evaluation"}</h3>
      ${res.recommendation ? `<p class="rec"><strong>Recommended Action:</strong> ${res.recommendation}</p>` : ''}
      ${whyNotHtml}
      <details>
        <summary>${isConfirmed ? "How was this proven?" : "Inference trace and evaluation details"}</summary>
        <pre>${(res.how && res.how.length ? res.how.join("\n") : (res.trace || "No active rule trace."))}</pre>
      </details>
    </div>`;
  resultsBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

document.querySelectorAll(".qa-buttons button[data-ans]").forEach(btn => {
  btn.addEventListener("click", async () => {
    let answer = btn.dataset.ans;
    answer = answer === "true" ? true : answer === "false" ? false : null;
    try {
      const response = await fetch("/api/backward/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: currentSession, answer })
      });
      if (!response.ok) {
        throw new Error(`Inference engine returned HTTP ${response.status}`);
      }
      const res = await response.json();
      renderBackwardStep(res);
    } catch (err) {
      console.error("Backward answer error:", err);
    }
  });
});

document.getElementById("bc-why").addEventListener("click", async () => {
  try {
    const res = await (await fetch(`/api/backward/why/${currentSession}`)).json();
    const box = document.getElementById("bc-why-box");
    box.textContent = res.why;
    box.style.display = "block";
  } catch (err) {
    console.error("Failed to get why explanation:", err);
  }
});

// ---- KNOWLEDGE BASE INSPECTOR -------------------------------------------
async function loadKB() {
  try {
    const res = await (await fetch("/api/kb")).json();
    document.getElementById("kb-rules").innerHTML = res.map(r => {
      const prov = r.provenance;
      const sourceHtml = prov ? `
        <div class="rule-source">
          <strong>Source:</strong> ${prov.source || prov.title}<br>
          <strong>Official Citation:</strong> <a href="${prov.url}" target="_blank" rel="noopener noreferrer">${prov.url}</a>
        </div>` : '';
      return `
        <div class="rule-card">
          <div class="rule-header"><b>${r.id}:</b> ${r.text}</div>
          <div class="rule-logic"><code>IF ${r.conditions.join(' AND ')} THEN ${r.conclusion}</code></div>
          ${sourceHtml}
        </div>`;
    }).join("");
  } catch (err) {
    console.error("Failed to load KB:", err);
  }
}

// Coordinated initialization
async function init() {
  await loadFacts();
  await loadPresets();
  await loadCategories();
  await loadGoals();
  await loadKB();
}

init();
