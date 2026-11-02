/** Presentation only: coordinates use the supplied report values unchanged. */
import { TEAM_COLOURS } from './viewer/entity_markers.js';

export const states = {
  true: ['Position recorded', 'var(--accent)'], false: ['Missing', 'var(--muted)'],
  H: ['Home possession (H)', TEAM_COLOURS[0]], A: ['Away possession (A)', TEAM_COLOURS[1]],
  D: ['Play stopped (D)', 'var(--muted)'], X: ['No prediction (X)', 'currentColor'],
};
/** The export retains one duration per gap, including repeated durations. */
export const GAP_BIN_COUNT = 30;

export function gapHistogram(points) {
  if (!points.length) return [];
  const maximum = Math.max(...points.map(point => point.seconds));
  const width = (maximum || 1) / GAP_BIN_COUNT;
  const bins = Array.from({length: GAP_BIN_COUNT}, (_, index) => ({
    start: index * width, stop: (index + 1) * width, count: 0,
  }));
  for (const point of points) {
    const index = Math.min(GAP_BIN_COUNT - 1, Math.floor(point.seconds / width));
    bins[index].count++;
  }
  return bins;
}
export function chart(container, label, height, width = 640) {
  const document = container.ownerDocument;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('role', 'group');
  svg.setAttribute('aria-label', label);
  container.append(svg);
  const add = (tag, attrs, text) => {
    const el = document.createElementNS(svg.namespaceURI, tag);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
    if (text !== undefined) el.textContent = text;
    svg.append(el);
    return el;
  };
  return { svg, add };
}
export function inspect(svg, marks, descriptions, output) {
  if (!marks.length) return;
  let selected = 0;
  const select = index => {
    selected = Math.max(0, Math.min(index, marks.length - 1));
    marks.forEach((mark, i) => mark.setAttribute('data-inspected', i === selected));
    output.textContent = descriptions[selected];
    svg.setAttribute('aria-label', `${descriptions[selected]} Use Left and Right arrows to inspect values, Home or End for the first or last.`);
  };
  svg.setAttribute('tabindex', '0');
  marks.forEach((mark, i) => {
    const title = svg.ownerDocument.createElementNS(svg.namespaceURI, 'title');
    title.textContent = descriptions[i]; mark.append(title);
    mark.addEventListener('pointerenter', () => select(i));
    mark.addEventListener('click', () => select(i));
  });
  svg.addEventListener('keydown', event => {
    const next = {ArrowRight: selected + 1, ArrowLeft: selected - 1, Home: 0, End: marks.length - 1}[event.key];
    if (next !== undefined) {
      event.preventDefault(); select(next);
      marks[selected].scrollIntoView?.({block: "nearest", inline: "nearest"});
    }
  });
  svg.addEventListener('focus', () => select(selected));
  select(0);
}
export function renderTimeline(container, intervals, count, fps, output) {
  const width = Math.max(640, container.clientWidth || 640);
  const plotWidth = width - 100;
  const {svg, add} = chart(container, 'Video timeline', 110, width);
  // Keep labels at their drawn size when the viewport changes; the wrapper scrolls.
  svg.setAttribute('style', `width: ${width}px`);
  const descriptions = [];
  const marks = intervals.map(run => {
    descriptions.push(`${states[run.value][0]} · ${(run.start / fps).toFixed(2)}–${(run.stop / fps).toFixed(2)} s · frames ${run.start}–${run.stop} (last frame not included)`);
    return add('rect', {x: 60 + plotWidth * run.start / count, y: 12, width: plotWidth * (run.stop - run.start) / count, height: 32, fill: states[run.value][1]});
  });
  for (let i = 0; i <= 4; i++) {
    const x = 60 + plotWidth * i / 4;
    add('line', {x1:x, x2:x, y1:48, y2:54, class:'chart-grid'});
    add('text', {x,y:72,'text-anchor':'middle',class:'chart-tick'}, (count / fps * i / 4).toFixed(count / fps < 1 ? 2 : 0));
  }
  add('text', {x:60 + plotWidth / 2,y:100,'text-anchor':'middle',class:'chart-axis'}, 'Time in the video (seconds)');
  inspect(svg, marks, descriptions, output);
}
export function renderGapHistogram(container, points, output) {
  const bins = gapHistogram(points);
  if (!bins.length) return;
  const maximum = bins.at(-1).stop;
  const ceiling = Math.max(4, Math.ceil(Math.max(...bins.map(bin => bin.count)) / 4) * 4);
  const {svg, add} = chart(container, 'Lengths of gaps in ball tracking', 270);
  for (let i = 0; i <= 4; i++) {
    const y = 210 - 42.5 * i, x = 60 + 135 * i;
    add('line', {x1:60,x2:600,y1:y,y2:y,class:'chart-grid'});
    add('text', {x:48,y:y+4,'text-anchor':'end',class:'chart-tick'}, String(ceiling * i / 4));
    add('text', {x,y:232,'text-anchor':'middle',class:'chart-tick'}, (maximum * i / 4).toFixed(maximum < 1 ? 3 : 1));
  }
  add('text', {x:60,y:20,class:'chart-axis'}, 'Number of gaps');
  add('text', {x:330,y:260,'text-anchor':'middle',class:'chart-axis'}, 'Time without a ball position (seconds)');
  const marks = bins.map((bin, index) => {
    const height = 170 * bin.count / ceiling;
    return add('rect', {x:60+540/bins.length*index,y:210-height,width:540/bins.length-2,height,class:'metric-primary'});
  });
  const digits = maximum < 1 ? 3 : 2;
  inspect(svg, marks, bins.map((bin, index) =>
    `${bin.start.toFixed(digits)}–${bin.stop.toFixed(digits)} s (${index === bins.length - 1 ? 'includes both ends' : 'does not include the upper end'}) · ${bin.count} ${bin.count === 1 ? 'gap' : 'gaps'} · ${points.length} total gaps`
  ), output);
}
export function renderSpellScores(container, scores, output) {
  const {svg, add} = chart(container, 'Possession score at different matching requirements', 270);
  for(let i=0;i<=4;i++) {
    const x=100+120*i;
    add('line',{x1:x,x2:x,y1:30,y2:210,class:'chart-grid'});
    add('text',{x,y:232,'text-anchor':'middle',class:'chart-tick'},(i/4).toFixed(2));
  }
  const descriptions=[];
  const marks=Object.entries(scores).map(([iou, score],i)=>{
    const y=40+i*35;
    add('text',{x:60,y:y+12,'text-anchor':'middle',class:'chart-label'},`${Math.round(Number(iou)*100)}%`);
    add('text',{x:630,y:y+12,'text-anchor':'end',class:'chart-value'},score.f1.toFixed(4));
    descriptions.push(`Required time overlap: ${Math.round(Number(iou)*100)}% · possession score: ${score.f1.toFixed(4)}`);
    return add('rect',{x:100,y,width:score.f1*480,height:16,class:'metric-primary'});
  });
  add('text',{x:60,y:20,'text-anchor':'middle',class:'chart-axis'},'Overlap');
  add('text',{x:340,y:260,'text-anchor':'middle',class:'chart-axis'},'spellF1');
  inspect(svg,marks,descriptions,output);
}
