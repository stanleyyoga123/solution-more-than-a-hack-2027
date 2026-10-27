const CHUNK_SIZE = 250;
const MAX_CHUNKS = 6;

/** A bounded cache of frame chunks; concurrent requests share one download. */
export class FrameCache {
  /**
   * @param {import('./tracking_client.js').TrackingClient} client
   * @param {number} frameCount
   */
  constructor(client, frameCount) {
    this._client = client;
    this._frameCount = frameCount;
    /** @type {Map<number, Map<number, import('./tracking_types.js').TrackingFrame>>} */
    this._chunks = new Map();
    /** @type {Map<number, Promise<Map<number, import('./tracking_types.js').TrackingFrame>>>} */
    this._pending = new Map();
  }

  /** @param {number} frame */
  peek(frame) {
    const start = Math.floor(frame / CHUNK_SIZE) * CHUNK_SIZE;
    return this._chunks.get(start)?.get(frame);
  }

  /** @param {number} frame */
  async get(frame) {
    const start = Math.floor(frame / CHUNK_SIZE) * CHUNK_SIZE;
    const chunk = await this._loadChunk(start);
    return chunk.get(frame);
  }

  /** Load the upcoming chunk before playback reaches its boundary. @param {number} frame */
  async prefetch(frame) {
    const start = Math.floor(frame / CHUNK_SIZE) * CHUNK_SIZE;
    if (frame - start >= CHUNK_SIZE - 75) {
      await this._loadChunk(start + CHUNK_SIZE);
    }
  }

  /** @param {number} start */
  async _loadChunk(start) {
    if (start >= this._frameCount) return;
    if (this._chunks.has(start)) {
      const chunk = this._chunks.get(start);
      this._chunks.delete(start);
      this._chunks.set(start, chunk);
      return chunk;
    }
    if (this._pending.has(start)) return this._pending.get(start);

    const request = this._downloadChunk(start);
    this._pending.set(start, request);
    try {
      return await request;
    } finally {
      this._pending.delete(start);
    }
  }

  /** @param {number} start */
  async _downloadChunk(start) {
    const count = Math.min(CHUNK_SIZE, this._frameCount - start);
    const frames = await this._client.frames(start, count);
    const chunk = new Map(frames.map((frame) => [frame.frame, frame]));
    this._chunks.set(start, chunk);
    while (this._chunks.size > MAX_CHUNKS) {
      this._chunks.delete(this._chunks.keys().next().value);
    }
    return chunk;
  }
}
