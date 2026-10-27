import test from "node:test";
import assert from "node:assert/strict";
import {
  adjacentPrediction, predictionAt, predictionDescription,
} from "../../../frontend/web/viewer/prediction_model.js";

const SEGMENTS = [
  { start_frame: 2, end_frame: 4, label: "H" },
  { start_frame: 5, end_frame: 5, label: "A" },
  { start_frame: 8, end_frame: 10, label: "X" },
  { start_frame: 11, end_frame: 12, label: "D" },
];

test("prediction lookup honors both inclusive boundaries and keeps missing CSV frames distinct from X", () => {
  for (const frame of [2, 3, 4]) assert.equal(predictionAt(SEGMENTS, frame), SEGMENTS[0]);
  assert.equal(predictionAt(SEGMENTS, 5), SEGMENTS[1]);
  assert.equal(predictionAt(SEGMENTS, 10), SEGMENTS[2]);
  assert.equal(predictionAt(SEGMENTS, 12), SEGMENTS[3]);
  for (const frame of [0, 1, 6, 7, 13]) assert.equal(predictionAt(SEGMENTS, frame), null);
  assert.equal(predictionAt([], 0), null);
});

test("prediction change navigation finds strict previous and next starts without wrapping", () => {
  assert.equal(adjacentPrediction(SEGMENTS, 0, 1), SEGMENTS[0]);
  assert.equal(adjacentPrediction(SEGMENTS, 2, -1), null);
  assert.equal(adjacentPrediction(SEGMENTS, 4, -1), SEGMENTS[0]);
  assert.equal(adjacentPrediction(SEGMENTS, 5, -1), SEGMENTS[0]);
  assert.equal(adjacentPrediction(SEGMENTS, 6, 1), SEGMENTS[2]);
  assert.equal(adjacentPrediction(SEGMENTS, 6, -1), SEGMENTS[1]);
  assert.equal(adjacentPrediction(SEGMENTS, 12, 1), null);
});

test("prediction descriptions identify submitted teams and distinguish dead play from abstention", () => {
  const teams = { home: "Barcelona", away: "Athletic" };
  assert.equal(predictionDescription("H", teams), "Barcelona possession (H)");
  assert.equal(predictionDescription("A", teams), "Athletic possession (A)");
  assert.equal(predictionDescription("D", teams), "Dead ball (D)");
  assert.equal(predictionDescription("X", teams), "No answer (X)");
});
