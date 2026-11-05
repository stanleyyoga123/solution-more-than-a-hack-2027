import {
  sortRuns,
  comparisonRuns,
  metricText,
  shortId,
  runLabel,
} from "./model.js";
import { renderScores, renderScatter, renderFragmentation } from "./charts.js";

const columns = [
  ["pipeline", "Pipeline"],
  ["strategy", "Strategy"],
  ["run_id", "Run ID"],
  ["commit", "Git commit"],
  ["spell_f1_mean", "spellF1"],
  ["macro_f1", "macroF1"],
  ["dead_ball_f1", "Dead-ball F1"],
  ["predicted_possession_count", "Predicted possessions"],
  ["fragmentation", "Fragmentation"],
];
function element(document, tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
export function mountExperiments(root) {
  const document = root.ownerDocument;
  // Static template only: manifest values always enter through textContent.
  root.innerHTML = `
    <header class="experiments-header">
      <div><h1 id="experiments-title">Experiment comparison</h1><p class="intro">Possession inference, measured in context.</p></div>
      <button type="button" id="experiments-reload" class="quality-button">Reload registry</button>
    </header>
    <p class="experiment-caveat">Public scores are exploratory: only five minutes and <strong>17 labelled possessions</strong>. They do not establish a winning full-match model.</p>
    <p id="experiments-status" role="status" aria-live="polite"></p>
    <div id="experiments-content" hidden>
      <div class="comparison-selection"><p id="experiment-selection" role="status"></p><button id="experiment-clear" class="quiet-button">Clear selection</button></div>
      <p id="experiment-scope-note" class="experiment-note"></p>
      <div class="experiment-charts">
        <section class="experiment-chart" aria-labelledby="scores-title">
          <h2 id="scores-title">Official evaluation metrics</h2>
          <p class="experiment-note">Recorded scores for each pipeline. Check evaluation provenance before drawing conclusions.</p>
          <div class="chart-legend"><span><i class="legend-primary"></i>spellF1</span><span><i class="legend-secondary"></i>macroF1</span></div>
          <p class="chart-scroll-hint">Scroll chart horizontally for all values.</p><div id="experiment-scores" class="chart-scroll" tabindex="0" role="region" aria-label="Official score chart; scroll horizontally for all values"></div>
        </section>
        <section class="experiment-chart" aria-labelledby="scatter-title">
          <h2 id="scatter-title">Dead ball & possession quality</h2>
          <p class="experiment-note">Zero is a measured result. Runs missing either metric are omitted.</p>
          <p class="chart-scroll-hint">Scroll chart horizontally to see the full axes.</p><div id="experiment-scatter" class="chart-scroll" tabindex="0" role="region" aria-label="Dead-ball and possession chart; scroll horizontally for full axes"></div>
          <p class="experiment-note">The top-right point is not a recommendation for the full match.</p>
        </section>
        <section class="experiment-chart fragmentation-chart" aria-labelledby="fragmentation-title">
          <h2 id="fragmentation-title">Possession fragmentation</h2>
          <p class="experiment-note">Evaluated-window counts only. Fragmentation is the official segment ratio, not predicted ÷ ground-truth possessions. Above 1× indicates more segments; below 1× may indicate over-persistence.</p>
          <div class="chart-legend"><span><i class="legend-primary"></i>Predicted possessions</span><span><i class="legend-secondary"></i>Ground-truth possessions</span></div>
          <p class="chart-scroll-hint">Scroll chart horizontally for counts and fragmentation.</p><div id="experiment-fragmentation" class="chart-scroll" tabindex="0" role="region" aria-label="Fragmentation chart; scroll horizontally for counts and ratio"></div>
          <p id="experiment-full-counts" class="experiment-note"></p>
        </section>
      </div>
      <p class="experiment-note">Hover a mark for values, or focus it and press Enter to open run details. Exact recorded values are available in each row.</p>
      <section class="experiment-registry" aria-labelledby="registry-title">
        <div class="registry-heading"><h2 id="registry-title">Recorded runs</h2><p id="experiment-table-count" class="experiment-note"></p></div>
        <p class="experiment-note">Select pipeline runs to compare them in the charts. Comparisons across pipelines are exploratory; check evaluation provenance in run details for matching conditions. Possession counts and fragmentation below refer to evaluated frames.</p>
        <p class="chart-scroll-hint">Scroll the table horizontally to inspect all metrics.</p>
        <div class="experiment-table-scroll" tabindex="0" role="region" aria-label="Experiment registry table; scroll horizontally for all metrics">
          <table class="experiment-table"><thead><tr id="experiment-head"><th scope="col">Compare</th></tr></thead><tbody id="experiment-rows"></tbody></table>
        </div>
      </section>
    </div>`;
  const $ = (id) => root.querySelector(`#${id}`);
  const content = $("experiments-content"),
    status = $("experiments-status");
  const selected = new Set();
  let runs = [],
    loaded = false,
    loading = false,
    sortKey = "pipeline",
    direction = "asc";
  const headers = new Map();
  for (const [key, label] of columns) {
    const th = element(document, "th");
    th.scope = "col";
    const button = element(document, "button", "table-sort", label);
    button.type = "button";
    button.addEventListener("click", () => {
      direction = sortKey === key && direction === "asc" ? "desc" : "asc";
      sortKey = key;
      render();
    });
    th.append(button);
    $("experiment-head").append(th);
    headers.set(key, th);
  }
  function details(run) {
    const box = element(document, "details", "run-details");
    box.dataset.runId = run.run_id;
    box.append(element(document, "summary", "", `Details · ${shortId(run)}`));
    const body = element(document, "div", "run-details-body");
    body.append(element(document, "h3", "", runLabel(run)));
    const warningList = element(document, "ul", "repro-warnings");
    run.warnings.forEach((warning) =>
      warningList.append(element(document, "li", "", warning)),
    );
    body.append(warningList);
    body.append(element(document, "h4", "", "Configuration parameters"));
    body.append(
      element(
        document,
        "pre",
        "",
        Object.keys(run.configuration).length
          ? JSON.stringify(run.configuration, null, 2)
          : "No reviewed configuration parameters available.",
      ),
    );
    body.append(element(document, "h4", "", "Available provenance"));
    body.append(
      element(
        document,
        "pre",
        "",
        JSON.stringify(
          {
            recording_commit: run.commit,
            ...run.provenance,
            evaluation: run.evaluation,
          },
          null,
          2,
        ),
      ),
    );
    body.append(element(document, "h4", "", "Recorded metric values"));
    body.append(
      element(document, "pre", "", JSON.stringify(run.metrics, null, 2)),
    );
    body.append(
      element(
        document,
        "p",
        "experiment-note",
        `Full-submission predicted possessions: ${metricText(run.full_submission_possession_count, 0)}. This statistic is separate from evaluated-window counts and may include off-play frames.`,
      ),
    );
    box.append(body);
    return box;
  }
  function inspect(run) {
    const boxes = [...root.querySelectorAll(".run-details")];
    const box = boxes.find((node) => node.dataset.runId === run.run_id);
    if (box) {
      box.open = true;
      box.scrollIntoView({ block: "nearest" });
      box.querySelector("summary").focus();
    }
  }
  function render() {
    const compared = comparisonRuns(runs, "", selected);
    $("experiment-selection").textContent =
      `${selected.size} selected · ${compared.length} shown in charts${selected.size ? "" : " · showing all pipeline runs"}`;
    $("experiment-clear").disabled = !selected.size;
    $("experiment-scope-note").classList.add("exploratory-comparison");
    $("experiment-scope-note").textContent =
      "Exploratory cross-pipeline comparison. Runs may have different or unknown datasets, ground truth or scorers; identical evaluation conditions are not confirmed. Counts remain specific to each run’s evaluated window. This is not a full-match ranking.";
    renderScores($("experiment-scores"), compared, inspect);
    renderScatter($("experiment-scatter"), compared, inspect);
    renderFragmentation($("experiment-fragmentation"), compared, inspect);
    const full = compared.filter(
      (run) => run.full_submission_possession_count !== null,
    );
    $("experiment-full-counts").textContent = full.length
      ? `Separate full-submission statistics (not plotted against evaluated ground truth): ${full.map((run) => `${run.pipeline ?? "Unknown pipeline"}: ${metricText(run.full_submission_possession_count, 0)} predicted possessions`).join("; ")}. May include off-play frames.`
      : "Full-submission possession counts are unavailable for these runs. Evaluated-window counts are not full-match statistics.";
    for (const [key, th] of headers)
      th.setAttribute(
        "aria-sort",
        key === sortKey
          ? direction === "asc"
            ? "ascending"
            : "descending"
          : "none",
      );
    const body = $("experiment-rows");
    const opened = new Set(
      [...body.querySelectorAll("details[open]")].map(
        (node) => node.dataset.runId,
      ),
    );
    body.replaceChildren();
    for (const run of sortRuns(runs, sortKey, direction)) {
      const row = element(document, "tr");
      const checkCell = element(document, "td");
      const check = element(document, "input");
      check.type = "checkbox";
      check.checked = selected.has(run.run_id);
      check.setAttribute("aria-label", `Compare ${runLabel(run)}`);
      check.addEventListener("change", () => {
        check.checked ? selected.add(run.run_id) : selected.delete(run.run_id);
        render();
        [...body.querySelectorAll("input")]
          .find((node) => node.dataset.runId === run.run_id)
          ?.focus();
      });
      check.dataset.runId = run.run_id;
      const checkLabel = element(document, "label", "compare-hit-area");
      checkLabel.append(check);
      checkCell.append(checkLabel);
      row.append(checkCell);
      for (const [key] of columns) {
        let value = run[key];
        if (key === "run_id") value = shortId(run);
        if (key === "commit") value = run.commit?.slice(0, 8) ?? "—";
        if (key in run.metrics)
          value = metricText(
            run.metrics[key],
            key === "predicted_possession_count"
              ? 0
              : key === "fragmentation"
                ? 2
                : 4,
          );
        const cell = element(
          document,
          "td",
          key in run.metrics ? "numeric" : "",
          value ?? "—",
        );
        if (key === "run_id") cell.title = run.run_id;
        if (key === "commit")
          cell.title = run.commit ?? "Recording commit unavailable";
        row.append(cell);
      }
      body.append(row);
      const detailRow = element(document, "tr", "details-row"),
        cell = element(document, "td");
      cell.colSpan = columns.length + 1;
      const disclosure = details(run);
      disclosure.open = opened.has(run.run_id);
      cell.append(disclosure);
      detailRow.append(cell);
      body.append(detailRow);
    }
    if (!runs.length) {
      const row = element(document, "tr"),
        cell = element(
          document,
          "td",
          "table-empty",
          "No recorded runs available.",
        );
      cell.colSpan = columns.length + 1;
      row.append(cell);
      body.append(row);
    }
    $("experiment-table-count").textContent =
      `${runs.length} runs`;
  }
  async function reload() {
    if (loading) return;
    loading = true;
    $("experiments-reload").disabled = true;
    status.textContent = "Reading experiment registry…";
    try {
      const response = await fetch("/api/experiments", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      runs = payload.runs;
      loaded = true;
      for (const id of selected)
        if (!runs.some((run) => run.run_id === id)) selected.delete(id);
      content.hidden = !runs.length;
      status.textContent = runs.length
        ? `${runs.length} recorded runs · ${runs.filter((run) => !run.comparable).length} with incomplete evaluation provenance.`
        : "No experiments recorded yet. Record existing submission, metadata and score artifacts with scripts/record_experiment.py, then reload this registry.";
      render();
    } catch (error) {
      content.hidden = true;
      status.textContent = `Cannot load the experiment registry (${error.message}). Check the local server, then use Reload registry to retry.`;
    } finally {
      loading = false;
      $("experiments-reload").disabled = false;
    }
  }
  $("experiment-clear").addEventListener("click", () => {
    selected.clear();
    render();
  });
  $("experiments-reload").addEventListener("click", reload);
  return {
    open: () => {
      if (!loaded) return reload();
    },
    reload,
  };
}
