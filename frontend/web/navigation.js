/** Keep the initialized viewer mounted while switching top-level views. */
export function setupNavigation(document, { leaveTracking, openExperiments, openDiagnostics = () => {} }) {
  const tracking = document.querySelector("#tracking-panel");
  const experiments = document.querySelector("#experiments-panel");
  const trackingTab = document.querySelector("#tracking-tab");
  const experimentsTab = document.querySelector("#experiments-tab");
  function show(name) {
    const diagnostic = name === "diagnostics";
    const panel = document.querySelector("#diagnostics-panel");
    const tab = document.querySelector("#diagnostics-tab");
    if (panel) panel.hidden = !diagnostic;
    if (tab) tab.setAttribute("aria-current", diagnostic ? "page" : "false");
    if (diagnostic) openDiagnostics();
    const active = name === "experiments";
    if ((active || diagnostic) && !tracking.hidden) leaveTracking();
    tracking.hidden = active || diagnostic;
    experiments.hidden = !active;
    trackingTab.setAttribute("aria-current", active || diagnostic ? "false" : "page");
    experimentsTab.setAttribute("aria-current", active ? "page" : "false");
    if (active) openExperiments();
  }
  trackingTab.addEventListener("click", () => show("tracking"));
  experimentsTab.addEventListener("click", () => show("experiments"));
  document.querySelector("#diagnostics-tab")?.addEventListener("click", () => show("diagnostics"));
  show("tracking");
  return { show };
}
