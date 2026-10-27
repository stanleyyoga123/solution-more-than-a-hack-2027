import { PREDICTION_COLOURS, predictionDescription } from "./prediction_model.js";
import { formatTime } from "./timeline.js";

/** Present submitted possession labels without changing video or tracking data. */
export class PredictionView {
  /** @param {HTMLElement} root @param {HTMLElement} overlay
   * @param {import('./tracking_types.js').RecordingMetadata} metadata
   */
  constructor(root, overlay, metadata) {
    this._overlay = overlay;
    this._metadata = metadata;
    this.controls = {
      overlay: root.querySelector("#show-prediction-overlay"),
      previous: root.querySelector("#prediction-previous"),
      next: root.querySelector("#prediction-next"),
      timeline: root.querySelector("#prediction-timeline"),
    };
    this._label = root.querySelector("#prediction-current");
    this._interval = root.querySelector("#prediction-interval");
    this._status = root.querySelector("#prediction-status");
    const [home, away] = Object.values(metadata.teams);
    root.querySelector("#prediction-home-name").textContent = `${home} (H)`;
    root.querySelector("#prediction-away-name").textContent = `${away} (A)`;
  }

  /** @param {import('./prediction_types.js').PredictionPayload} payload */
  showPayload(payload) {
    if (!payload.available) {
      this.showUnavailable("No prediction file loaded. Add output/prediction.csv or choose --predictions when starting the viewer.");
      return;
    }
    this._status.dataset.state = "ready";
    this._status.textContent = (
      `${payload.filename} · ${payload.row_count.toLocaleString()} labelled frames · `
      + `${payload.segments.length.toLocaleString()} intervals`
    );
    this.controls.overlay.disabled = false;
    this._label.textContent = "Waiting for a video frame…";
  }

  /** @param {string} message @param {boolean} [error] */
  showUnavailable(message, error = false) {
    this._status.textContent = message;
    this._status.dataset.state = error ? "error" : "unavailable";
    this._label.textContent = "Predictions unavailable";
    this._interval.textContent = "";
    this._label.style.color = "";
    this.controls.overlay.disabled = true;
    this.clearOverlay();
  }

  /** @param {import('./prediction_types.js').PredictionSegment|null} segment
   * @param {number} frame @param {boolean} overlayVisible
   */
  showFrame(segment, frame, overlayVisible) {
    const text = segment === null
      ? "No prediction for this frame"
      : predictionDescription(segment.label, this._metadata.teams);
    const colour = segment === null ? "#a6afa0" : PREDICTION_COLOURS[segment.label];
    this._label.textContent = text;
    this._label.style.color = colour;
    this._interval.textContent = segment === null
      ? `Frame ${frame.toLocaleString()} is not present in the prediction CSV.`
      : this._intervalDescription(segment);
    this._overlay.textContent = `Prediction · ${text}`;
    this._overlay.style.setProperty("--prediction-colour", colour);
    this._overlay.hidden = !overlayVisible;
  }

  showWaiting() {
    this._label.textContent = "Waiting for a video frame…";
    this._label.style.color = "";
    this._interval.textContent = "";
    this.clearOverlay();
  }

  clearOverlay() {
    this._overlay.hidden = true;
  }

  /** @param {boolean} previous @param {boolean} next @param {boolean} ready */
  setNavigation(previous, next, ready) {
    this.controls.previous.disabled = !ready || !previous;
    this.controls.next.disabled = !ready || !next;
    this.controls.timeline.dataset.ready = String(ready);
  }

  /** @param {import('./prediction_types.js').PredictionSegment} segment */
  _intervalDescription(segment) {
    const fps = this._metadata.fps;
    const duration = (segment.end_frame - segment.start_frame + 1) / fps;
    return (
      `Frames ${segment.start_frame.toLocaleString()}–${segment.end_frame.toLocaleString()}`
      + ` · ${formatTime(segment.start_frame / fps, true)}`
      + `–${formatTime((segment.end_frame + 1) / fps, true)}`
      + ` · ${duration.toFixed(2)} s`
    );
  }
}
