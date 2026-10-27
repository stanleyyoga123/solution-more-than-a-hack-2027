import test from "node:test";
import assert from "node:assert/strict";
import { BirdseyePlayback } from "../../../frontend/web/viewer/birdseye_playback.js";
import { clipFrameAtSourceFrame } from "../../../frontend/web/viewer/clip_timeline.js";

const SOURCE_FPS = 25;
const CLIP = {
  video_url: "/birdseye-video",
  width: 1260,
  height: 816,
  fps: 25,
  frame_count: 20,
  start_frame: 100,
};

/** A media boundary controlled by explicit metadata and seek events. */
class VideoDouble extends EventTarget {
  constructor() {
    super();
    this._currentTime = 0;
    this.readyState = 0;
    this.seeking = false;
    this.paused = true;
    this.hidden = false;
    this.playbackRate = 1;
    this.playCalls = 0;
    this.playResult = Promise.resolve();
  }

  get currentTime() {
    return this._currentTime;
  }

  set currentTime(time) {
    this._currentTime = time;
    this.seeking = true;
  }

  loadMetadata() {
    this.readyState = 1;
    this.dispatchEvent(new Event("loadedmetadata"));
  }

  finishSeek(time = this.currentTime) {
    this._currentTime = time;
    this.seeking = false;
    this.readyState = 2;
    this.dispatchEvent(new Event("seeked"));
  }

  play() {
    this.playCalls += 1;
    this.paused = false;
    return this.playResult;
  }

  pause() {
    this.paused = true;
  }

  requestVideoFrameCallback(callback) {
    this.frameCallback = callback;
    return 1;
  }
}

function playback(clip = CLIP) {
  const video = new VideoDouble();
  const status = { textContent: "", dataset: {} };
  const follower = new BirdseyePlayback(video, status, clip, SOURCE_FPS, () => {});
  follower.start();
  return { video, status, follower };
}

test("trimmed footage maps source frames to clip frames and excludes its end", () => {
  assert.equal(clipFrameAtSourceFrame(99, SOURCE_FPS, CLIP), null);
  assert.equal(clipFrameAtSourceFrame(100, SOURCE_FPS, CLIP), 0);
  assert.equal(clipFrameAtSourceFrame(105, SOURCE_FPS, CLIP), 5);
  assert.equal(clipFrameAtSourceFrame(119, SOURCE_FPS, CLIP), 19);
  assert.equal(clipFrameAtSourceFrame(120, SOURCE_FPS, CLIP), null);
});

test("a paused sync waits for metadata and reveals the requested clip frame", () => {
  const { video, status, follower } = playback();
  follower.sync(105, false, 0.5);
  assert.equal(video.hidden, true);
  assert.equal(video.paused, true);

  video.loadMetadata();
  assert.equal(video.src, CLIP.video_url);
  assert.equal(video.currentTime, 5.25 / 25);
  video.finishSeek();

  assert.equal(video.hidden, false);
  assert.equal(video.paused, true);
  assert.equal(video.playbackRate, 0.5);
  assert.equal(status.dataset.state, "ready");
});

test("shared playback controls update footage playback rate and pause position", async () => {
  const { video, follower } = playback();
  video.loadMetadata();
  follower.sync(105, true, 2);
  video.finishSeek();
  await Promise.resolve();
  assert.ok(video.playCalls > 0);
  assert.equal(video.paused, false);
  assert.equal(video.playbackRate, 2);

  follower.sync(108, false, 0.5);
  video.finishSeek();
  assert.equal(video.paused, true);
  assert.equal(video.playbackRate, 0.5);
  assert.equal(Math.floor(video.currentTime * CLIP.fps), 8);
  assert.equal(video.hidden, false);
});

test("rapid seeks keep the previous decoded frame hidden until the latest target arrives", () => {
  const { video, follower } = playback();
  video.loadMetadata();
  follower.sync(102, false, 1);
  const earlierTarget = video.currentTime;
  follower.sync(112, false, 1);
  assert.equal(video.hidden, true);

  video.finishSeek(earlierTarget);
  assert.equal(video.hidden, true);
  assert.equal(Math.floor(video.currentTime * CLIP.fps), 12);
  video.finishSeek();
  assert.equal(video.hidden, false);
});

test("missing footage and frames outside a trimmed clip stay hidden and paused", () => {
  const missing = playback(null);
  missing.follower.sync(105, true, 1);
  assert.equal(missing.video.hidden, true);
  assert.equal(missing.video.paused, true);
  assert.equal(missing.video.playCalls, 0);

  const { video, follower } = playback();
  video.loadMetadata();
  follower.sync(105, false, 1);
  video.finishSeek();
  assert.equal(video.hidden, false);

  follower.sync(120, true, 1);
  assert.equal(video.hidden, true);
  assert.equal(video.paused, true);
  follower.sync(99, true, 1);
  assert.equal(video.hidden, true);
  assert.equal(video.paused, true);
});

test("playback realigns footage when its clock falls several source frames behind", () => {
  const { video, follower } = playback();
  video.loadMetadata();
  follower.sync(102, true, 1);
  video.finishSeek();

  follower.sync(112, true, 1);
  assert.equal(Math.floor(video.currentTime * CLIP.fps), 12);
  assert.equal(video.hidden, true);
  video.finishSeek();
  assert.equal(video.hidden, false);
});

test("a late playback rejection cannot replace a newer suspended state", async () => {
  const { video, status, follower } = playback();
  let rejectPlayback;
  video.playResult = new Promise((_, reject) => {
    rejectPlayback = reject;
  });
  video.loadMetadata();
  follower.sync(105, true, 1);
  video.finishSeek();
  assert.ok(video.playCalls > 0);

  follower.suspend("Source video is seeking");
  rejectPlayback(new Error("Old play request was interrupted"));
  await Promise.resolve();
  await Promise.resolve();

  assert.equal(video.hidden, true);
  assert.equal(video.paused, true);
  assert.equal(status.textContent, "Source video is seeking");
});

test("buffering hides the previous image until the aligned footage can play again", () => {
  const { video, status, follower } = playback();
  video.loadMetadata();
  follower.sync(105, false, 1);
  video.finishSeek();
  assert.equal(video.hidden, false);

  video.dispatchEvent(new Event("waiting"));
  assert.equal(video.hidden, true);
  assert.equal(status.dataset.state, "loading");

  video.dispatchEvent(new Event("canplay"));
  assert.equal(video.hidden, false);
  assert.equal(status.dataset.state, "ready");
});

test("a terminal media error remains visible across seeks outside and inside the clip", () => {
  const { video, status, follower } = playback();
  video.loadMetadata();
  follower.sync(105, false, 1);
  video.finishSeek();
  video.dispatchEvent(new Event("error"));
  const errorMessage = status.textContent;
  assert.equal(status.dataset.state, "error");

  for (const sourceFrame of [120, 105]) {
    follower.sync(sourceFrame, false, 1);
    assert.equal(video.hidden, true);
    assert.equal(video.paused, true);
    assert.equal(status.hidden, false);
    assert.equal(status.dataset.state, "error");
    assert.equal(status.textContent, errorMessage);
  }
});
