/** Keep the initialized viewer mounted while switching top-level views. */
export function setupNavigation(document, { leaveTracking, openExperiments }) {
  const tracking = document.querySelector("#tracking-panel");
  const experiments = document.querySelector("#experiments-panel");
  const trackingTab = document.querySelector("#tracking-tab");
  const experimentsTab = document.querySelector("#experiments-tab");
  function show(name) {
    const active = name === "experiments";
    if (active && !tracking.hidden) leaveTracking();
    tracking.hidden = active;
    experiments.hidden = !active;
    trackingTab.setAttribute("aria-current", active ? "false" : "page");
    experimentsTab.setAttribute("aria-current", active ? "page" : "false");
    if (active) openExperiments();
  }
  trackingTab.addEventListener("click", () => show("tracking"));
  experimentsTab.addEventListener("click", () => show("experiments"));
  show("tracking");
  return { show };
}
