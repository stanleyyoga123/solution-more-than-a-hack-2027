import test from "node:test";
import assert from "node:assert/strict";
import { FrameCache } from "../../../frontend/web/viewer/frame_cache.js";

function frames(start, count) {
  return Array.from({ length: count }, (_, offset) => ({
    frame: start + offset,
    pixels: [],
    normalized: [],
  }));
}

test("simultaneous frame requests share a chunk and return the requested positions", async () => {
  const requests = [];
  const client = {
    async frames(start, count) {
      requests.push({ start, count });
      return frames(start, count);
    },
  };
  const cache = new FrameCache(client, 1000);
  const [first, second] = await Promise.all([cache.get(251), cache.get(299)]);
  assert.equal(first.frame, 251);
  assert.equal(second.frame, 299);
  assert.deepEqual(requests, [{ start: 250, count: 250 }]);
  assert.equal(cache.peek(252).frame, 252);
});

test("upcoming chunks are prefetched and the final request stops at the recording end", async () => {
  const requests = [];
  const client = {
    async frames(start, count) {
      requests.push({ start, count });
      return frames(start, count);
    },
  };
  const cache = new FrameCache(client, 520);
  await cache.prefetch(425);
  assert.equal((await cache.get(519)).frame, 519);
  await cache.prefetch(519);
  assert.deepEqual(requests, [{ start: 500, count: 20 }]);
});

test("old chunks are evicted while recently visited chunks remain available", async () => {
  const client = {
    async frames(start, count) {
      return frames(start, count);
    },
  };
  const cache = new FrameCache(client, 2000);
  for (let frame = 0; frame < 1500; frame += 250) await cache.get(frame);
  await cache.get(0);
  await cache.get(1500);
  assert.equal(cache.peek(250), undefined);
  assert.equal(cache.peek(0).frame, 0);
  assert.equal(cache.peek(1500).frame, 1500);
});

test("failed downloads can be retried after a seek", async () => {
  let requests = 0;
  const client = {
    async frames(start, count) {
      requests += 1;
      if (requests === 1) throw new Error("Connection interrupted");
      return frames(start, count);
    },
  };
  const cache = new FrameCache(client, 500);
  await assert.rejects(cache.get(10), /Connection interrupted/);
  assert.equal((await cache.get(10)).frame, 10);
  assert.equal(requests, 2);
});
