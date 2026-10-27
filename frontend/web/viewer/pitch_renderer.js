import { pitchGeometry, pitchPosition } from "./pitch_geometry.js";
import { drawEntity } from "./entity_markers.js";

/** Draw the physical pitch and current normalized positions. */
export class PitchRenderer {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {{length: number, width: number}} dimensions
   * @param {Map<string, string>} colours
   */
  constructor(canvas, dimensions, colours) {
    this._canvas = canvas;
    this._context = canvas.getContext("2d");
    this._dimensions = dimensions;
    this._colours = colours;
    this._geometry = pitchGeometry(
      canvas.width,
      canvas.height,
      dimensions.length,
      dimensions.width,
    );
    this._background = document.createElement("canvas");
    this._background.width = canvas.width;
    this._background.height = canvas.height;
    this._drawPitch(this._background.getContext("2d"));
  }

  clear() {
    this._context.drawImage(this._background, 0, 0);
  }

  /**
   * @param {import('./tracking_types.js').Observation[]} positions
   * @param {boolean} labels
   */
  render(positions, labels) {
    this.clear();
    this._context.save();
    this._context.beginPath();
    this._context.rect(0, 0, this._canvas.width, this._canvas.height);
    this._context.clip();
    for (const entity of positions) {
      const point = pitchPosition(entity.pos_x, entity.pos_y, this._geometry);
      drawEntity(this._context, entity, point.x, point.y, this._colours, labels, 10);
    }
    this._context.restore();
  }

  /** @param {CanvasRenderingContext2D} context */
  _drawPitch(context) {
    const geometry = this._geometry;
    const { length, width } = this._dimensions;
    context.fillStyle = "#142315";
    context.fillRect(0, 0, this._canvas.width, this._canvas.height);
    for (let stripe = 0; stripe < 10; stripe += 1) {
      context.fillStyle = stripe % 2 === 0 ? "#243c26" : "#29422b";
      context.fillRect(
        geometry.x + stripe * geometry.width / 10,
        geometry.y,
        geometry.width / 10,
        geometry.height,
      );
    }

    context.save();
    context.translate(geometry.x, geometry.y);
    context.scale(geometry.scale, geometry.scale);
    context.strokeStyle = "#b9cab0a8";
    context.fillStyle = "#c7d7be";
    context.lineWidth = 0.22;
    context.strokeRect(0, 0, length, width);
    context.beginPath();
    context.moveTo(length / 2, 0);
    context.lineTo(length / 2, width);
    context.stroke();
    this._circle(context, length / 2, width / 2, 9.15);
    this._spot(context, length / 2, width / 2);

    for (const side of [0, 1]) {
      const goalX = side === 0 ? 0 : length;
      const direction = side === 0 ? 1 : -1;
      context.strokeRect(goalX, (width - 40.32) / 2, direction * 16.5, 40.32);
      context.strokeRect(goalX, (width - 18.32) / 2, direction * 5.5, 18.32);
      context.strokeRect(goalX, (width - 7.32) / 2, -direction * 2, 7.32);
      this._spot(context, goalX + direction * 11, width / 2);

      // Only the part of the penalty arc outside the penalty area is visible.
      context.save();
      context.beginPath();
      const arcX = side === 0 ? 16.5 : length - 30;
      context.rect(arcX, 0, 13.5, width);
      context.clip();
      this._circle(context, goalX + direction * 11, width / 2, 9.15);
      context.restore();
    }
    context.restore();
  }

  /**
   * @param {CanvasRenderingContext2D} context
   * @param {number} x
   * @param {number} y
   * @param {number} radius
   */
  _circle(context, x, y, radius) {
    context.beginPath();
    context.arc(x, y, radius, 0, Math.PI * 2);
    context.stroke();
  }

  /** @param {CanvasRenderingContext2D} context @param {number} x @param {number} y */
  _spot(context, x, y) {
    context.beginPath();
    context.arc(x, y, 0.3, 0, Math.PI * 2);
    context.fill();
  }
}
