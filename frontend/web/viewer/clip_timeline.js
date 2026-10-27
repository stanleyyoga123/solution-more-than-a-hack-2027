/**
 * Map a source frame into the rendered clip, preserving its source offset.
 * @param {number} sourceFrame
 * @param {number} sourceFps
 * @param {import('./tracking_types.js').BirdseyeMetadata} clip
 * @returns {number | null}
 */
export function clipFrameAtSourceFrame(sourceFrame, sourceFps, clip) {
  const elapsed = (sourceFrame - clip.start_frame) / sourceFps;
  const clipFrame = Math.floor(elapsed * clip.fps + 0.00001);
  if (elapsed < 0 || clipFrame >= clip.frame_count) return null;
  return clipFrame;
}

/**
 * Convert a decoded footage timestamp back into the source tracking timeline.
 * @param {number} seconds
 * @param {number} sourceFps
 * @param {import('./tracking_types.js').BirdseyeMetadata} clip
 * @returns {number | null}
 */
export function sourceFrameAtClipTime(seconds, sourceFps, clip) {
  const clipFrame = Math.floor(seconds * clip.fps + 0.00001);
  if (seconds < 0 || clipFrame >= clip.frame_count) return null;
  const sourceOffset = Math.floor(clipFrame * sourceFps / clip.fps + 0.00001);
  return clip.start_frame + sourceOffset;
}

