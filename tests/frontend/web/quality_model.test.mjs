import test from "node:test";
import assert from "node:assert/strict";
import {
  adjacentQualityEvent,
  eventSeekFrame,
  filterQualityEvents,
  nearestQualityEvent,
  qualityEvents,
} from "../../../frontend/web/viewer/quality_model.js";

function motion(id, start, end, peak = end, entity = "player_7") {
  return {
    id,
    entity_id: entity,
    entity_type: entity === "ball" ? "ball" : "player",
    team_id: entity === "ball" ? "" : "home",
    start_frame: start,
    end_frame: end,
    peak_frame: peak,
    peak_speed_mps: 20,
    peak_acceleration_mps2: null,
    speed_flag: true,
    acceleration_flag: false,
    sample_count: 2,
  };
}

function gap(id, start, end, status, entity = "player_7") {
  return {
    id,
    entity_id: entity,
    entity_type: "player",
    team_id: "home",
    start_frame: start,
    end_frame: end,
    missing_frames: end - start + 1,
    gap_seconds: (end - start + 1) / 25,
    left_frame: start === 0 ? null : start - 1,
    right_frame: end + 1,
    endpoint_distance_m: null,
    required_speed_mps: null,
    forward_error_m: null,
    backward_error_m: null,
    status,
    reason: status === "plausible" ? "motion_consistent" : "long_gap",
  };
}

test("quality reports become chronological motion and gap events without changing source records", () => {
  const payload = {
    episodes: [motion("motion-late", 80, 85), motion("motion-first", 10, 12)],
    gaps: [gap("gap-middle", 30, 40, "uncertain")],
  };
  const original = structuredClone(payload);

  const events = qualityEvents(payload);

  assert.deepEqual(events.map(({ id, kind }) => [id, kind]), [
    ["motion-first", "motion"],
    ["gap-middle", "gap"],
    ["motion-late", "motion"],
  ]);
  assert.deepEqual(payload, original);
  assert.equal(events[0].peak_speed_mps, 20);
  assert.equal(events[1].left_frame, 29);
});

test("quality event filters combine category and exact entity without treating motion as a gap status", () => {
  const events = qualityEvents({
    episodes: [motion("motion", 10, 12)],
    gaps: [
      gap("uncertain-player", 20, 30, "uncertain"),
      gap("implausible-player", 40, 50, "implausible"),
      gap("plausible-other", 60, 61, "plausible", "player_8"),
    ],
  });

  assert.deepEqual(filterQualityEvents(events, "all", "all"), events);
  assert.deepEqual(
    filterQualityEvents(events, "motion", "player_7").map(({ id }) => id),
    ["motion"],
  );
  assert.deepEqual(
    filterQualityEvents(events, "uncertain", "all").map(({ id }) => id),
    ["uncertain-player"],
  );
  assert.deepEqual(
    filterQualityEvents(events, "implausible", "player_7").map(({ id }) => id),
    ["implausible-player"],
  );
  assert.deepEqual(filterQualityEvents(events, "plausible", "player_7"), []);
  assert.deepEqual(
    filterQualityEvents(events, "all", "player_8").map(({ id }) => id),
    ["plausible-other"],
  );
});

test("missing quality reports produce an empty navigable collection", () => {
  const events = qualityEvents({ episodes: [], gaps: [] });

  assert.deepEqual(events, []);
  assert.equal(adjacentQualityEvent(events, null, 0, 1), null);
  assert.equal(adjacentQualityEvent(events, null, 0, -1), null);
  assert.equal(nearestQualityEvent(events, 0, "motion"), null);
});

test("selecting motion seeks its peak while gap selection seeks the observed left boundary", () => {
  assert.equal(eventSeekFrame({ ...motion("motion", 10, 20, 17), kind: "motion" }), 17);
  assert.equal(eventSeekFrame({ ...gap("gap", 30, 40, "uncertain"), kind: "gap" }), 29);
  assert.equal(eventSeekFrame({ ...gap("leading", 0, 40, "uncertain"), kind: "gap" }), 0);
});

test("gap selection preserves frame zero as an available endpoint", () => {
  const event = { ...gap("after-first-frame", 1, 3, "uncertain"), kind: "gap" };

  assert.equal(event.left_frame, 0);
  assert.equal(eventSeekFrame(event), 0);
});

test("previous and next move through filtered events without wrapping", () => {
  const events = qualityEvents({
    episodes: [motion("first", 10, 12), motion("last", 70, 75)],
    gaps: [gap("middle", 30, 40, "uncertain")],
  });

  assert.equal(adjacentQualityEvent(events, "middle", 999, -1)?.id, "first");
  assert.equal(adjacentQualityEvent(events, "middle", 0, 1)?.id, "last");
  assert.equal(adjacentQualityEvent(events, "first", 50, -1), null);
  assert.equal(adjacentQualityEvent(events, "last", 0, 1), null);
});

test("navigation without a selected event uses event starts strictly before or after the playhead", () => {
  const events = qualityEvents({
    episodes: [motion("first", 10, 20), motion("last", 70, 75)],
    gaps: [gap("middle", 30, 40, "uncertain")],
  });

  assert.equal(adjacentQualityEvent(events, null, 30, -1)?.id, "first");
  assert.equal(adjacentQualityEvent(events, null, 30, 1)?.id, "last");
  assert.equal(adjacentQualityEvent(events, "filtered-out", 25, 1)?.id, "middle");
  assert.equal(adjacentQualityEvent(events, null, 0, -1), null);
  assert.equal(adjacentQualityEvent(events, null, 100, 1), null);
});

test("timeline picking respects lanes and treats both event boundaries as part of the interval", () => {
  const events = qualityEvents({
    episodes: [motion("motion", 10, 20), motion("next-motion", 22, 25)],
    gaps: [gap("gap", 10, 21, "uncertain")],
  });

  assert.equal(nearestQualityEvent(events, 10, "motion")?.id, "motion");
  assert.equal(nearestQualityEvent(events, 20, "motion")?.id, "motion");
  assert.equal(nearestQualityEvent(events, 21, "gap")?.id, "gap");
  assert.equal(nearestQualityEvent(events, 22, "motion")?.id, "next-motion");
  assert.equal(nearestQualityEvent(events, 21, "motion")?.id, "motion");
  assert.equal(nearestQualityEvent(events.filter(({ kind }) => kind === "motion"), 10, "gap"), null);
});
