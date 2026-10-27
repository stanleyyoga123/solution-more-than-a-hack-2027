import test from "node:test";
import assert from "node:assert/strict";
import {
  pitchGeometry,
  pitchPosition,
} from "../../../frontend/web/viewer/pitch_geometry.js";

test("pitch coordinates retain physical aspect and downward y orientation", () => {
  const geometry = pitchGeometry(1200, 760, 105, 68);
  assert.ok(Math.abs(geometry.width / geometry.height - 105 / 68) < 1e-12);
  assert.deepEqual(pitchPosition(0, 0, geometry), {
    x: geometry.x,
    y: geometry.y,
  });
  const corner = pitchPosition(1, 1, geometry);
  assert.equal(corner.x, geometry.x + geometry.width);
  assert.equal(corner.y, geometry.y + geometry.height);
  const outside = pitchPosition(-0.02, 1.03, geometry);
  assert.ok(outside.x < geometry.x);
  assert.ok(outside.y > geometry.y + geometry.height);
});
