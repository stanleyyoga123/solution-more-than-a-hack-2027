import { PREDICTION_COLOURS } from "./prediction_model.js";

/** Paint prediction intervals once and move the source-frame playhead separately. */
export class PredictionTimeline {
  /** @param {HTMLCanvasElement} canvas @param {number} frameCount */
  constructor(canvas, frameCount) {
    this._canvas = canvas;
    this._frameCount = frameCount;
    this._background = canvas.ownerDocument.createElement("canvas");
    this._background.width = canvas.width;
    this._background.height = canvas.height;
    /** @type {number|null} */
    this._frame = null;
    this.setSegments([]);
  }

  /** @param {import('./prediction_types.js').PredictionSegment[]} segments */
  setSegments(segments) {
    const context = this._background.getContext("2d");
    const { width, height } = this._canvas;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#141a13";
    context.fillRect(0, 0, width, height);
    const scale = width / this._frameCount;
    for (const segment of segments) {
      const start = Math.max(0, segment.start_frame * scale);
      const end = Math.min(width, (segment.end_frame + 1) * scale);
      if (end <= start) continue;
      context.fillStyle = PREDICTION_COLOURS[segment.label];
      context.globalAlpha = segment.label === "D" ? 0.65 : 0.85;
      context.fillRect(start, 5, end - start, height - 10);
    }
    context.globalAlpha = 1;
    this.showFrame(this._frame);
  }

  /** @param {number|null} frame */
  showFrame(frame) {
    this._frame = frame;
    const context = this._canvas.getContext("2d");
    const { width, height } = this._canvas;
    context.clearRect(0, 0, width, height);
    context.drawImage(this._background, 0, 0);
    if (frame === null) return;
    const x = Math.min(width - 1, Math.max(0, frame / this._frameCount * width));
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.lineWidth = 2;
    context.strokeStyle = "#ffffff";
    context.stroke();
  }

  /** @param {MouseEvent} event */
  frameAt(event) {
    const bounds = this._canvas.getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    return Math.min(this._frameCount - 1, Math.floor(fraction * this._frameCount));
  }
}
