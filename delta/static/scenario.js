(() => {
  "use strict";
  const body = document.body;
  const csrf = document.querySelector('meta[name="delta-csrf-token"]')?.content || "";
  const scenarioId = body.dataset.scenarioId;
  const status = document.querySelector("#page-status");
  const setStatus = (message, state = "") => { if (!status) return; status.textContent = message; status.dataset.state = state; };
  const request = async (url, options = {}) => {
    const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, ...(options.headers || {}) } });
    let payload = {};
    try { payload = await response.json(); } catch { payload = { message: "Delta returned an unreadable response." }; }
    if (!response.ok) { const error = new Error(payload.message || "Delta could not complete this request."); error.payload = payload; error.status = response.status; throw error; }
    return payload;
  };
  document.querySelector("#sign-out")?.addEventListener("click", async () => {
    try { await request("/api/logout", { method: "POST", body: JSON.stringify({}) }); window.location.assign("/login"); }
    catch (error) { setStatus(error.message, "error"); }
  });
  if (!scenarioId) return;
  const form = document.querySelector("#handoff-form");
  const previewButton = document.querySelector("#preview-button");
  const runButton = document.querySelector("#run-button");
  const resetButton = document.querySelector("#reset-button");
  const decisionList = document.querySelector("#decision-list");
  const outputList = document.querySelector("#output-list");
  const receiptEntries = document.querySelector("#receipt-entries");
  let generation = "";
  let previewed = false;
  const value = id => document.querySelector(`#${id}`)?.value.trim() || "";
  const label = decision => decision.label || decision.step_id || decision.id || "Work item";
  const stateText = decision => ({ reuse: "REUSE", rerun: "RERUN", pending_dependency: "WAIT", blocked: "BLOCKED", failed: "FAILED" }[decision.decision] || String(decision.decision || "UNKNOWN").toUpperCase());
  const renderDecisions = (decisions = []) => {
    decisionList.replaceChildren();
    if (!decisions.length) { const p = document.createElement("p"); p.className = "empty-state"; p.textContent = "No decision is available for this request."; decisionList.append(p); return; }
    decisions.forEach((decision, index) => {
      const row = document.createElement("article"); row.className = "decision-row";
      const number = document.createElement("span"); number.className = "decision-index"; number.textContent = String(index + 1).padStart(2, "0");
      const copy = document.createElement("div"); const heading = document.createElement("h3"); heading.textContent = label(decision); const reason = document.createElement("p"); reason.textContent = decision.reason || "Delta did not provide a reason."; copy.append(heading, reason);
      const pill = document.createElement("span"); pill.className = `state-pill state-${decision.decision || "unknown"}`; pill.textContent = stateText(decision); row.append(number, copy, pill); decisionList.append(row);
    });
  };
  const renderOutputs = (steps = []) => {
    outputList.replaceChildren();
    const safe = steps.filter(step => step.visibility === "browser_safe" && step.current_output !== null);
    if (!safe.length) { const p = document.createElement("p"); p.className = "empty-state"; p.textContent = "No browser-safe output is available yet."; outputList.append(p); return; }
    safe.forEach(step => { const item = document.createElement("article"); item.className = "safe-output"; const heading = document.createElement("h3"); heading.textContent = step.label; const content = document.createElement("p"); content.textContent = JSON.stringify(step.current_output, null, 2); const source = document.createElement("small"); source.textContent = `Source: ${step.source || "Sibyl"}`; item.append(heading, content, source); outputList.append(item); });
  };
  const renderReceipt = (receipt, preview = false) => {
    if (!receipt) return;
    const summary = document.querySelector("#receipt-summary"); summary.replaceChildren(); summary.dataset.state = "success";
    const strong = document.createElement("strong"); strong.textContent = receipt.summary || "Receipt recorded."; const span = document.createElement("span"); const counts = receipt.counts || {}; span.textContent = `Reused ${counts.reused || 0} · blocked ${counts.blocked || 0} · executed ${counts.executed || 0} · waiting ${counts.pending_dependency || 0}`; summary.append(strong, span);
    document.querySelector("#receipt-status").textContent = preview ? "Preview only" : "Recorded";
    receiptEntries.replaceChildren();
    (receipt.entries || []).forEach(entry => { const row = document.createElement("article"); row.className = "receipt-entry"; const heading = document.createElement("strong"); heading.textContent = entry.step_id; const outcome = document.createElement("span"); outcome.className = `state-pill state-${entry.outcome || "unknown"}`; outcome.textContent = String(entry.outcome || "not recorded").replaceAll("_", " ").toUpperCase(); const reason = document.createElement("p"); reason.textContent = entry.reason || "No reason recorded."; row.append(heading, outcome, reason); receiptEntries.append(row); });
  };
  const applyState = payload => { generation = payload.generation || generation; document.querySelector("#generation-label").textContent = generation.slice(0, 12); document.querySelector("#generation-evidence").textContent = generation; renderDecisions(payload.handoff?.decisions || payload.steps || []); renderOutputs(payload.steps || []); };
  const load = async () => { setStatus("Recalling Agent A's saved work…", "busy"); try { const payload = await request(`/api/scenarios/${encodeURIComponent(scenarioId)}`); applyState(payload); setStatus("Saved work loaded. Edit the request, then preview the handoff."); } catch (error) { setStatus(error.message, error.status === 409 ? "stale" : "error"); } };
  form?.addEventListener("submit", async event => { event.preventDefault(); previewButton.disabled = true; runButton.disabled = true; previewed = false; setStatus("Evaluating the handoff boundary…", "busy"); try { const payload = await request(`/api/scenarios/${encodeURIComponent(scenarioId)}/handoff`, { method: "POST", body: JSON.stringify({ brief: value("brief"), revision: value("revision"), generation }) }); applyState(payload); renderDecisions(payload.handoff?.decisions || []); renderReceipt({ summary: payload.handoff?.receipt, counts: {}, entries: [] }, true); previewed = true; runButton.disabled = false; document.querySelector("#decision-stamp").textContent = "PREVIEWED"; document.querySelector("#run-note").textContent = "The preview is current. Running Agent B executes only missing work."; setStatus("Preview ready. Approved work may cross; blocked work stays behind."); } catch (error) { setStatus(error.message, error.status === 409 ? "stale" : "error"); } finally { previewButton.disabled = false; } });
  runButton?.addEventListener("click", async () => { runButton.disabled = true; setStatus("Running Agent B through the deterministic fixture…", "busy"); try { const payload = await request(`/api/scenarios/${encodeURIComponent(scenarioId)}/agent-run`, { method: "POST", body: JSON.stringify({ task: value("task"), brief: value("brief"), revision: value("revision"), generation, mode: "deterministic_fixture" }) }); applyState(payload); renderDecisions(payload.execution?.decisions || payload.steps || []); renderReceipt(payload.receipt); document.querySelector("#decision-stamp").textContent = payload.agent_run?.status === "succeeded" ? "COMPLETE" : "FAILED"; document.querySelector("#run-note").textContent = payload.agent_run?.status === "succeeded" ? "Agent B received approved context. The receipt records each consequence." : (payload.agent_run?.error_code || "Agent B did not complete."); setStatus(payload.agent_run?.status === "succeeded" ? "Agent B completed on the deterministic fixture path. No live provider or payment was used." : "Agent B failed. Review the error and retry from a current preview.", payload.agent_run?.status === "succeeded" ? "" : "error"); } catch (error) { setStatus(error.message, error.status === 409 ? "stale" : "error"); } finally { runButton.disabled = !previewed; } });
  resetButton?.addEventListener("click", async () => { if (!window.confirm("Reset this scenario and recreate Agent A's fixture work?")) return; resetButton.disabled = true; setStatus("Resetting this scenario…", "busy"); try { const payload = await request(`/api/scenarios/${encodeURIComponent(scenarioId)}/reset`, { method: "POST", body: JSON.stringify({ generation }) }); applyState(payload); previewed = false; runButton.disabled = true; document.querySelector("#decision-stamp").textContent = "RESET"; document.querySelector("#receipt-status").textContent = "Not recorded"; setStatus("Scenario reset. Agent A's new generation is ready."); } catch (error) { setStatus(error.message, error.status === 409 ? "stale" : "error"); } finally { resetButton.disabled = false; } });
  load();
})();
