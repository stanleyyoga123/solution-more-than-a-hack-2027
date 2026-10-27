import test from "node:test";
import assert from "node:assert/strict";
import { CameraRenderer } from "../../../frontend/web/viewer/camera_renderer.js";
import { BirdseyeOverlay } from "../../../frontend/web/viewer/birdseye_overlay.js";
import { BirdseyeOverlayRenderer } from "../../../frontend/web/viewer/birdseye_overlay_renderer.js";

const COLOURS = new Map([["home", "#64afff"], ["away", "#fa7976"]]);
const PIXELS = [
  { entity_id: "player_7", entity_type: "player", team_id: "home", pos_x: 100, pos_y: 200 },
  { entity_id: "player_8", entity_type: "player", team_id: "away", pos_x: 400, pos_y: 300 },
];
const NORMALIZED = PIXELS.map((entity) => ({
  ...entity, pos_x: entity.pos_x / 1000, pos_y: entity.pos_y / 500,
}));

/** Capture painted circles and text to inspect the visible selection outline. */
function recordingCanvas() {
  const markers = [];
  const outlines = [];
  const labels = [];
  let circle = null;
  const context = {
    clearRect() { markers.length = 0; outlines.length = 0; labels.length = 0; },
    beginPath() {},
    rect() {},
    clip() {},
    save() {},
    restore() {},
    arc(x, y, radius) { circle = { x, y, radius }; },
    fill() { markers.push({ ...circle, colour: this.fillStyle }); },
    stroke() { outlines.push({ ...circle, colour: this.strokeStyle }); },
    fillRect() {},
    measureText(text) { return { width: text.length * 8 }; },
    fillText(text) { labels.push(text); },
  };
  return {
    canvas: { width: 0, height: 0, hidden: false, getContext: () => context },
    markers,
    outlines,
    labels,
  };
}

test("camera selection outlines the observed entity while preserving team colours and label controls", () => {
  const drawing = recordingCanvas();
  const renderer = new CameraRenderer(drawing.canvas, 1000, 500, COLOURS);
  renderer.setHighlightedEntity("player_7");

  assert.equal(renderer.render(PIXELS, false, true), 2);

  assert.deepEqual(drawing.markers.map(({ x, y, colour }) => ({ x, y, colour })), [
    { x: 100, y: 200, colour: "#64afff" },
    { x: 400, y: 300, colour: "#fa7976" },
  ]);
  assert.deepEqual(drawing.labels, []);
  const rings = drawing.outlines.filter(({ radius }) => radius > 15);
  assert.equal(rings.length, 1);
  assert.equal(rings[0].x, 100);
  assert.equal(rings[0].y, 200);

  renderer.render(PIXELS, true, true);
  assert.deepEqual(drawing.labels, ["7", "8"]);
  renderer.render(PIXELS, false, false);
  assert.deepEqual(drawing.markers, []);
  assert.deepEqual(drawing.outlines, []);
});

test("a selected entity missing from camera positions creates neither a marker nor a phantom outline", () => {
  const drawing = recordingCanvas();
  const renderer = new CameraRenderer(drawing.canvas, 1000, 500, COLOURS);
  renderer.setHighlightedEntity("player_7");

  renderer.render([PIXELS[1]], false, true);

  assert.equal(drawing.markers.length, 1);
  assert.equal(drawing.outlines.filter(({ radius }) => radius > 15).length, 0);
  renderer.setHighlightedEntity(null);
  renderer.render(PIXELS, false, true);
  assert.equal(drawing.outlines.filter(({ radius }) => radius > 15).length, 0);
});

test("bird's-eye selection uses observed normalized coordinates and remains independent of labels", () => {
  const drawing = recordingCanvas();
  const renderer = new BirdseyeOverlayRenderer(
    drawing.canvas,
    { length: 105, width: 68 },
    { width: 1260, height: 816 },
    COLOURS,
  );
  renderer.setHighlightedEntity("player_7");

  renderer.render(NORMALIZED, false);

  const rings = drawing.outlines.filter(({ radius }) => radius > 9);
  assert.equal(rings.length, 1);
  assert.equal(rings[0].x, 126);
  assert.ok(Math.abs(rings[0].y - 326.4) < 1e-9);
  assert.deepEqual(drawing.labels, []);
  assert.equal(drawing.markers.length, 2);

  renderer.render([NORMALIZED[1]], true);
  assert.equal(drawing.outlines.filter(({ radius }) => radius > 9).length, 0);
  assert.deepEqual(drawing.labels, ["8"]);
  renderer.hide();
  assert.equal(drawing.canvas.hidden, true);
  assert.deepEqual(drawing.outlines, []);
});

test("changing a quality selection redraws only the currently displayed bird's-eye frame", async () => {
  const drawings = [];
  const renderer = {
    selected: null,
    visible: false,
    setHighlightedEntity(entityId) { this.selected = entityId; },
    hide() { this.visible = false; },
    render(positions, labels) {
      this.visible = true;
      drawings.push({ positions, labels, selected: this.selected });
    },
  };
  const cache = {
    peek(frame) {
      return { frame, normalized: frame === 100 ? [NORMALIZED[0]] : [NORMALIZED[1]] };
    },
  };
  const overlay = new BirdseyeOverlay(renderer, cache);
  overlay.showFrame(100);
  overlay.setHighlightedEntity("player_7");

  assert.deepEqual(drawings.at(-1), {
    positions: [NORMALIZED[0]], labels: true, selected: "player_7",
  });
  overlay.showFrame(101);
  overlay.setLabels(false);
  assert.deepEqual(drawings.at(-1), {
    positions: [NORMALIZED[1]], labels: false, selected: "player_7",
  });
  overlay.setVisible(false);
  const before = drawings.length;
  overlay.setHighlightedEntity("player_8");
  assert.equal(renderer.visible, false);
  assert.equal(drawings.length, before);
  overlay.showFrame(null);
  overlay.setVisible(true);
  assert.equal(renderer.visible, false);
  assert.equal(drawings.length, before);
});
