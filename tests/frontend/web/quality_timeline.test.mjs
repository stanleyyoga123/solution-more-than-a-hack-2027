import test from "node:test";
import assert from "node:assert/strict";
import { qualityEventColour } from "../../../frontend/web/viewer/quality_model.js";
import { QualityTimeline } from "../../../frontend/web/viewer/quality_timeline.js";

/** Capture rectangles that reach the displayed canvas through its background. */
function recordingTimeline(frameCount) {
  let painted = [];
  function createCanvas() {
    const rectangles = [];
    const context = {
      clearRect() { rectangles.length = 0; },
      fillRect(x, y, width, height) {
        rectangles.push({ x, y, width, height, colour: this.fillStyle });
      },
      strokeRect() {},
      drawImage(image) { painted = image.rectangles.map((rectangle) => ({ ...rectangle })); },
      beginPath() {},
      moveTo() {},
      lineTo() {},
      stroke() {},
    };
    return {
      width: 100,
      height: 100,
      rectangles,
      ownerDocument: { createElement: createCanvas },
      getContext: () => context,
      getBoundingClientRect: () => ({ left: 10, top: 20, width: 100, height: 100 }),
    };
  }
  const timeline = new QualityTimeline(createCanvas(), frameCount);
  return { timeline, painted: () => painted };
}

function gapAt(frame) {
  return {
    id: `gap-${frame}`,
    kind: "gap",
    entity_id: "player_7",
    entity_type: "player",
    team_id: "home",
    start_frame: frame,
    end_frame: frame,
    missing_frames: 1,
    gap_seconds: 0.04,
    left_frame: frame === 0 ? null : frame - 1,
    right_frame: null,
    endpoint_distance_m: null,
    required_speed_mps: null,
    forward_error_m: null,
    backward_error_m: null,
    status: "uncertain",
    reason: "unbounded_gap",
  };
}

test("first- and final-frame quality intervals remain visible within the timeline canvas", () => {
  for (const frame of [0, 9]) {
    const { timeline, painted } = recordingTimeline(10);
    const event = gapAt(frame);

    timeline.setEvents([event], event.id);

    const intervals = painted().filter(({ colour }) => colour === qualityEventColour(event));
    assert.ok(intervals.length > 0);
    for (const interval of intervals) {
      assert.ok(interval.x >= 0);
      assert.ok(interval.x < 100);
      assert.ok(interval.width > 0);
      assert.ok(interval.x + interval.width <= 100);
    }
  }
});

test("clicking the timeline's right boundary selects the final source frame in either lane", () => {
  const { timeline } = recordingTimeline(10);

  assert.deepEqual(timeline.pointAt({ clientX: 109.9, clientY: 30 }), {
    frame: 9, lane: "motion",
  });
  assert.deepEqual(timeline.pointAt({ clientX: 110, clientY: 100 }), {
    frame: 9, lane: "gap",
  });
});

test("a single-frame recording keeps its interval visible and all timeline clicks on frame zero", () => {
  const { timeline, painted } = recordingTimeline(1);
  const event = gapAt(0);

  timeline.setEvents([event], null);

  const intervals = painted().filter(({ colour }) => colour === qualityEventColour(event));
  assert.equal(intervals.length, 1);
  assert.ok(intervals[0].x >= 0);
  assert.ok(intervals[0].width > 0);
  assert.ok(intervals[0].x + intervals[0].width <= 100);
  for (const clientX of [10, 60, 110]) {
    assert.equal(timeline.pointAt({ clientX, clientY: 100 }).frame, 0);
  }
});
