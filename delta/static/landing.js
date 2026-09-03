(() => {
  "use strict";
  const scenarios = {
    date: { value: "Sep 10 → Sep 18", field: "launch_date", summary: "1 keep · 1 rerun · 1 wait", states: [["reuse", "KEEP", "Visual inputs are unchanged.", "+$0.00"], ["rerun", "RERUN", "Launch date changed.", "Cost unknown"], ["pending", "WAIT", "Waiting for announcement.", "After step 02"]] },
    visual: { value: "Studio → Field", field: "visual_brief", summary: "2 keep · 1 rerun · 0 wait", states: [["rerun", "RERUN", "Visual brief changed.", "Cost unknown"], ["reuse", "KEEP", "Announcement inputs match.", "+$0.00"], ["reuse", "KEEP", "Source announcement matches.", "+$0.00"]] },
    product: { value: "Charger → Power station", field: "product_description", summary: "0 keep · 2 rerun · 1 wait", states: [["rerun", "RERUN", "Product description changed.", "Cost unknown"], ["rerun", "RERUN", "Product description changed.", "Cost unknown"], ["pending", "WAIT", "Waiting for announcement.", "After step 02"]] }
  };
  const box = document.querySelector("#revision-console");
  const tabs = [...document.querySelectorAll(".scenario")];
  const nodes = [...document.querySelectorAll(".artifact-card")];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  function select(name, replay = true) {
    const data = scenarios[name]; if (!data || !box) return;
    box.dataset.scenario = name;
    if (replay && !reduced.matches) { box.classList.remove("is-running"); void box.offsetWidth; box.classList.add("is-running"); }
    tabs.forEach(tab => { const on = tab.dataset.scenario === name; tab.classList.toggle("active", on); tab.setAttribute("aria-selected", String(on)); tab.tabIndex = on ? 0 : -1; });
    document.querySelector("#change-value").textContent = data.value;
    document.querySelector("#change-field").textContent = data.field;
    document.querySelector("#scenario-summary").textContent = data.summary;
    nodes.forEach((node, index) => { const [state, label, reason, cost] = data.states[index]; node.classList.remove("status-reuse", "status-rerun", "status-pending"); node.classList.add(`status-${state}`); node.querySelector(".state").textContent = label; node.querySelector(".reason").textContent = reason; node.querySelector(".cost").textContent = cost; });
  }
  tabs.forEach((tab, index) => { tab.addEventListener("click", () => select(tab.dataset.scenario)); tab.addEventListener("keydown", event => { if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return; event.preventDefault(); const next = (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length; tabs[next].focus(); select(tabs[next].dataset.scenario); }); });
  document.querySelector("#watch-revision")?.addEventListener("click", () => { box?.scrollIntoView({ behavior: reduced.matches ? "auto" : "smooth", block: "center" }); select("date"); });
  const menu = document.querySelector("#marketing-menu"); const nav = document.querySelector("#site-nav");
  function close() { nav?.classList.remove("open"); menu?.setAttribute("aria-expanded", "false"); menu?.setAttribute("aria-label", "Open navigation"); }
  menu?.addEventListener("click", () => { const open = !nav.classList.contains("open"); nav.classList.toggle("open", open); menu.setAttribute("aria-expanded", String(open)); menu.setAttribute("aria-label", open ? "Close navigation" : "Open navigation"); });
  nav?.querySelectorAll("a").forEach(link => link.addEventListener("click", close));
  document.addEventListener("keydown", event => { if (event.key === "Escape") { close(); menu?.focus(); } });
  select("date", false);
})();
