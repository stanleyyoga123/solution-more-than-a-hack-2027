import { adjacentPrediction, predictionAt } from "./prediction_model.js";

/** Follow the displayed source frame independently of tracking-position requests. */
export class PredictionController {
  /** @param {import('./tracking_client.js').TrackingClient} client
   * @param {import('./prediction_view.js').PredictionView} view
   * @param {import('./prediction_timeline.js').PredictionTimeline} timeline
   * @param {(frame:number)=>void} seek
   */
  constructor(client, view, timeline, seek) {
    this._client = client;
    this._view = view;
    this._timeline = timeline;
    this._seek = seek;
    /** @type {import('./prediction_types.js').PredictionSegment[]} */
    this._segments = [];
    this._available = false;
    this._ready = false;
    /** @type {number|null} */
    this._frame = null;
  }

  async start() {
    this._bindControls();
    try {
      const payload = await this._client.predictions();
      this._available = payload.available;
      this._segments = payload.segments;
      this._view.showPayload(payload);
      this._timeline.setSegments(this._segments);
      this._render();
    } catch (error) {
      this._available = false;
      this._view.showUnavailable(`Predictions could not load: ${error.message}`, true);
      this._showNavigation();
    }
  }

  /** @param {boolean} ready */
  setReady(ready) {
    this._ready = ready;
    if (!ready) this.suspend();
    this._render();
  }

  /** Called only for a displayed video frame. @param {number} frame */
  showFrame(frame) {
    this._frame = frame;
    this._timeline.showFrame(frame);
    this._render();
  }

  /** Clear the old prediction while the video's displayed frame is uncertain. */
  suspend() {
    this._frame = null;
    this._timeline.showFrame(null);
    if (this._available) this._view.showWaiting();
    else this._view.clearOverlay();
    this._showNavigation();
  }

  _bindControls() {
    const controls = this._view.controls;
    controls.previous.addEventListener("click", () => this._navigate(-1));
    controls.next.addEventListener("click", () => this._navigate(1));
    controls.overlay.addEventListener("change", () => this._render());
    controls.timeline.addEventListener("click", (event) => {
      if (this._ready && this._available) this._seek(this._timeline.frameAt(event));
    });
  }

  /** @param {number} direction */
  _navigate(direction) {
    if (!this._ready || !this._available || this._frame === null) return;
    const segment = adjacentPrediction(this._segments, this._frame, direction);
    if (segment !== null) this._seek(segment.start_frame);
  }

  _render() {
    if (this._available && this._ready && this._frame !== null) {
      this._view.showFrame(
        predictionAt(this._segments, this._frame),
        this._frame,
        this._view.controls.overlay.checked,
      );
    } else {
      this._view.clearOverlay();
    }
    this._showNavigation();
  }

  _showNavigation() {
    const ready = this._ready && this._available && this._frame !== null;
    const previous = ready
      && adjacentPrediction(this._segments, this._frame, -1) !== null;
    const next = ready
      && adjacentPrediction(this._segments, this._frame, 1) !== null;
    this._view.setNavigation(previous, next, ready);
  }
}
