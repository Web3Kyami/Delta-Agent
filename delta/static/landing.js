(() => {
  "use strict";

  const scenarios = {
    date: {
      note: "The new date only changes the announcement. Its translation waits for the updated source.",
      change: "1 input changed",
      summary: "1 kept · 1 to rebuild · 1 waiting",
      cards: [
        ["keep", "Keep", "Product visual", "Brief still matches the approved art direction.", "No added cost", "01 / Existing"],
        ["rebuild", "Rebuild", "Launch announcement", "Its launch date has changed.", "Quote before run", "02 / Changed"],
        ["wait", "Wait", "Translation", "It needs the revised announcement first.", "Calculated after 02", "03 / Dependent"]
      ]
    },
    visual: {
      note: "The new direction changes the visual only. The existing announcement and translation still match.",
      change: "1 input changed",
      summary: "2 kept · 1 to rebuild · none waiting",
      cards: [
        ["rebuild", "Rebuild", "Product visual", "Its approved visual direction changed.", "Quote before run", "01 / Changed"],
        ["keep", "Keep", "Launch announcement", "Its inputs still match the saved work.", "No added cost", "02 / Existing"],
        ["keep", "Keep", "Translation", "Its announcement source is unchanged.", "No added cost", "03 / Existing"]
      ]
    },
    product: {
      note: "The product has changed. Delta rebuilds the affected work and waits for the new announcement before translation.",
      change: "1 input changed",
      summary: "none kept · 2 to rebuild · 1 waiting",
      cards: [
        ["rebuild", "Rebuild", "Product visual", "The product description changed.", "Quote before run", "01 / Changed"],
        ["rebuild", "Rebuild", "Launch announcement", "The product description changed.", "Quote before run", "02 / Changed"],
        ["wait", "Wait", "Translation", "It needs the revised announcement first.", "Calculated after 02", "03 / Dependent"]
      ]
    }
  };

  const scenarioButtons = [...document.querySelectorAll(".scenario")];
  const cards = [...document.querySelectorAll(".work-card")];
  const desk = document.querySelector(".desk");
  const menuButton = document.querySelector("#marketing-menu");
  const navigation = document.querySelector("#site-nav");

  function updateCard(card, values) {
    const [state, stateLabel, title, reason, cost, meta] = values;
    card.classList.remove("status-keep", "status-rebuild", "status-wait", "is-updating");
    void card.offsetWidth;
    card.classList.add(`status-${state}`, "is-updating");
    card.querySelector(".work-card-meta > span:first-child").textContent = meta;
    card.querySelector(".state").className = `state state-${state}`;
    card.querySelector(".state").textContent = stateLabel;
    card.querySelector("h3").textContent = title;
    card.querySelector("p").textContent = reason;
    card.querySelector(".work-cost").textContent = cost;
  }

  function selectScenario(name) {
    const data = scenarios[name];
    if (!data || !desk) return;
    desk.dataset.scenario = name;
    scenarioButtons.forEach((button) => {
      const selected = button.dataset.scenario === name;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-selected", String(selected));
    });
    document.querySelector("#change-note").textContent = data.note;
    document.querySelector("#map-change").textContent = data.change;
    document.querySelector("#map-summary").textContent = data.summary;
    cards.forEach((card, index) => updateCard(card, data.cards[index]));
  }

  scenarioButtons.forEach((button) => button.addEventListener("click", () => selectScenario(button.dataset.scenario)));
  menuButton?.addEventListener("click", () => {
    const open = !navigation.classList.contains("open");
    navigation.classList.toggle("open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
  });
  navigation?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
    navigation.classList.remove("open");
    menuButton?.setAttribute("aria-expanded", "false");
    menuButton?.setAttribute("aria-label", "Open navigation");
  }));
})();
