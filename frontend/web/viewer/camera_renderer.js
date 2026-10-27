import { drawEntity } from "./entity_markers.js";

/** Pixel coordinates share the original video's native canvas dimensions. */
export class CameraRenderer {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {number} width
   * @param {number} height
   * @param {Map<string, string>} colours
   */
  constructor(canvas, width, height, colours) {
    this._canvas = canvas;
    this._canvas.width = width;
    this._canvas.height = height;
    this._context = canvas.getContext("2d");
    this._colours = colours;
    this._highlightedEntity = null;
  }

  /** @param {string|null} entityId */
  setHighlightedEntity(entityId) {
    this._highlightedEntity = entityId;
  }

  clear() {
    this._context.clearRect(0, 0, this._canvas.width, this._canvas.height);
  }

  /**
   * @param {import('./tracking_types.js').Observation[]} positions
   * @param {boolean} labels
   * @param {boolean} overlay
   * @returns {number} Number of players inside the video image.
   */
  render(positions, labels, overlay) {
    this.clear();
    const visible = positions.filter((entity) => (
      entity.pos_x >= 0 && entity.pos_x < this._canvas.width
      && entity.pos_y >= 0 && entity.pos_y < this._canvas.height
    ));
    if (overlay) {
      for (const entity of visible) {
        drawEntity(
          this._context,
          entity,
          entity.pos_x,
          entity.pos_y,
          this._colours,
          labels,
          15,
          entity.entity_id === this._highlightedEntity,
        );
      }
    }
    return visible.filter((entity) => entity.entity_type === "player").length;
  }
}
