import test from "node:test";
import assert from "node:assert/strict";
import { ViewerController } from "../../../frontend/web/viewer/viewer_controller.js";

/** Exercise the public video callbacks while tracking requests remain unresolved. */
function viewerFixture() {
  const video = Object.assign(new EventTarget(), {
    currentTime: 0, paused: true, seeking: false, ended: false, playbackRate: 1,
    pause() { this.paused = true; },
    requestVideoFrameCallback(callback) { this.nextFrame = callback; },
  });
  const controls = Object.fromEntries([
    "play", "previous", "next", "kickoff", "timeline", "frame", "speed",
    "cameraLabels", "pitchLabels", "birdseyeLabels", "birdseyeOverlay",
    "overlay", "keyboardTarget",
  ].map((name) => [name, Object.assign(new EventTarget(), { checked: true })]));
  const predictions = {
    displayed: [], suspended: 0, ready: false,
    setReady(ready) { this.ready = ready; },
    suspend() { this.suspended++; },
    showFrame(frame) { this.displayed.push(frame); },
  };
  const cache = {
    requests: [],
    peek() { return null; },
    get(frame) {
      return new Promise((resolve) => this.requests.push({ frame, resolve }));
    },
    prefetch: async () => {},
  };
  const camera = { clear() {}, render: () => 0 };
  const view = {
    enableControls() {}, showFrame() {}, showStatus() {}, showPlaying() {},
    clearCounts() {}, showCounts() {},
  };
  const controller = new ViewerController({
    video, controls, predictions, cache, camera, view,
    pitch: { clear() {}, render() {} },
    birdseye: { start() {}, suspend() {}, sync() {} },
    birdseyeOverlay: { setLabels() {}, setVisible() {} },
    qualityReview: { setReady() {}, showFrame() {} },
    metadata: { frame_count: 100, fps: 25, default_frame: 0, video_url: "/video" },
  });
  return { controller, predictions, video, cache };
}

test("the decoded source frame updates predictions before tracking data arrives", async () => {
  const fixture = viewerFixture();
  fixture.controller.start();
  fixture.video.dispatchEvent(new Event("loadedmetadata"));

  fixture.video.nextFrame(0, { mediaTime: 10 / 25 });
  assert.equal(fixture.predictions.ready, true);
  assert.deepEqual(fixture.predictions.displayed, [10]);
  assert.equal(fixture.cache.requests[0].frame, 10);

  fixture.video.nextFrame(0, { mediaTime: 20 / 25 });
  assert.deepEqual(fixture.predictions.displayed, [10, 20]);
  fixture.cache.requests[0].resolve({ pixels: [], normalized: [] });
  await Promise.resolve();
  assert.deepEqual(fixture.predictions.displayed, [10, 20]);
});

test("seeking and source errors clear the old prediction before any new decoded frame", () => {
  const fixture = viewerFixture();
  fixture.controller.start();
  fixture.video.dispatchEvent(new Event("loadedmetadata"));
  fixture.video.nextFrame(0, { mediaTime: 10 / 25 });
  const initial = fixture.predictions.suspended;

  fixture.controller.seek(50);
  assert.equal(fixture.predictions.suspended, initial + 1);
  assert.deepEqual(fixture.predictions.displayed, [10]);
  fixture.video.seeking = true;
  fixture.video.dispatchEvent(new Event("seeking"));
  fixture.video.nextFrame(0, { mediaTime: 10 / 25 });
  assert.equal(fixture.predictions.suspended, initial + 2);
  assert.deepEqual(fixture.predictions.displayed, [10]);
  fixture.video.dispatchEvent(new Event("error"));
  assert.equal(fixture.predictions.ready, false);
});
