/** Normalize report rows into a single chronological review list.
 * @param {import('./quality_types.js').QualityPayload} payload
 * @returns {import('./quality_types.js').QualityEvent[]}
 */
export function qualityEvents(payload) {
  return [
    ...payload.episodes.map((episode) => ({ ...episode, kind: "motion" })),
    ...payload.gaps.map((gap) => ({ ...gap, kind: "gap" })),
  ].sort((left, right) => (
    left.start_frame - right.start_frame
    || left.entity_id.localeCompare(right.entity_id)
    || left.id.localeCompare(right.id)
  ));
}

/**
 * @param {import('./quality_types.js').QualityEvent[]} events
 * @param {string} category
 * @param {string} entityId
 */
export function filterQualityEvents(events, category, entityId) {
  return events.filter((event) => {
    const entityMatches = entityId === "all" || event.entity_id === entityId;
    const categoryMatches = category === "all"
      || (category === "motion" && event.kind === "motion")
      || (event.kind === "gap" && event.status === category);
    return entityMatches && categoryMatches;
  });
}

/** @param {import('./quality_types.js').QualityEvent} event */
export function eventSeekFrame(event) {
  if (event.kind === "motion") return event.peak_frame;
  return event.left_frame === null ? event.start_frame : event.left_frame;
}

/** Navigate filtered chronological events without wrapping at either boundary.
 * @param {import('./quality_types.js').QualityEvent[]} events
 * @param {string|null} selectedId
 * @param {number} currentFrame
 * @param {number} direction
 * @returns {import('./quality_types.js').QualityEvent|null}
 */
export function adjacentQualityEvent(events, selectedId, currentFrame, direction) {
  const selected = events.findIndex((event) => event.id === selectedId);
  if (selected >= 0) return events[selected + direction] ?? null;
  const candidates = events.filter((event) => direction > 0
    ? event.start_frame > currentFrame
    : event.start_frame < currentFrame);
  return direction > 0 ? candidates[0] ?? null : candidates.at(-1) ?? null;
}

/** Find the nearest inclusive interval in the clicked lane; first event wins ties.
 * @param {import('./quality_types.js').QualityEvent[]} events
 * @param {number} frame
 * @param {'motion'|'gap'} lane
 * @returns {import('./quality_types.js').QualityEvent|null}
 */
export function nearestQualityEvent(events, frame, lane) {
  let nearest = null;
  let shortest = Infinity;
  for (const event of events) {
    if (event.kind !== lane) continue;
    const distance = Math.max(event.start_frame - frame, frame - event.end_frame, 0);
    if (distance < shortest) {
      nearest = event;
      shortest = distance;
    }
  }
  return nearest;
}

/** @param {import('./quality_types.js').QualityEvent} event */
export function qualityEventColour(event) {
  if (event.kind === "motion") return "#ffba68";
  if (event.status === "implausible") return "#ff817b";
  if (event.status === "plausible") return "#a6d88c";
  return "#a3a7ce";
}
