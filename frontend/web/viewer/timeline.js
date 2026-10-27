/** Convert a decoded video timestamp to its zero-based source frame. */
export function frameAtTime(seconds, fps, frameCount) {
  const frame = Math.floor(seconds * fps + 0.00001);
  return Math.max(0, Math.min(frameCount - 1, frame));
}

/** Seek inside a frame to avoid landing on the preceding timestamp boundary. */
export function frameSeekTime(frame, fps) {
  return (frame + 0.25) / fps;
}

/** Display source time; this clock is not the match clock. */
export function formatTime(seconds, milliseconds = false) {
  const totalMilliseconds = Math.round(seconds * 1000);
  const hours = Math.floor(totalMilliseconds / 3600000);
  const minutes = Math.floor(totalMilliseconds / 60000) % 60;
  const wholeSeconds = Math.floor(totalMilliseconds / 1000) % 60;
  const clock = [hours, minutes, wholeSeconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
  if (!milliseconds) return clock;
  return `${clock}.${String(totalMilliseconds % 1000).padStart(3, "0")}`;
}
