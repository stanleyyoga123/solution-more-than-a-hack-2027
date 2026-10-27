import test from "node:test";
import assert from "node:assert/strict";
import { BirdseyeOverlay } from "../../../frontend/web/viewer/birdseye_overlay.js";
import {
  BirdseyeOverlayRenderer,
  birdseyePosition,
} from "../../../frontend/web/viewer/birdseye_overlay_renderer.js";
import { BirdseyePlayback } from "../../../frontend/web/viewer/birdseye_playback.js";
import { sourceFrameAtClipTime } from "../../../frontend/web/viewer/clip_timeline.js";

const PITCH = { length: 105, width: 68 };
const FOOTAGE = { width: 1260, height: 816 };
const COLOURS = new Map([["home", "#64afff"], ["away", "#fa7976"]]);
const POSITIONS = [
  {
    entity_id: "player_7", entity_type: "player", team_id: "home",
    pos_x: 0.25, pos_y: 0.25,
  },
  {
    entity_id: "player_42", entity_type: "player", team_id: "away",
    pos_x: 0.75, pos_y: 0.75,
  },
  {
    entity_id: "ball", entity_type: "ball", team_id: "",
    pos_x: 0.5, pos_y: 0.5,
  },
];

/** Record the observable marker centers, colors and labels painted on a canvas. */
function recordingCanvas() {
  const markers = [];
  const labels = [];
  let circle;
  const context = {
    clearRect() { markers.length = 0; labels.length = 0; },
    beginPath() {},
    rect() {},
    clip() {},
    save() {},
    restore() {},
    arc(x, y) { circle = { x, y }; },
    fill() { markers.push({ ...circle, colour: this.fillStyle }); },
    stroke() {},
    fillRect() {},
    measureText(text) { return { width: text.length * 8 }; },
    fillText(text) { labels.push(text); },
  };
  const canvas = { width: 0, height: 0, hidden: false, getContext: () => context };
  return { canvas, markers, labels };
}

function recordingRenderer() {
  return {
    visible: false,
    drawings: [],
    render(positions, labels) {
      this.visible = true;
      this.drawings.push({ positions, labels });
    },
    hide() { this.visible = false; },
  };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

test("overlay coordinates retain pipeline 04 physical scale despite even canvas padding", () => {
  const point = birdseyePosition(0.5, 0.5, { length: 10.01, width: 6.01 });
  assert.ok(Math.abs(point.x - 60.06) < 0.000001);
  assert.ok(Math.abs(point.y - 36.06) < 0.000001);

  const { canvas } = recordingCanvas();
  new BirdseyeOverlayRenderer(
    canvas,
    { length: 10.01, width: 6.01 },
    { width: 122, height: 74 },
    COLOURS,
  );
  assert.equal(canvas.width, 122);
  assert.equal(canvas.height, 74);
});

test("footage markers use the camera and pitch colors with independent label visibility", () => {
  const { canvas, markers, labels } = recordingCanvas();
  const renderer = new BirdseyeOverlayRenderer(canvas, PITCH, FOOTAGE, COLOURS);
  renderer.render(POSITIONS, true);

  assert.equal(canvas.hidden, false);
  assert.deepEqual(markers, [
    { x: 315, y: 204, colour: "#64afff" },
    { x: 945, y: 612, colour: "#fa7976" },
    { x: 630, y: 408, colour: "#f9e572" },
  ]);
  assert.deepEqual(labels, ["7", "42", "Ball"]);

  renderer.render(POSITIONS, false);
  assert.equal(markers.length, 3);
  assert.deepEqual(labels, []);
  renderer.hide();
  assert.equal(canvas.hidden, true);
  assert.deepEqual(markers, []);
});

test("a newer displayed frame discards positions returned for an older frame", async () => {
  const renderer = recordingRenderer();
  const older = deferred();
  const newer = deferred();
  const requests = [];
  const cache = {
    peek: () => undefined,
    get(frame) {
      requests.push(frame);
      return frame === 105 ? older.promise : newer.promise;
    },
  };
  const overlay = new BirdseyeOverlay(renderer, cache);
  overlay.showFrame(105);
  overlay.showFrame(106);
  assert.equal(renderer.visible, false);

  older.resolve({ frame: 105, normalized: [POSITIONS[0]] });
  await flushPromises();
  assert.deepEqual(renderer.drawings, []);
  newer.resolve({ frame: 106, normalized: [POSITIONS[1]] });
  await flushPromises();
  assert.deepEqual(requests, [105, 106]);
  assert.equal(renderer.visible, true);
  assert.deepEqual(renderer.drawings.at(-1).positions, [POSITIONS[1]]);
});

test("overlay and label toggles redraw only the current displayed footage frame", async () => {
  const renderer = recordingRenderer();
  const cache = { peek: () => ({ frame: 105, normalized: POSITIONS }) };
  const overlay = new BirdseyeOverlay(renderer, cache);
  overlay.showFrame(105);
  await flushPromises();
  overlay.setLabels(false);
  await flushPromises();
  assert.equal(renderer.drawings.at(-1).labels, false);

  overlay.setVisible(false);
  assert.equal(renderer.visible, false);
  overlay.setVisible(true);
  await flushPromises();
  assert.equal(renderer.visible, true);
  assert.deepEqual(renderer.drawings.at(-1).positions, POSITIONS);

  overlay.showFrame(null);
  overlay.setLabels(true);
  await flushPromises();
  assert.equal(renderer.visible, false);
});

test("hidden footage invalidates pending positions and failed loading leaves no old markers", async () => {
  const renderer = recordingRenderer();
  const pending = deferred();
  const cache = { peek: () => undefined, get: () => pending.promise };
  const overlay = new BirdseyeOverlay(renderer, cache);
  overlay.showFrame(105);
  overlay.showFrame(null);
  pending.resolve({ frame: 105, normalized: POSITIONS });
  await flushPromises();
  assert.equal(renderer.visible, false);
  assert.deepEqual(renderer.drawings, []);

  const failure = deferred();
  const failedOverlay = new BirdseyeOverlay(renderer, {
    peek: () => undefined,
    get: () => failure.promise,
  });
  failedOverlay.showFrame(106);
  failure.reject(new Error("Tracking request failed"));
  await flushPromises();
  assert.equal(renderer.visible, false);
  assert.deepEqual(renderer.drawings, []);
});

test("displayed clip timestamps map to original source frames with the rendered offset", () => {
  const clip = { fps: 25, frame_count: 20, start_frame: 100 };
  assert.equal(sourceFrameAtClipTime(0, 25, clip), 100);
  assert.equal(sourceFrameAtClipTime(0.16, 25, clip), 104);
  assert.equal(sourceFrameAtClipTime(0.799, 25, clip), 119);
  assert.equal(sourceFrameAtClipTime(-0.04, 25, clip), null);
  assert.equal(sourceFrameAtClipTime(0.8, 25, clip), null);
});

test("playback publishes the displayed footage frame and clears overlays while unavailable", () => {
  const video = Object.assign(new EventTarget(), {
    readyState: 2,
    currentTime: 0,
    seeking: false,
    paused: true,
    hidden: false,
    playbackRate: 1,
    pause() { this.paused = true; },
    play() { this.paused = false; return Promise.resolve(); },
    requestVideoFrameCallback(callback) { this.onFrame = callback; return 1; },
  });
  const clip = {
    video_url: "/birdseye-video", ...FOOTAGE,
    fps: 25, frame_count: 20, start_frame: 100,
  };
  const frames = [];
  const follower = new BirdseyePlayback(
    video,
    { textContent: "", dataset: {} },
    clip,
    25,
    (frame) => frames.push(frame),
  );
  follower.start();
  follower.sync(105, false, 1);
  assert.equal(frames.at(-1), null);
  video.dispatchEvent(new Event("loadedmetadata"));
  video.dispatchEvent(new Event("seeked"));
  assert.equal(video.hidden, false);

  video.onFrame(0, { mediaTime: 0.16 });
  assert.equal(frames.at(-1), 104);

  follower.sync(105, true, 1);
  if (video.hidden) {
    assert.equal(frames.at(-1), null);
  } else {
    assert.equal(frames.at(-1), 104);
  }

  video.dispatchEvent(new Event("waiting"));
  assert.equal(frames.at(-1), null);
  follower.suspend("Source seeking");
  assert.equal(frames.at(-1), null);
  follower.sync(120, false, 1);
  assert.equal(frames.at(-1), null);
  video.dispatchEvent(new Event("error"));
  assert.equal(frames.at(-1), null);
  assert.equal(video.hidden, true);
});
