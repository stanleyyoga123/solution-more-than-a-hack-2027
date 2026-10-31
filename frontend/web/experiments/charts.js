import {
  finite,
  metricText,
  runLabel,
  scatterPoints,
  fragmentationRows,
} from "./model.js";

const SVG = "http://www.w3.org/2000/svg";
function svgNode(document, tag, attrs = {}, text) {
  const node = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs))
    node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}
function chart(container, width, height, label) {
  container.replaceChildren();
  const document = container.ownerDocument;
  const svg = svgNode(document, "svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "group",
    "aria-label": label,
  });
  container.append(svg);
  const add = (tag, attrs, text) => {
    const node = svgNode(document, tag, attrs, text);
    svg.append(node);
    return node;
  };
  return { document, svg, add };
}
function empty(container, message) {
  container.replaceChildren();
  const p = container.ownerDocument.createElement("p");
  p.className = "chart-empty";
  p.textContent = message;
  container.append(p);
}
function interactive(node, document, description, onSelect, run) {
  node.setAttribute("tabindex", "0");
  node.setAttribute("role", "button");
  node.setAttribute("aria-label", description);
  node.append(svgNode(document, "title", {}, description));
  node.addEventListener("click", () => onSelect(run));
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(run);
    }
  });
}
function label(add, run, y) {
  add(
    "text",
    { x: 12, y, class: "chart-label" },
    run.pipeline ?? "Unknown pipeline",
  );
}

export function renderScores(container, runs, onSelect = () => {}) {
  if (
    !runs.some(
      (run) =>
        finite(run.metrics.spell_f1_mean) || finite(run.metrics.macro_f1),
    )
  ) {
    empty(container, "No official scores available for this selection.");
    return;
  }
  const { add, document } = chart(
    container,
    640,
    Math.max(180, runs.length * 82 + 65),
    "Official evaluation scores, from zero to one. Each run has spellF1 and macroF1 bars.",
  );
  for (let tick = 0; tick <= 4; tick++) {
    const x = 155 + tick * 105;
    runs.forEach((_, index) => {
      add("line", {
        x1: x,
        x2: x,
        y1: index * 82 + 23,
        y2: index * 82 + 70,
        class: "chart-grid",
      });
    });
    add(
      "text",
      {
        x,
        y: runs.length * 82 + 45,
        "text-anchor": "middle",
        class: "chart-tick",
      },
      metricText(tick / 4, 2),
    );
  }
  runs.forEach((run, index) => {
    const y = 35 + index * 82;
    label(add, run, y - 18);
    [
      ["spell_f1_mean", "spellF1", "metric-primary"],
      ["macro_f1", "macroF1", "metric-secondary"],
    ].forEach(([key, name, colour], series) => {
      const value = run.metrics[key],
        rowY = y + series * 25;
      if (finite(value)) {
        const bar = add("rect", {
          x: 155,
          y: rowY - 12,
          width: Math.max(2, value * 420),
          height: 16,
          class: colour,
        });
        interactive(
          bar,
          document,
          `${runLabel(run)}. ${name}: ${metricText(value)}`,
          onSelect,
          run,
        );
      }
      add(
        "text",
        { x: 632, y: rowY + 1, "text-anchor": "end", class: "chart-value" },
        metricText(value),
      );
    });
  });
}

export function renderScatter(container, runs, onSelect = () => {}) {
  const points = scatterPoints(runs);
  if (!points.length) {
    empty(
      container,
      "No runs have both dead-ball F1 and spellF1 in this selection.",
    );
    return;
  }
  const { add, document } = chart(
    container,
    600,
    320,
    "Dead-ball F1 on the horizontal axis and spellF1 on the vertical axis. Both range from zero to one.",
  );
  for (let tick = 0; tick <= 4; tick++) {
    const value = tick / 4,
      x = 65 + value * 470,
      y = 260 - value * 220;
    add("line", { x1: x, x2: x, y1: 40, y2: 260, class: "chart-grid" });
    add("line", { x1: 65, x2: 535, y1: y, y2: y, class: "chart-grid" });
    add(
      "text",
      { x, y: 282, "text-anchor": "middle", class: "chart-tick" },
      metricText(value, 2),
    );
    add(
      "text",
      { x: 52, y: y + 4, "text-anchor": "end", class: "chart-tick" },
      metricText(value, 2),
    );
  }
  add("text", { x: 65, y: 20, class: "chart-axis" }, "spellF1");
  add(
    "text",
    { x: 300, y: 312, "text-anchor": "middle", class: "chart-axis" },
    "Dead-ball F1",
  );
  const annotations = [];
  points.forEach(({ run, x, y }) => {
    const cx = 65 + x * 470,
      cy = 260 - y * 220;
    const point = add("circle", { cx, cy, r: 7, class: "scatter-point" });
    interactive(
      point,
      document,
      `${runLabel(run)}. Dead-ball F1: ${metricText(x)}. spellF1: ${metricText(y)}`,
      onSelect,
      run,
    );
    const name = run.pipeline ?? "Unknown pipeline";
    const anchor = x > 0.5 ? "end" : "start";
    const textX = cx + (anchor === "end" ? -12 : 12);
    const width = name.length * 7;
    const left = anchor === "end" ? textX - width : textX;
    let textY = cy - 12;
    while (
      annotations.some(
        (label) =>
          left < label.right &&
          left + width > label.left &&
          Math.abs(textY - label.y) < 18,
      )
    ) {
      textY -= 18;
    }
    annotations.push({ left, right: left + width, y: textY });
    add("line", {
      x1: cx,
      y1: cy - 8,
      x2: textX,
      y2: textY + 3,
      class: "chart-grid",
    });
    add(
      "text",
      { x: textX, y: textY, "text-anchor": anchor, class: "chart-label" },
      name,
    );
  });
}

export function renderFragmentation(container, runs, onSelect = () => {}) {
  const rows = fragmentationRows(runs);
  if (
    !rows.some(
      (row) => finite(row.predicted) || finite(row.truth) || finite(row.ratio),
    )
  ) {
    empty(
      container,
      "Possession counts and fragmentation are unavailable for this selection.",
    );
    return;
  }
  const maximum = Math.max(
    1,
    ...rows.flatMap((row) => [row.predicted, row.truth].filter(finite)),
  );
  const { add, document } = chart(
    container,
    740,
    Math.max(190, rows.length * 86 + 80),
    "Evaluated-window possession counts and official fragmentation segment ratio. Full-submission counts are excluded.",
  );
  add(
    "text",
    { x: 156, y: 20, class: "chart-axis" },
    "Possessions in evaluated window",
  );
  add(
    "text",
    { x: 650, y: 20, "text-anchor": "middle", class: "chart-axis" },
    "Fragmentation",
  );
  rows.forEach(({ run, predicted, truth, ratio }, index) => {
    const y = 54 + index * 86;
    label(add, run, y - 18);
    [
      [predicted, "Predicted", "metric-primary"],
      [truth, "Ground truth", "metric-secondary"],
    ].forEach(([value, name, colour], series) => {
      const rowY = y + series * 24;
      if (finite(value)) {
        const bar = add("rect", {
          x: 155,
          y: rowY - 12,
          width: Math.max(2, (value / maximum) * 340),
          height: 16,
          class: colour,
        });
        interactive(
          bar,
          document,
          `${runLabel(run)}. ${name}: ${metricText(value, 0)} possessions in evaluated window. Fragmentation: ${metricText(ratio, 2)}`,
          onSelect,
          run,
        );
      }
      add(
        "text",
        { x: 535, y: rowY + 1, "text-anchor": "end", class: "chart-value" },
        metricText(value, 0),
      );
    });
    add(
      "text",
      { x: 650, y: y + 3, "text-anchor": "middle", class: "chart-ratio" },
      finite(ratio) ? `${metricText(ratio, 2)}×` : "—",
    );
    add(
      "text",
      { x: 650, y: y + 25, "text-anchor": "middle", class: "chart-tick" },
      !finite(ratio)
        ? "Unavailable"
        : ratio > 1
          ? "More segments"
          : ratio < 1
            ? "Fewer segments"
            : "Same segment count",
    );
  });
  const bottom = rows.length * 86 + 55;
  add("text", { x: 155, y: bottom, class: "chart-tick" }, "0");
  add(
    "text",
    { x: 495, y: bottom, "text-anchor": "end", class: "chart-tick" },
    metricText(maximum, 0),
  );
}
