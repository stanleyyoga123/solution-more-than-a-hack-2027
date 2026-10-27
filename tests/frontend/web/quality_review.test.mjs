import test from "node:test";
import assert from "node:assert/strict";
import { QualityReviewController } from "../../../frontend/web/viewer/quality_review_controller.js";

function payload(episodes = [], gaps = []) {
  return {
    available: { trajectories: true, gaps: true },
    summary: {
      flagged_samples: episodes.length,
      trajectory_episodes: episodes.length,
      gap_count: gaps.length,
      status_counts: { plausible: 0, implausible: 0, uncertain: gaps.length },
    },
    episodes,
    gaps,
  };
}

function episode(id, start, peak, entity = "player_7") {
  return {
    id, entity_id: entity, entity_type: "player", team_id: "home",
    start_frame: start, end_frame: peak + 1, peak_frame: peak,
    peak_speed_mps: 20, peak_acceleration_mps2: null,
    speed_flag: true, acceleration_flag: false, sample_count: 2,
  };
}

/** Exercise public controller actions through controls without a browser DOM. */
function reviewHarness(client) {
  const controls = Object.fromEntries([
    "category", "entity", "highlight", "previous", "next", "previousPage",
    "nextPage", "clear", "before", "after", "list", "timeline",
  ].map((name) => [name, Object.assign(new EventTarget(), { value: "all", checked: true })]));
  const view = {
    controls,
    statuses: [],
    lists: [],
    selections: [],
    showReports() {},
    showStatus(message, error) { this.statuses.push({ message, error }); },
    showList(events, selected, page, total, ready) {
      this.lists.push({ events, selected, page, total, ready });
    },
    showSelection(event, frame, ready) { this.selections.push({ event, frame, ready }); },
    showFrame() {},
    setNavigation() {},
  };
  const timeline = {
    point: { frame: 0, lane: "gap" },
    setEvents() {},
    showFrame() {},
    pointAt() { return this.point; },
  };
  const seeks = [];
  const highlights = [];
  const controller = new QualityReviewController(
    client, view, timeline,
    (frame) => seeks.push(frame),
    (entity) => highlights.push(entity),
  );
  return { controller, view, timeline, seeks, highlights, controls };
}

test("quality navigation waits for video readiness and selects the episode peak once ready", async () => {
  const harness = reviewHarness({ quality: async () => payload([episode("motion", 10, 17)]) });
  await harness.controller.start();

  harness.controls.next.dispatchEvent(new Event("click"));
  assert.deepEqual(harness.seeks, []);
  harness.controller.setReady(true);
  harness.controls.next.dispatchEvent(new Event("click"));

  assert.deepEqual(harness.seeks, [17]);
  assert.equal(harness.highlights.at(-1), "player_7");
  assert.equal(harness.view.selections.at(-1).event.id, "motion");
  harness.controls.highlight.checked = false;
  harness.controls.highlight.dispatchEvent(new Event("change"));
  assert.equal(harness.highlights.at(-1), null);
  assert.deepEqual(harness.seeks, [17]);
});

test("filtering away the selected event clears its highlight and resets the visible list", async () => {
  const harness = reviewHarness({
    quality: async () => payload([
      episode("first", 10, 12), episode("second", 20, 22, "player_8"),
    ]),
  });
  await harness.controller.start();
  harness.controller.setReady(true);
  harness.controls.next.dispatchEvent(new Event("click"));

  harness.controls.entity.value = "player_8";
  harness.controls.entity.dispatchEvent(new Event("change"));

  assert.equal(harness.highlights.at(-1), null);
  assert.equal(harness.view.selections.at(-1).event, null);
  assert.deepEqual(harness.view.lists.at(-1).events.map(({ id }) => id), ["second"]);
  assert.equal(harness.view.lists.at(-1).page, 0);
  assert.deepEqual(harness.seeks, [12]);
});

test("leading-gap review seeks its start and ignores the absent left boundary", async () => {
  const leadingGap = {
    id: "leading", entity_id: "player_7", entity_type: "player", team_id: "home",
    start_frame: 0, end_frame: 9, missing_frames: 10, gap_seconds: 0.4,
    left_frame: null, right_frame: 10, endpoint_distance_m: null,
    required_speed_mps: null, forward_error_m: null, backward_error_m: null,
    status: "uncertain", reason: "unbounded_gap",
  };
  const harness = reviewHarness({ quality: async () => payload([], [leadingGap]) });
  await harness.controller.start();
  harness.controller.setReady(true);

  harness.controls.timeline.dispatchEvent(new Event("click"));
  harness.controls.before.dispatchEvent(new Event("click"));
  harness.controls.after.dispatchEvent(new Event("click"));

  assert.deepEqual(harness.seeks, [0, 10]);
  assert.equal(harness.highlights.at(-1), "player_7");
  harness.controls.clear.dispatchEvent(new Event("click"));
  assert.equal(harness.highlights.at(-1), null);
  assert.equal(harness.view.selections.at(-1).event, null);
});

test("quality list pagination keeps large reports bounded and follows filtered results", async () => {
  const episodes = Array.from({ length: 121 }, (_, index) => (
    episode(`event-${index}`, index * 10 + 1, index * 10 + 3)
  ));
  const harness = reviewHarness({ quality: async () => payload(episodes) });
  await harness.controller.start();

  assert.equal(harness.view.lists.at(-1).events.length, 50);
  harness.controls.nextPage.dispatchEvent(new Event("click"));
  assert.equal(harness.view.lists.at(-1).events[0].id, "event-50");
  harness.controls.nextPage.dispatchEvent(new Event("click"));
  assert.equal(harness.view.lists.at(-1).events.length, 21);
  harness.controls.nextPage.dispatchEvent(new Event("click"));
  assert.equal(harness.view.lists.at(-1).page, 2);

  harness.controls.category.value = "uncertain";
  harness.controls.category.dispatchEvent(new Event("change"));
  assert.deepEqual(harness.view.lists.at(-1).events, []);
  assert.equal(harness.view.lists.at(-1).page, 0);
});

test("quality loading failure is presented locally and does not seek or reject viewer startup", async () => {
  const harness = reviewHarness({ quality: async () => { throw new Error("Report request failed"); } });

  await harness.controller.start();
  harness.controller.setReady(true);
  harness.controls.next.dispatchEvent(new Event("click"));

  assert.deepEqual(harness.seeks, []);
  assert.deepEqual(harness.highlights, []);
  assert.equal(harness.view.statuses.length, 1);
  assert.match(harness.view.statuses[0].message, /Report request failed/);
  assert.equal(harness.view.statuses[0].error, true);
  assert.deepEqual(harness.view.lists.at(-1).events, []);
});
