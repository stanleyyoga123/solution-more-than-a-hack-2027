/** Read-only diagnostics, styled with the existing analysis workspace primitives. */
import { GAP_BIN_COUNT, renderTimeline, renderGapHistogram, renderSpellScores, states } from './diagnostic_charts.js';

export function mountDiagnostics(root, fetchReport = () => fetch('/api/diagnostics')) {
  const document = root.ownerDocument;
  let loaded = false, loading = false;
  const node = (tag, text, parent = root, className = '') => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    el.className = className;
    parent.append(el);
    return el;
  };
  const header = node('header', undefined, root, 'experiments-header');
  const heading = node('div', undefined, header);
  node('h1', 'Data & Diagnostics', heading).id = 'diagnostics-title';
  node('p', 'Tactical tracking and the public possession baseline.', heading, 'intro');
  const retry = node('button', 'Retry loading', header, 'quality-button');
  retry.type = 'button'; retry.hidden = true;
  const status = node('p', '', root, 'analysis-status');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const content = node('div');
  function section(title, note, parent = content) {
    const section = node('section', undefined, parent, 'experiment-chart');
    node('h2', title, section);
    if (note) node('p', note, section, 'experiment-note');
    return section;
  }
  function plot(section, draw) {
    node('p', 'Focus the chart and use ← / → to inspect values. Scroll horizontally on smaller screens.', section, 'experiment-note');
    const wrap = node('div', undefined, section, 'chart-scroll');
    const output = node('p', '', section, 'experiment-note diagnostic-readout');
    output.setAttribute('aria-live', 'polite');
    draw(wrap, output);
  }
  function legend(section, keys) {
    const legend = node('div', undefined, section, 'chart-legend');
    keys.forEach(key => {
      const item = node('span', undefined, legend);
      const swatch = node('i', undefined, item);
      swatch.style.background = states[key][1];
      swatch.setAttribute('aria-hidden', 'true');
      node('span', states[key][0], item);
    });
  }
  function table(section, headers, rows) {
    const wrap = node('div', undefined, section, 'experiment-table-scroll');
    const table = node('table', undefined, wrap, 'experiment-table diagnostic-table');
    const head = node('tr', undefined, node('thead', undefined, table));
    headers.forEach(text => node('th', text, head).scope = 'col');
    const body = node('tbody', undefined, table);
    rows.forEach(([name, value]) => {
      const row = node('tr', undefined, body);
      node('th', name, row).scope = 'row';
      node('td', value, row);
    });
  }
  function render(data) {
    const o = data.overview;
    const number = value => value.toLocaleString('en-US');
    const overview = section('Data overview & tracking reliability', 'Usable observations have valid, finite coordinates. Missing observations remain missing.');
    const metrics = node('dl', undefined, overview, 'diagnostic-metrics');
    for (const [name, value] of [
      ['Frames', number(data.frame_count)], ['Frame rate', `${data.fps} fps`],
      ['Duration', `${number(o.duration_seconds)} s`], ['Tracking rows', number(o.tracking_rows)],
      ['Usable observation rows', `${number(o.usable_rows)} / ${number(o.tracking_rows)}`],
      ['Ball visible', `${number(o.ball_visible_frames)} / ${number(data.frame_count)} frames`],
      ['Mean visible players per frame', o.mean_visible_players.toFixed(2)],
    ]) {
      const item = node('div', undefined, metrics);
      node('dt', name, item); node('dd', value, item);
    }
    const ball = section('Ball visibility', `${number(o.ball_visible_frames)} observed frames of ${number(data.frame_count)}. Tracking availability, not camera visibility or inferred possession.`);
    legend(ball, ['true', 'false']);
    plot(ball, (wrap, output) => renderTimeline(wrap, data.ball_visibility, data.frame_count, data.fps, output));
    const possession = section('Public baseline possession', `${number(data.frame_count)} frames · baseline predictions on the tactical recording timeline.`);
    legend(possession, ['H', 'A', 'D', 'X']);
    plot(possession, (wrap, output) => renderTimeline(wrap, data.possession, data.frame_count, data.fps, output));
    const grid = node('div', undefined, content, 'experiment-charts');
    const histogram = section('Missing-ball gap-duration histogram', `${number(data.gap_ecdf.length)} gaps · ${GAP_BIN_COUNT} equal-width bins; recording-edge gaps included.`, grid);
    if (data.gap_ecdf.length) plot(histogram, (wrap, output) => renderGapHistogram(wrap, data.gap_ecdf, output));
    else node('p', 'No missing-ball gaps in this recording.', histogram, 'chart-empty');
    const scores = section('Official spellF1 by IoU threshold', `Mean spellF1: ${data.spell_f1_mean.toFixed(4)} · ${Object.keys(data.spell_f1).length} IoU thresholds.`, grid);
    plot(scores, (wrap, output) => renderSpellScores(wrap, data.spell_f1, output));
    node('p', 'Official scorer: ground-truth X frames are excluded; prediction abstentions are filled within scored runs.', scores, 'experiment-note');
    const provenance = section('Input provenance', 'Report inputs. Times are tactical recording time, not broadcast or match clock time.');
    table(provenance, ['Input', 'Path'], Object.entries(data.sources));
  }
  async function open() {
    if (loaded || loading) return;
    loading = true; retry.hidden = true; content.replaceChildren();
    status.textContent = 'Loading diagnostics…';
    content.setAttribute('aria-busy', 'true');
    try {
      const response = await fetchReport();
      if (!response.ok) throw new Error('Diagnostic export could not be loaded.');
      const data = await response.json();
      if (data.available === false) {
        status.textContent = 'Diagnostic report unavailable.';
        node('p', 'Generate a report with python -m src.diagnostics, then start the viewer with --diagnostics output/diagnostics.json. See frontend/README.md for input paths.', content, 'chart-empty');
      } else {
        render(data);
        status.textContent = 'Tactical recording · Public baseline · Read-only report';
        loaded = true;
      }
    } catch (error) {
      content.replaceChildren();
      status.textContent = `${error.message} Retry loading the report.`;
      retry.hidden = false;
    } finally {
      loading = false;
      content.setAttribute('aria-busy', 'false');
    }
  }
  retry.addEventListener('click', open);
  return {open};
}
