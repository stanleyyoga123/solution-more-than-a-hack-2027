import test from "node:test";
import assert from "node:assert/strict";
import {
  frameAtTime,
  frameSeekTime,
  formatTime,
} from "../../../frontend/web/viewer/timeline.js";

test("decoded timestamps map to zero-based frames despite floating point boundaries", () => {
  for (const frame of [0, 1, 11186, 15000, 199318]) {
    assert.equal(frameAtTime(frame / 25, 25, 199319), frame);
    assert.equal(frameAtTime(frameSeekTime(frame, 25), 25, 199319), frame);
  }
  assert.equal(frameAtTime(447.439, 25, 199319), 11185);
  assert.equal(frameAtTime(9000, 25, 199319), 199318);
});

test("source timestamp formatting preserves milliseconds and rolls over hours", () => {
  assert.equal(formatTime(11186 / 25, true), "00:07:27.440");
  assert.equal(formatTime(3600.04, true), "01:00:00.040");
  assert.equal(formatTime(61), "00:01:01");
});
