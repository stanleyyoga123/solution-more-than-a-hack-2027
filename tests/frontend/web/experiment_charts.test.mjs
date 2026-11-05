import test from "node:test";
import assert from "node:assert/strict";
import {
  renderScatter,
  renderScores,
  renderFragmentation,
} from "../../../frontend/web/experiments/charts.js";

// Minimal drawing surface: record real SVG output and activation handlers.
function drawing() {
  const document = {
    createElement: (tag) => node(tag),
    createElementNS: (_, tag) => node(tag),
  };
  function node(tag) {
    return {
      tag,
      ownerDocument: document,
      attrs: {},
      children: [],
      events: {},
      textContent: "",
      setAttribute(key, value) {
        this.attrs[key] = value;
      },
      append(...nodes) {
        this.children.push(...nodes);
      },
      replaceChildren(...nodes) {
        this.children = nodes;
      },
      addEventListener(event, handler) {
        this.events[event] = handler;
      },
    };
  }
  const root = node("div");
  const all = () => {
    const result = [];
    const walk = (n) => {
      result.push(n);
      n.children.forEach(walk);
    };
    walk(root);
    return result;
  };
  return { root, all };
}
const run = {
  run_id: "11-test",
  pipeline: "11_possession_deadball",
  strategy: "control",
  metrics: {
    dead_ball_f1: 0,
    spell_f1_mean: 0.5,
    macro_f1: 0,
    predicted_possession_count: 20,
    ground_truth_possession_count: 17,
    fragmentation: 1.2,
  },
  full_submission_possession_count: 999,
};

test("zero scatter coordinates are visible inside padded axes and marks open details by keyboard", () => {
  const { root, all } = drawing();
  let selected;
  renderScatter(
    root,
    [run, { ...run, metrics: { dead_ball_f1: null, spell_f1_mean: 0.5 } }],
    (r) => (selected = r),
  );
  const points = all().filter((n) => n.tag === "circle");
  assert.equal(points.length, 1);
  assert.equal(points[0].attrs.cx, "65");
  assert.equal(points[0].attrs.cy, "150");
  assert.match(points[0].attrs["aria-label"], /control.*Dead-ball F1: 0.0000/);
  points[0].events.keydown({ key: "Enter", preventDefault() {} });
  assert.equal(selected, run);
});
test("score bars render measured zero as a visible mark but never draw missing values", () => {
  const { root, all } = drawing();
  renderScores(root, [
    { ...run, metrics: { spell_f1_mean: null, macro_f1: 0 } },
  ]);
  const bars = all().filter((n) => n.tag === "rect");
  assert.equal(bars.length, 1);
  assert.equal(bars[0].attrs.width, "2");
  assert.match(bars[0].attrs["aria-label"], /macroF1: 0.0000/);
});
test("fragmentation drawings label graded counts, never full-submission counts", () => {
  const { root, all } = drawing();
  renderFragmentation(root, [run]);
  const text = all()
    .map((n) => n.textContent)
    .join(" ");
  assert.match(text, /20 possessions in evaluated window/);
  assert.match(text, /17 possessions in evaluated window/);
  assert.doesNotMatch(text, /999/);
  assert.match(text, /1.20×/);
});
test("empty chart data produces explanations without bogus zero marks", () => {
  for (const render of [renderScatter, renderScores, renderFragmentation]) {
    const { root, all } = drawing();
    render(root, []);
    assert.equal(all().filter((n) => n.tag === "svg").length, 0);
    assert.ok(all().some((n) => n.tag === "p" && n.textContent.length));
  }
});

test("all chart annotations identify the full pipeline rather than a run fingerprint", () => {
  for (const render of [renderScores, renderScatter, renderFragmentation]) {
    const { root, all } = drawing();
    render(root, [run]);
    const labels = all()
      .filter(
        (node) => node.tag === "text" && node.attrs.class === "chart-label",
      )
      .map((node) => node.textContent);
    assert.deepEqual(labels, ["11_possession_deadball"]);
  }
});
