import test from "node:test";
import assert from "node:assert/strict";
import {
  filterRuns,
  sortRuns,
  comparisonRuns,
  scatterPoints,
  metricText,
  fragmentationRows,
} from "../../../frontend/web/experiments/model.js";

const runs = [
  {
    run_id: "a",
    pipeline: "05",
    strategy: "baseline",
    group_id: "public",
    comparable: true,
    status: "Dirty",
    metrics: {
      spell_f1_mean: 0.3,
      dead_ball_f1: 0,
      predicted_possession_count: 26,
      ground_truth_possession_count: 17,
      fragmentation: 1.4,
    },
  },
  {
    run_id: "b",
    pipeline: "11",
    strategy: "control",
    group_id: "public",
    comparable: true,
    status: "Incomplete",
    metrics: { spell_f1_mean: 0.5, dead_ball_f1: null },
  },
  {
    run_id: "c",
    pipeline: "09",
    strategy: "nearest",
    group_id: "unverified:c",
    comparable: false,
    status: "Incomplete",
    metrics: { spell_f1_mean: null, dead_ball_f1: 0.7 },
  },
];
test("filters combine query, pipeline and status without altering records", () => {
  assert.deepEqual(
    filterRuns(runs, { query: "BASE", pipeline: "05", status: "Dirty" }).map(
      (r) => r.run_id,
    ),
    ["a"],
  );
  assert.equal(filterRuns(runs, { query: "missing" }).length, 0);
  assert.equal(runs.length, 3);
});
test("sorts numeric metrics with missing last in both directions", () => {
  assert.deepEqual(
    sortRuns(runs, "spell_f1_mean", "asc").map((r) => r.run_id),
    ["a", "b", "c"],
  );
  assert.deepEqual(
    sortRuns(runs, "spell_f1_mean", "desc").map((r) => r.run_id),
    ["b", "a", "c"],
  );
});
test("explicit-scope comparison never crosses groups and selection intersects the scope", () => {
  assert.deepEqual(
    comparisonRuns(runs, "public", new Set(["a", "c"])).map((r) => r.run_id),
    ["a"],
  );
  assert.deepEqual(
    comparisonRuns(runs, "unverified:c", new Set()).map((r) => r.run_id),
    ["c"],
  );
});
test("scatter includes zero but excludes either missing coordinate", () => {
  assert.deepEqual(
    scatterPoints(runs).map((p) => [p.run.run_id, p.x, p.y]),
    [["a", 0, 0.3]],
  );
  assert.equal(metricText(0), "0.0000");
  assert.equal(metricText(null), "—");
});
test("fragmentation uses evaluated counts only, retaining unavailable values", () => {
  assert.deepEqual(
    fragmentationRows([{ ...runs[0], full_submission_possession_count: 900 }]),
    [
      {
        run: { ...runs[0], full_submission_possession_count: 900 },
        predicted: 26,
        truth: 17,
        ratio: 1.4,
      },
    ],
  );
  assert.equal(fragmentationRows([runs[1]])[0].predicted, null);
});

test("all-pipelines comparison includes different evaluation groups and respects selection", () => {
  assert.deepEqual(
    comparisonRuns(runs, "", new Set()).map((run) => run.run_id),
    ["a", "b", "c"],
  );
  assert.deepEqual(
    comparisonRuns(runs, "", new Set(["a", "c"])).map((run) => run.run_id),
    ["a", "c"],
  );
});
