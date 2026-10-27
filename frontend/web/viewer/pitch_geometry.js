/** Fit the physical pitch and a five-metre margin without distorting its aspect. */
export function pitchGeometry(width, height, length, pitchWidth) {
  const margin = 5;
  const scale = Math.min(
    width / (length + margin * 2),
    height / (pitchWidth + margin * 2),
  );
  return {
    x: (width - length * scale) / 2,
    y: (height - pitchWidth * scale) / 2,
    width: length * scale,
    height: pitchWidth * scale,
    scale,
  };
}

/** Normalized x goes right and y goes down; off-pitch values stay off-pitch. */
export function pitchPosition(x, y, geometry) {
  return {
    x: geometry.x + x * geometry.width,
    y: geometry.y + y * geometry.height,
  };
}
