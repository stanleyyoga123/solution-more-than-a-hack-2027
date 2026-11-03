/** Pure registry selection and formatting; missing measurements remain missing. */
export const metricKeys = [
  "spell_f1_mean",
  "macro_f1",
  "dead_ball_f1",
  "predicted_possession_count",
  "fragmentation",
];
export const finite = (value) =>
  typeof value === "number" && Number.isFinite(value);
export function metricText(value, digits = 4) {
  return finite(value)
    ? value.toLocaleString("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
    : "—";
}
export function shortId(run) {
  return run.run_id.split("-").at(-1).slice(0, 8);
}
export function runLabel(run) {
  return `${run.pipeline ?? "Unknown pipeline"} · ${run.strategy ?? "Unknown strategy"} · ${shortId(run)}`;
}
export function filterRuns(
  runs,
  { query = "", pipeline = "", status = "" } = {},
) {
  const search = query.trim().toLowerCase();
  return runs.filter(
    (run) =>
      (!pipeline || run.pipeline === pipeline) &&
      (!status || run.status === status) &&
      (!search ||
        [
          run.pipeline,
          run.strategy,
          run.run_id,
          run.commit,
          run.evaluation?.scope,
          run.evaluation?.dataset_id,
        ]
          .join(" ")
          .toLowerCase()
          .includes(search)),
  );
}
export function sortRuns(runs, key, direction = "asc") {
  const value = (run) =>
    metricKeys.includes(key)
      ? run.metrics[key]
      : key === "scope"
        ? run.evaluation?.scope
        : run[key];
  return [...runs].sort((a, b) => {
    const left = value(a),
      right = value(b);
    if (left == null && right == null) return a.run_id.localeCompare(b.run_id);
    if (left == null) return 1;
    if (right == null) return -1;
    const order =
      typeof left === "number"
        ? left - right
        : String(left).localeCompare(String(right));
    return (
      order * (direction === "desc" ? -1 : 1) ||
      a.run_id.localeCompare(b.run_id)
    );
  });
}
export function comparisonRuns(runs, groupId, selected) {
  return runs.filter(
    (run) =>
      (!groupId || run.group_id === groupId) &&
      (!selected.size || selected.has(run.run_id)),
  );
}
export function scatterPoints(runs) {
  return runs
    .filter(
      (run) =>
        finite(run.metrics.dead_ball_f1) && finite(run.metrics.spell_f1_mean),
    )
    .map((run) => ({
      run,
      x: run.metrics.dead_ball_f1,
      y: run.metrics.spell_f1_mean,
    }));
}
export function fragmentationRows(runs) {
  return runs.map((run) => ({
    run,
    predicted: run.metrics.predicted_possession_count ?? null,
    truth: run.metrics.ground_truth_possession_count ?? null,
    ratio: run.metrics.fragmentation ?? null,
  }));
}
