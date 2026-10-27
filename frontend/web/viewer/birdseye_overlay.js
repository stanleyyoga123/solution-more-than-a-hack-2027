/** Load tracking for the decoded footage frame and discard superseded requests. */
export class BirdseyeOverlay {
  /**
   * @param {import('./birdseye_overlay_renderer.js').BirdseyeOverlayRenderer} renderer
   * @param {import('./frame_cache.js').FrameCache} cache
   */
  constructor(renderer, cache) {
    this._renderer = renderer;
    this._cache = cache;
    /** @type {number | null} */
    this._frame = null;
    this._labels = true;
    this._visible = true;
    this._generation = 0;
  }

  /** @param {number | null} frame */
  showFrame(frame) {
    this._frame = frame;
    this._refresh();
  }

  /** @param {boolean} enabled */
  setLabels(enabled) {
    this._labels = enabled;
    this._refresh();
  }

  /** @param {boolean} enabled */
  setVisible(enabled) {
    this._visible = enabled;
    this._refresh();
  }

  async _refresh() {
    const generation = ++this._generation;
    this._renderer.hide();
    if (this._frame === null || !this._visible) return;
    const frame = this._frame;
    const cached = this._cache.peek(frame);
    if (cached) {
      this._renderer.render(cached.normalized, this._labels);
      return;
    }
    let positions;
    try {
      positions = await this._cache.get(frame);
    } catch {
      // The main tracking view reports loading failures; never retain stale dots.
      if (generation === this._generation) this._renderer.hide();
      return;
    }
    if (generation !== this._generation) return;
    this._renderer.render(positions.normalized, this._labels);
  }
}
