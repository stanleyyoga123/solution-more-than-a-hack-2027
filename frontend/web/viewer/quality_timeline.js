import { qualityEventColour } from "./quality_model.js";

/** Cache report intervals separately from the moving source-frame playhead. */
export class QualityTimeline {
  /** @param {HTMLCanvasElement} canvas @param {number} frameCount */
  constructor(canvas, frameCount) {
    this._canvas = canvas;
    this._context = canvas.getContext("2d");
    this._lastFrame = frameCount - 1;
    this._background = canvas.ownerDocument.createElement("canvas");
    this._background.width = canvas.width;
    this._background.height = canvas.height;
    this._frame = 0;
    this.setEvents([], null);
  }

  /** @param {import('./quality_types.js').QualityEvent[]} events @param {string|null} selectedId */
  setEvents(events, selectedId) {
    const context = this._background.getContext("2d");
    const { width, height } = this._canvas;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#121811";
    context.fillRect(0, 0, width, height);
    context.fillStyle = "#263023";
    context.fillRect(0, height / 2 - 1, width, 2);
    for (const event of events) {
      this._drawInterval(context, event, event.id === selectedId);
    }
    const selected = events.find((event) => event.id === selectedId);
    if (selected) this._drawInterval(context, selected, true);
    this.showFrame(this._frame);
  }

  /** @param {number} frame */
  showFrame(frame) {
    this._frame = frame;
    const context = this._context;
    const { width, height } = this._canvas;
    context.clearRect(0, 0, width, height);
    context.drawImage(this._background, 0, 0);
    const fraction = frame / Math.max(1, this._lastFrame);
    const x = Math.min(width - 1, Math.max(0, fraction * width));
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.lineWidth = 2;
    context.strokeStyle = "#eef1eb";
    context.stroke();
  }

  /** @param {MouseEvent} event */
  pointAt(event) {
    const bounds = this._canvas.getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    return {
      frame: Math.round(fraction * this._lastFrame),
      lane: event.clientY - bounds.top < bounds.height / 2 ? "motion" : "gap",
    };
  }

  /**
   * @param {CanvasRenderingContext2D} context
   * @param {import('./quality_types.js').QualityEvent} event
   * @param {boolean} selected
   */
  _drawInterval(context, event, selected) {
    const { width, height } = this._canvas;
    const scale = width / Math.max(1, this._lastFrame);
    const x = Math.min(
      width - 2, Math.max(0, event.start_frame * scale),
    );
    const end = Math.min(width, (event.end_frame + 1) * scale);
    const intervalWidth = Math.max(2, end - x);
    const y = event.kind === "motion" ? 8 : height / 2 + 8;
    context.fillStyle = qualityEventColour(event);
    context.globalAlpha = selected ? 1 : 0.5;
    context.fillRect(x, y, intervalWidth, height / 2 - 16);
    context.globalAlpha = 1;
    if (selected) {
      context.strokeStyle = "#ffffff";
      context.lineWidth = 2;
      context.strokeRect(x, y, intervalWidth, height / 2 - 16);
    }
  }
}
