/**
 * @typedef {'H'|'A'|'D'|'X'} PredictionLabel
 *
 * @typedef {Object} PredictionSegment
 * @property {number} start_frame Inclusive first source frame.
 * @property {number} end_frame Inclusive last source frame.
 * @property {PredictionLabel} label
 *
 * @typedef {Object} PredictionPayload
 * @property {boolean} available
 * @property {string|null} filename
 * @property {number} row_count
 * @property {PredictionSegment[]} segments
 * @property {Record<PredictionLabel, number>} counts
 */
export {};
