export const TEAM_COLOURS = ["#64afff", "#fa7976"];
export const BALL_COLOUR = "#f9e572";

/** @param {Record<string, string>} teams */
export function teamColours(teams) {
  return new Map(
    Object.keys(teams).map((id, index) => [id, TEAM_COLOURS[index % TEAM_COLOURS.length]]),
  );
}

/**
 * @param {CanvasRenderingContext2D} context
 * @param {import('./tracking_types.js').Observation} entity
 * @param {number} x
 * @param {number} y
 * @param {Map<string, string>} colours
 * @param {boolean} labels
 * @param {number} radius
 */
export function drawEntity(context, entity, x, y, colours, labels, radius) {
  const isBall = entity.entity_type === "ball";
  context.beginPath();
  context.arc(x, y, isBall ? radius * 0.8 : radius, 0, Math.PI * 2);
  context.fillStyle = isBall ? BALL_COLOUR : colours.get(entity.team_id);
  context.fill();
  context.strokeStyle = "#111a11";
  context.lineWidth = Math.max(1.5, radius / 4);
  context.stroke();
  if (!labels) return;

  const label = isBall ? "Ball" : entity.entity_id.replace(/^player_/, "");
  const fontSize = radius * 1.75;
  context.font = `600 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
  context.textAlign = "left";
  context.textBaseline = "middle";
  const textX = x + radius + 4;
  const textY = y - radius - 2;
  const textWidth = context.measureText(label).width;
  context.fillStyle = "#0c140ce0";
  context.fillRect(textX - 3, textY - fontSize * 0.65, textWidth + 6, fontSize * 1.3);
  context.fillStyle = "#ffffff";
  context.fillText(label, textX, textY);
}
