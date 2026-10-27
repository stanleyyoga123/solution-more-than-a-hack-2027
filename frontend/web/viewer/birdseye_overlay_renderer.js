import { drawEntity } from "./entity_markers.js";

const PIXELS_PER_METRE = 12;

/**
 * Map pitch fractions onto the same physical scale as pipeline 04.
 * @param {number} x
 * @param {number} y
 * @param {{length: number, width: number}} pitch
 */
export function birdseyePosition(x, y, pitch) {
  return {
    x: x * pitch.length * PIXELS_PER_METRE,
    y: y * pitch.width * PIXELS_PER_METRE,
  };
}

/** Draw tracking directly over the footage without minimap margins or clamping. */
export class BirdseyeOverlayRenderer {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {{length: number, width: number}} pitch
   * @param {{width: number, height: number} | null} footage
   * @param {Map<string, string>} colours
   */
  constructor(canvas, pitch, footage, colours) {
    this._canvas = canvas;
    this._context = canvas.getContext("2d");
    this._pitch = pitch;
    this._colours = colours;
    canvas.width = footage === null ? 0 : footage.width;
    canvas.height = footage === null ? 0 : footage.height;
    this.hide();
  }

  hide() {
    this._canvas.hidden = true;
    this._context.clearRect(0, 0, this._canvas.width, this._canvas.height);
  }

  /**
   * @param {import('./tracking_types.js').Observation[]} positions
   * @param {boolean} labels
   */
  render(positions, labels) {
    this.hide();
    this._context.save();
    this._context.beginPath();
    this._context.rect(0, 0, this._canvas.width, this._canvas.height);
    this._context.clip();
    for (const entity of positions) {
      const point = birdseyePosition(entity.pos_x, entity.pos_y, this._pitch);
      drawEntity(this._context, entity, point.x, point.y, this._colours, labels, 9);
    }
    this._context.restore();
    this._canvas.hidden = false;
  }
}
