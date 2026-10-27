import test from "node:test";
import assert from "node:assert/strict";
import { PredictionController } from "../../../frontend/web/viewer/prediction_controller.js";
import { PredictionView } from "../../../frontend/web/viewer/prediction_view.js";

const SEGMENTS = [
  { start_frame: 0, end_frame: 9, label: "H" },
  { start_frame: 10, end_frame: 19, label: "A" },
  { start_frame: 25, end_frame: 29, label: "X" },
];

function payload(available = true) {
  return {
    available, filename: available ? "prediction.csv" : null,
    row_count: available ? 25 : 0,
    segments: available ? SEGMENTS : [], counts: { H: 10, A: 10, D: 0, X: 5 },
  };
}

function harness(client = { predictions: async () => payload() }) {
  const controls = Object.fromEntries(["previous", "next", "overlay", "timeline"]
    .map((name) => [name, Object.assign(new EventTarget(), { checked: true })]));
  const view = {
    controls, frames: [], unavailable: [], hidden: false, waiting: false,
    showPayload(value) { this.payload = value; },
    showUnavailable(message, error) { this.unavailable.push({ message, error }); },
    showFrame(segment, frame, visible) {
      this.frames.push({ segment, frame, visible });
      this.hidden = !visible;
    },
    showWaiting() { this.waiting = true; this.hidden = true; },
    clearOverlay() { this.hidden = true; },
    setNavigation(previous, next, ready) { this.navigation = { previous, next, ready }; },
  };
  const timeline = {
    setSegments(segments) { this.segments = segments; },
    showFrame(frame) { this.frame = frame; },
    frameAt() { return 26; },
  };
  const seeks = [];
  const controller = new PredictionController(client, view, timeline, (frame) => seeks.push(frame));
  return { controller, view, controls, timeline, seeks };
}

test("predictions load once, follow displayed frames and support interval or timeline navigation", async () => {
  let requests = 0;
  const fixture = harness({ predictions: async () => { requests++; return payload(); } });
  await fixture.controller.start();
  fixture.controller.showFrame(9);
  fixture.controls.next.dispatchEvent(new Event("click"));
  assert.deepEqual(fixture.seeks, []);

  fixture.controller.setReady(true);
  assert.equal(fixture.view.frames.at(-1).segment.label, "H");
  fixture.controls.next.dispatchEvent(new Event("click"));
  fixture.controller.showFrame(10);
  assert.equal(fixture.view.frames.at(-1).segment.label, "A");
  fixture.controls.previous.dispatchEvent(new Event("click"));
  fixture.controls.timeline.dispatchEvent(new Event("click"));
  fixture.controller.showFrame(22);
  assert.equal(fixture.view.frames.at(-1).segment, null);
  fixture.controller.showFrame(25);
  assert.equal(fixture.view.frames.at(-1).segment.label, "X");
  assert.deepEqual(fixture.seeks, [10, 0, 26]);
  assert.equal(requests, 1);
});

test("seeking clears the displayed prediction and an overlay toggle cannot resurrect a stale frame", async () => {
  const fixture = harness();
  await fixture.controller.start();
  fixture.controller.setReady(true);
  fixture.controller.showFrame(3);
  assert.equal(fixture.view.hidden, false);

  fixture.controller.suspend();
  fixture.controls.overlay.checked = false;
  fixture.controls.overlay.dispatchEvent(new Event("change"));
  fixture.controls.overlay.checked = true;
  fixture.controls.overlay.dispatchEvent(new Event("change"));
  fixture.controls.next.dispatchEvent(new Event("click"));
  assert.equal(fixture.view.hidden, true);
  assert.equal(fixture.timeline.frame, null);
  assert.deepEqual(fixture.seeks, []);

  fixture.controller.showFrame(13);
  assert.equal(fixture.view.frames.at(-1).segment.label, "A");
  fixture.controls.overlay.checked = false;
  fixture.controls.overlay.dispatchEvent(new Event("change"));
  assert.equal(fixture.view.frames.at(-1).visible, false);
  assert.equal(fixture.view.frames.at(-1).segment.label, "A");
});

test("a late prediction response uses the latest displayed frame", async () => {
  let resolve;
  const fixture = harness({ predictions: () => new Promise((done) => { resolve = done; }) });
  const loading = fixture.controller.start();
  fixture.controller.setReady(true);
  fixture.controller.showFrame(3);
  fixture.controller.showFrame(15);
  resolve(payload());
  await loading;
  assert.equal(fixture.view.frames.at(-1).frame, 15);
  assert.equal(fixture.view.frames.at(-1).segment.label, "A");
});

test("absent or failed predictions leave navigation disabled without rejecting startup", async () => {
  for (const client of [
    { predictions: async () => payload(false) },
    { predictions: async () => { throw new Error("HTTP 500"); } },
  ]) {
    const fixture = harness(client);
    await fixture.controller.start();
    fixture.controller.setReady(true);
    fixture.controller.showFrame(10);
    fixture.controls.next.dispatchEvent(new Event("click"));
    fixture.controls.timeline.dispatchEvent(new Event("click"));
    assert.deepEqual(fixture.seeks, []);
    assert.equal(fixture.view.frames.length, 0);
    assert.equal(fixture.view.hidden, true);
    assert.equal(fixture.view.navigation.ready, false);
  }
});

test("prediction view distinguishes abstention and missing CSV rows and reports inclusive interval duration", () => {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) {
      elements.set(selector, { style: { setProperty() {} }, dataset: {} });
    }
    return elements.get(selector);
  }
  const overlay = { style: { setProperty() {} }, hidden: true };
  const view = new PredictionView({ querySelector: element }, overlay, {
    teams: { home: "Barcelona", away: "Athletic" }, fps: 25, frame_count: 30,
  });
  view.showPayload(payload());
  view.showFrame(SEGMENTS[2], 25, true);
  assert.equal(element("#prediction-current").textContent, "No answer (X)");
  assert.match(element("#prediction-interval").textContent, /Frames 25–29/);
  assert.match(element("#prediction-interval").textContent, /0.20 s/);
  assert.equal(overlay.hidden, false);

  view.showFrame(null, 22, true);
  assert.equal(element("#prediction-current").textContent, "No prediction for this frame");
  assert.match(overlay.textContent, /^Prediction · No prediction/);
  view.showWaiting();
  assert.equal(overlay.hidden, true);
});
