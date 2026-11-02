import test from "node:test";
import assert from "node:assert/strict";
import { setupNavigation } from "../../../frontend/web/navigation.js";

function target() {
  return {
    hidden: false,
    attrs: {},
    handlers: {},
    setAttribute(k, v) {
      this.attrs[k] = v;
    },
    addEventListener(k, f) {
      this.handlers[k] = f;
    },
  };
}
test("navigation preserves panels, pauses video and scopes viewer activation", () => {
  const elements = Object.fromEntries(
    [
      "tracking-tab",
      "experiments-tab",
      "tracking-panel",
      "experiments-panel",
    ].map((id) => [id, target()]),
  );
  let pauses = 0,
    loads = 0;
  const document = { querySelector: (selector) => elements[selector.slice(1)] };
  const nav = setupNavigation(document, {
    leaveTracking: () => pauses++,
    openExperiments: () => loads++,
  });
  assert.equal(elements["tracking-panel"].hidden, false);
  nav.show("experiments");
  assert.equal(elements["tracking-panel"].hidden, true);
  assert.equal(elements["experiments-panel"].hidden, false);
  assert.equal(elements["experiments-tab"].attrs["aria-current"], "page");
  assert.equal(pauses, 1);
  assert.equal(loads, 1);
  nav.show("tracking");
  assert.equal(elements["tracking-panel"].hidden, false);
  assert.equal(elements["experiments-panel"].hidden, true);
});

// Exercise the existing controller's real key handler while its view is hidden.
import { ViewerController } from "../../../frontend/web/viewer/viewer_controller.js";
test("hidden viewer ignores playback keys and active viewer still steps", () => {
  let active = false,
    currentTime = 0,
    pauses = 0;
  const keyTarget = target();
  const controls = Object.fromEntries(
    [
      "play",
      "previous",
      "next",
      "kickoff",
      "timeline",
      "frame",
      "speed",
      "cameraLabels",
      "pitchLabels",
      "overlay",
      "birdseyeLabels",
      "birdseyeOverlay",
    ].map((key) => [key, target()]),
  );
  controls.keyboardTarget = keyTarget;
  controls.isActive = () => active;
  const video = {
    paused: true,
    seeking: false,
    ended: false,
    addEventListener() {},
    pause() {
      pauses++;
    },
    requestVideoFrameCallback() {},
    get currentTime() {
      return currentTime;
    },
    set currentTime(value) {
      currentTime = value;
    },
  };
  const noop = () => {};
  const controller = new ViewerController({
    video,
    controls,
    view: { showStatus: noop, showFrame: noop, showPlaying: noop, clearCounts: noop },
    cache: { peek: () => null, load: async () => null },
    camera: { clear: noop },
    pitch: { clear: noop },
    birdseye: { start: noop, suspend: noop, sync: noop },
    birdseyeOverlay: { setLabels: noop, setVisible: noop, showFrame: noop },
    metadata: {
      fps: 25,
      frame_count: 100,
      default_frame: 0,
      video_url: "/video",
    },
    qualityReview: { showFrame: noop },
  });
  controller.start();
  const event = {
    code: "ArrowRight",
    target: { closest: () => null },
    preventDefault: noop,
  };
  keyTarget.handlers.keydown(event);
  assert.equal(currentTime, 0);
  assert.equal(pauses, 0);
  active = true;
  keyTarget.handlers.keydown(event);
  assert.ok(currentTime > 0);
  assert.equal(pauses, 1);
});

test("diagnostics opens independently and pauses the tracking viewer", () => {
  const elements = Object.fromEntries(
    ["tracking", "experiments", "diagnostics"].flatMap(name =>
      ["tab", "panel"].map(kind => [`${name}-${kind}`, target()])),
  );
  let pauses = 0, opens = 0;
  const nav = setupNavigation({ querySelector: s => elements[s.slice(1)] }, {
    leaveTracking: () => pauses++, openExperiments() {},
    openDiagnostics: () => opens++,
  });
  nav.show("diagnostics");
  assert.equal(pauses, 1);
  assert.equal(opens, 1);
  assert.equal(elements["diagnostics-panel"].hidden, false);
  assert.equal(elements["tracking-panel"].hidden, true);
  assert.equal(elements["experiments-panel"].hidden, true);
  nav.show("experiments");
  assert.equal(elements["diagnostics-panel"].hidden, true);
});
