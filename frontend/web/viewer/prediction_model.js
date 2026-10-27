import { TEAM_COLOURS } from "./entity_markers.js";

export const PREDICTION_COLOURS = {
  H: TEAM_COLOURS[0],
  A: TEAM_COLOURS[1],
  D: "#c2c7be",
  X: "#b4a1d8",
};

/** Find the first segment beginning strictly after a source frame.
 * @param {import('./prediction_types.js').PredictionSegment[]} segments
 * @param {number} frame
 */
function upperBound(segments, frame) {
  let low = 0;
  let high = segments.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (segments[middle].start_frame <= frame) low = middle + 1;
    else high = middle;
  }
  return low;
}

/** Return only an explicitly supplied inclusive interval; never fill CSV gaps.
 * @param {import('./prediction_types.js').PredictionSegment[]} segments
 * @param {number} frame
 * @returns {import('./prediction_types.js').PredictionSegment|null}
 */
export function predictionAt(segments, frame) {
  const candidate = segments[upperBound(segments, frame) - 1];
  return candidate && frame <= candidate.end_frame ? candidate : null;
}

/** Navigate segment starts without wrapping or inventing a label in a gap.
 * @param {import('./prediction_types.js').PredictionSegment[]} segments
 * @param {number} frame
 * @param {number} direction
 * @returns {import('./prediction_types.js').PredictionSegment|null}
 */
export function adjacentPrediction(segments, frame, direction) {
  if (direction > 0) return segments[upperBound(segments, frame)] ?? null;
  return segments[upperBound(segments, frame - 1) - 1] ?? null;
}

/** @param {import('./prediction_types.js').PredictionLabel} label
 * @param {Record<string, string>} teams
 */
export function predictionDescription(label, teams) {
  const [home, away] = Object.values(teams);
  if (label === "H") return `${home} possession (H)`;
  if (label === "A") return `${away} possession (A)`;
  if (label === "D") return "Dead ball (D)";
  return "No answer (X)";
}
