(() => {
  "use strict";

  const form = document.querySelector("#workflow-form");
  const previewButton = document.querySelector("#preview-button");
  const restoreButton = document.querySelector("#restore-button");
  const executeButton = document.querySelector("#execute-button");
  const errorSummary = document.querySelector("#error-summary");
  const liveStatus = document.querySelector("#live-status");
  const steps = document.querySelector("#steps");
  const readoutPanel = document.querySelector(".readout-panel");
  const navOpen = document.querySelector("#nav-open");
  const navClose = document.querySelector("#nav-close");
  const navOverlay = document.querySelector("#nav-overlay");
  const continuityRestore = document.querySelector("#continuity-restore");
  const currentView = document.body.dataset.view;
  let latestPlanId = null;
  let lastNavTrigger = null;
  let executeShouldBeDisabled = true;

  const stateLabels = {
    idle: "Idle",
    reuse: "Reuse",
    rerun: "Rerun",
    pending_dependency: "Pending dependency",
    blocked: "Blocked",
    awaiting_quote: "Awaiting quote",
    funded_awaiting_provider: "Funded / awaiting provider",
    deliverable_ready: "Deliverable ready",
    awaiting_settlement: "Awaiting settlement",
    complete: "Complete",
    failed: "Failure",
    expired: "Expired",
    rejected: "Rejected",
    ambiguous: "Ambiguous",
    reconciliation_required: "Reconciliation required",
    artifact_unavailable: "Artifact unavailable"
  };

  function values() {
    return Object.fromEntries(new FormData(form).entries());
  }

  function announce(message) {
    liveStatus.textContent = message;
  }

  function showError(message) {
    errorSummary.textContent = message;
    errorSummary.hidden = false;
    errorSummary.focus();
    announce(`Error: ${message}`);
  }

  function clearError() {
    errorSummary.textContent = "";
    errorSummary.hidden = true;
  }

  function invalidatePreview() {
    if (!latestPlanId) return;
    latestPlanId = null;
    executeShouldBeDisabled = true;
    executeButton.disabled = true;
    document.querySelector("#execution-note").textContent = "Inputs changed. Preview the current inputs again before executing.";
    announce("Inputs changed. The previous preview is no longer current.");
  }

  function setBusy(button, busy, busyLabel) {
    if (!button.dataset.idleMarkup) button.dataset.idleMarkup = button.innerHTML;
    button.disabled = busy || (button === executeButton && executeShouldBeDisabled);
    button.classList.toggle("is-busy", busy);
    button.setAttribute("aria-busy", String(busy));
    if (readoutPanel) readoutPanel.setAttribute("aria-busy", String(busy));
    if (busy) {
      const label = button.querySelector("span");
      if (label) label.textContent = busyLabel;
      else button.textContent = busyLabel;
    } else {
      button.innerHTML = button.dataset.idleMarkup;
    }
  }

  function setNavigation(open) {
    document.body.classList.toggle("nav-visible", open);
    navOpen.setAttribute("aria-expanded", String(open));
    navOverlay.tabIndex = open ? 0 : -1;
    if (open) {
      lastNavTrigger = document.activeElement;
      navClose.focus();
    } else if (lastNavTrigger) {
      lastNavTrigger.focus();
      lastNavTrigger = null;
    }
  }

  async function request(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options
    });
    const payload = await response.json().catch(() => ({ status: "error", message: "Delta returned an unreadable response." }));
    if (!response.ok) {
      if (payload.message && payload.message.toLowerCase().includes("csrf")) {
        throw new Error("This page session expired. Refresh the page, then try the action again.");
      }
      throw new Error(payload.message || "Delta could not complete the request.");
    }
    return payload;
  }

  function statusClass(state) {
    if (["reuse", "complete"].includes(state)) return "status-reuse";
    if (["rerun"].includes(state)) return "status-rerun";
    if (["pending_dependency", "awaiting_quote", "funded_awaiting_provider", "deliverable_ready", "awaiting_settlement"].includes(state)) return "status-awaiting";
    if (["failed", "expired", "rejected", "ambiguous", "reconciliation_required", "blocked"].includes(state)) return "status-failure";
    if (state === "artifact_unavailable") return "status-unavailable";
    return "status-idle";
  }

  function addText(parent, tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text == null ? "Unknown" : String(text);
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  }

  function displayReason(step) {
    const reasons = {
      REUSE_VALID_RESULT: "This output still matches the current request.",
      RERUN_NO_VALID_RESULT: "No saved output matches these inputs.",
      PENDING_DEPENDENCY_OUTPUT: "This step needs a revised upstream output first."
    };
    return reasons[step.reason_code] || step.reason;
  }

  function renderStep(step, index) {
    const card = document.createElement("article");
    card.className = "step-card";
    card.setAttribute("aria-labelledby", `step-title-${step.id}`);

    const top = document.createElement("div");
    top.className = "step-top";
    const titleGroup = document.createElement("div");
    addText(titleGroup, "p", `0${index + 1} / Step`, "step-number");
    addText(titleGroup, "h3", step.label, "").id = `step-title-${step.id}`;
    top.appendChild(titleGroup);
    addText(top, "span", stateLabels[step.state] || step.state, `status-pill ${statusClass(step.state)}`);
    card.appendChild(top);

    addText(card, "p", displayReason(step), "step-reason");
    const meta = document.createElement("div");
    meta.className = "step-meta";
    const estimate = step.estimated_cost ? `${step.estimated_cost.amount ?? "Unknown"} ${step.estimated_cost.currency}` : "Unknown";
    addText(meta, "span", "Estimate: ", "").appendChild(document.createTextNode(estimate));
    addText(meta, "span", "Source: ", "").appendChild(document.createTextNode(step.source || "unknown"));
    if (step.job_id) addText(meta, "span", `Job: ${step.job_id}`);
    if (step.chain_id) addText(meta, "span", `Chain: ${step.chain_id}`);
    if (step.completed_at) addText(meta, "span", `Stored: ${new Date(step.completed_at).toLocaleString()}`);
    card.appendChild(meta);

    if (step.current_output !== null && step.current_output !== undefined) {
      addText(card, "div", JSON.stringify(step.current_output, null, 2), "output-box");
      addText(card, "p", step.source === "deterministic fixture" ? "Current output is labelled deterministic fixture data, not live provider evidence." : "Current output is persisted work.", "action-note");
    } else {
      addText(card, "p", step.state === "pending_dependency" ? "Output will be available after the upstream step runs." : "No reusable output exists for this exact input.", "action-note");
    }
    if (step.artifact && !step.artifact.available) addText(card, "p", "Artifact reference exists, but the artifact is unavailable and cannot be reused.", "action-note");
    return card;
  }

  function renderRunStep(step, index) {
    const row = document.createElement("article");
    row.className = "run-step";
    addText(row, "span", String(index + 1).padStart(2, "0"), "run-step-number");
    addText(row, "strong", step.label);
    addText(row, "p", displayReason(step));
    addText(row, "span", stateLabels[step.state] || step.state, `status-pill ${statusClass(step.state)}`);
    return row;
  }

  function renderContinuityResult(step) {
    const row = document.createElement("article");
    row.className = "continuity-result";
    const identity = document.createElement("div");
    addText(identity, "strong", step.label);
    addText(identity, "small", step.completed_at ? `Saved ${new Date(step.completed_at).toLocaleString()}` : "No saved timestamp");
    row.appendChild(identity);
    if (step.current_output !== null && step.current_output !== undefined) {
      const details = document.createElement("details");
      addText(details, "summary", "View saved output");
      addText(details, "pre", JSON.stringify(step.current_output, null, 2));
      row.appendChild(details);
      const available = !step.artifact || step.artifact.available;
      addText(row, "span", available ? "Available" : "Artifact unavailable", `status-pill ${available ? "status-reuse" : "status-unavailable"}`);
    } else {
      addText(row, "span", "No matching saved output", "compact-empty");
      addText(row, "span", "Not saved", "status-pill status-idle");
    }
    return row;
  }

  function render(payload) {
    latestPlanId = payload.status === "previewed" ? (payload.plan_id || null) : null;
    const state = document.querySelector("#readout-state");
    state.textContent = payload.status === "executed" ? "Executed" : (payload.status === "loaded" ? "Loaded" : "Previewed");
    state.className = `status-pill ${payload.status === "executed" ? "status-reuse" : "status-idle"}`;
    document.querySelector("#estimated-cost").textContent = payload.estimated_additional_service_cost == null ? "Unknown" : `${payload.estimated_additional_service_cost} ${payload.estimated_cost_currency}`;
    document.querySelector("#cost-source").textContent = payload.estimated_cost_source === "deterministic fixture" ? "Demo estimate" : (payload.estimated_cost_source || "Unknown");
    document.querySelector("#plan-id").textContent = payload.plan_id || "Not created";
    const actualCost = payload.execution ? payload.execution.actual_service_cost : payload.actual_service_cost;
    document.querySelector("#actual-cost").textContent = actualCost == null ? (payload.actual_cost_status === "not_applicable_fixture" ? "Not applicable" : "Not recorded") : `${actualCost} USDC`;
    const payloadSteps = payload.steps || [];
    document.querySelector("#reuse-count").textContent = payloadSteps.filter(step => step.decision === "reuse").length;
    document.querySelector("#rerun-count").textContent = payloadSteps.filter(step => step.decision === "rerun").length;
    document.querySelector("#pending-count").textContent = payloadSteps.filter(step => step.decision === "pending_dependency").length;
    document.querySelector("#run-project").textContent = payload.project_id || "Unknown project";
    document.querySelector("#run-state").textContent = payload.status === "executed" ? "Executed" : (payload.status === "loaded" ? "Recovered" : "Preview ready");
    document.querySelector("#run-state").className = `status-pill ${payload.status === "executed" ? "status-reuse" : "status-awaiting"}`;
    document.querySelector("#run-generated").textContent = payload.generated_at ? new Date(payload.generated_at).toLocaleString() : "Unknown";
    steps.replaceChildren();
    if (!payload.steps || payload.steps.length === 0) {
      addText(steps, "div", "No workflow state was returned.", "empty-readout");
    } else {
      payload.steps.forEach((step, index) => steps.appendChild(renderStep(step, index)));
    }
    const runSteps = document.querySelector("#run-steps");
    if (runSteps) {
      runSteps.replaceChildren();
      payloadSteps.forEach((step, index) => runSteps.appendChild(renderRunStep(step, index)));
    }
    const continuityResults = document.querySelector("#continuity-results");
    if (continuityResults && payload.status === "loaded") {
      continuityResults.replaceChildren();
      payloadSteps.forEach(step => continuityResults.appendChild(renderContinuityResult(step)));
    }
    const hasRerun = (payload.steps || []).some(step => step.decision === "rerun");
    executeShouldBeDisabled = !latestPlanId || !hasRerun || payload.status === "executed";
    executeButton.disabled = executeShouldBeDisabled;
    document.querySelector("#execution-note").textContent = payload.status === "executed"
      ? "The fixture outputs were persisted. Preview again after changing an input to see a new rerun decision."
      : hasRerun ? "This action runs only the configured local deterministic fixtures. It does not create ACP jobs or spend funds." : "Nothing new needs to run for these inputs. Change an input, then preview again to create work to execute.";

    const hasSavedOutput = (payload.steps || []).some(step => step.current_output !== null && step.current_output !== undefined);
    const recovery = document.querySelector("#recovery-banner");
    recovery.hidden = payload.status !== "loaded" && !hasSavedOutput;
    if (!recovery.hidden) document.querySelector("#recovery-message").textContent = hasSavedOutput ? "Persisted outputs were read from the project scope." : "Sibyl was checked for this project and no matching output was found.";
    document.querySelector("#memory-state").textContent = hasSavedOutput ? "State loaded" : "Scope checked";
    document.querySelector("#memory-state").className = `status-pill ${hasSavedOutput ? "status-reuse" : "status-awaiting"}`;
    document.querySelector("#memory-copy").textContent = hasSavedOutput
      ? "Saved outputs for this project were recovered and matched to the current request."
      : "The project scope was checked and no matching reusable output was found.";
    const overviewSaved = document.querySelector("#overview-saved");
    if (overviewSaved) overviewSaved.textContent = hasSavedOutput ? `${payloadSteps.filter(step => step.current_output !== null && step.current_output !== undefined).length} outputs` : "No matching work";
    announce(payload.status === "executed" ? "Deterministic fixture workflow executed and persisted." : `Revision ${payload.status}.`);
  }

  function validateClient() {
    clearError();
    const data = values();
    const missing = ["project_id", "description", "brief", "launch_date", "target_language"].filter(key => !String(data[key] || "").trim());
    if (missing.length) {
      showError(`Complete the required fields: ${missing.join(", ")}.`);
      return false;
    }
    return true;
  }

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (!validateClient()) return;
    setBusy(previewButton, true, "Previewing...");
    try {
      render(await request("/api/preview", { method: "POST", body: JSON.stringify(values()), headers: { "X-CSRF-Token": getCsrfToken() } }));
      clearError();
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(previewButton, false);
    }
  });

  async function restoreSavedWork(button) {
    if (!validateClient()) return;
    setBusy(button, true, "Restoring...");
    try {
      const query = new URLSearchParams(values());
      render(await request(`/api/state?${query.toString()}`));
      clearError();
    } catch (error) {
      showError(error.message);
    } finally {
      setBusy(button, false);
    }
  }

  restoreButton.addEventListener("click", () => restoreSavedWork(restoreButton));
  if (continuityRestore) continuityRestore.addEventListener("click", () => restoreSavedWork(continuityRestore));

  executeButton.addEventListener("click", async () => {
    if (!latestPlanId || !validateClient()) return;
    setBusy(executeButton, true, "Executing...");
    try {
      render(await request("/api/execute", { method: "POST", body: JSON.stringify({ ...values(), plan_id: latestPlanId }), headers: { "X-CSRF-Token": getCsrfToken() } }));
      clearError();
    } catch (error) {
      if (error.message.toLowerCase().includes("preview") && error.message.toLowerCase().includes("stale")) invalidatePreview();
      showError(error.message);
    } finally {
      setBusy(executeButton, false);
    }
  });

  form.addEventListener("input", invalidatePreview);
  form.addEventListener("change", invalidatePreview);

  navOpen.addEventListener("click", () => setNavigation(true));
  navClose.addEventListener("click", () => setNavigation(false));
  navOverlay.addEventListener("click", () => setNavigation(false));
  document.querySelectorAll(".nav-item").forEach(link => link.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(item => {
      item.classList.remove("active");
      item.removeAttribute("aria-current");
    });
    link.classList.add("active");
    link.setAttribute("aria-current", "page");
    if (window.matchMedia("(max-width: 900px)").matches) setNavigation(false);
  }));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && document.body.classList.contains("nav-visible")) setNavigation(false);
  });

  if (["overview", "runs"].includes(currentView)) {
    const query = new URLSearchParams(values());
    request(`/api/state?${query.toString()}`).then(render).catch(error => showError(error.message));
  }

  function getCsrfToken() {
    const cookie = document.cookie.split(";").map(value => value.trim()).find(value => value.startsWith("delta_csrf="));
    return cookie ? decodeURIComponent(cookie.slice("delta_csrf=".length)) : "";
  }
})();
