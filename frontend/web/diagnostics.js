import {renderSummary} from './diagnostic_summary.js';
import {renderAdvanced} from './advanced_diagnostics.js';
/** Read-only diagnostics, styled with the existing analysis workspace primitives. */
import { GAP_BIN_COUNT, renderTimeline, renderGapHistogram, renderSpellScores, states } from './diagnostic_charts.js';

export function mountDiagnostics(root, fetchReport = () => fetch('/api/diagnostics'), onInspect = () => {}) {
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
  node('p', 'See where tracking is missing, compare possession predictions with the reference answers, and watch moments that need a closer look.', heading, 'intro');
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
    if (data.generated_at) node('p', `Updated ${new Date(data.generated_at).toLocaleString()}. All times refer to the tactical video, not the match clock.`, content, 'experiment-note');
    node('p', 'The organisers provide reference answers for part of the recording: who has the ball, or whether play has stopped. We can check predictions only where those answers are available. A frame is one image in the video.', content, 'experiment-note');
    renderSummary(data,content,node);
    node('p','Point to or tap a chart to see its values. With a chart selected, use the arrow keys to move through it, or Home and End to jump to either end. Swipe sideways on wide charts.',content,'experiment-note');
    const number = value => value.toLocaleString('en-US');
    const overview = section('Recording & tracking coverage', 'A recorded position tells us where a player or the ball was. Gaps are left empty; no positions have been filled in.');
    overview.id='diagnostics-tracking';
    const metrics = node('dl', undefined, overview, 'diagnostic-metrics');
    for (const [name, value] of [
      ['Video frames', number(data.frame_count)], ['Frame rate', `${data.fps} fps`],
      ['Duration', `${number(o.duration_seconds)} s`], ['Position records', number(o.tracking_rows)],
      ['Records with a usable position', `${number(o.usable_rows)} / ${number(o.tracking_rows)}`],
      ['Frames with a ball position', `${number(o.ball_visible_frames)} / ${number(data.frame_count)} frames`],
      ['Average players tracked per frame', o.mean_visible_players.toFixed(2)],
    ]) {
      const item = node('div', undefined, metrics);
      node('dt', name, item); node('dd', value, item);
    }
    const ball = section('When the ball is tracked', `The ball has a recorded position in ${number(o.ball_visible_frames)} of ${number(data.frame_count)} frames. A missing position does not necessarily mean it is off camera or out of play.`);
    legend(ball, ['true', 'false']);
    plot(ball, (wrap, output) => renderTimeline(wrap, data.ball_visibility, data.frame_count, data.fps, output));
    const possession = section('Predicted possession across the recording', `The baseline is our starting prediction method. This shows its answers for all ${number(data.frame_count)} frames, not the reference answers.`);
    legend(possession, ['H', 'A', 'D', 'X']);
    plot(possession, (wrap, output) => renderTimeline(wrap, data.possession, data.frame_count, data.fps, output));
    const grid = node('div', undefined, content, 'experiment-charts');
    const histogram = section('How long is the ball missing?', `${number(data.gap_ecdf.length)} gaps, grouped by length into ${GAP_BIN_COUNT} ranges. Gaps at the start and end of the video count too.`, grid);
    if (data.gap_ecdf.length) plot(histogram, (wrap, output) => renderGapHistogram(wrap, data.gap_ecdf, output));
    else node('p', 'No missing-ball gaps in this recording.', histogram, 'chart-empty');
    const scores = section('How well do predicted possessions match?', `Official possession score (spellF1): ${data.spell_f1_mean.toFixed(4)}. Higher is better, up to 1. The bars show ${Object.keys(data.spell_f1).length} levels of matching strictness.`, grid);
    plot(scores, (wrap, output) => renderSpellScores(wrap, data.spell_f1, output));
    node('p', 'A possession is a period when one team has the ball. The score checks whether predicted possessions match the reference in time. IoU measures how much their time spans overlap; a higher requirement is stricter. Only frames with reference answers are scored.', scores, 'experiment-note');
    const scoringHelp=node('details',undefined,scores,'diagnostic-method');
    node('summary','Official scoring rules',scoringHelp);
    node('p','Frames without a reference answer (X) are not scored. The official scorer fills missing predictions within the scored sections before comparing possessions.',scoringHelp,'experiment-note');
    renderAdvanced(data, {section,node,plot,legend,table}, onInspect);
    const provenance = section('About this report', 'Files used to prepare this report. The report is loaded when the viewer starts; restart the viewer after replacing it.');
    table(provenance, ['Input', 'Source filename'], Object.entries(data.sources).map(([name,path])=>[({tracking:'Player and ball positions',metadata:'Recording and pitch details',baseline:'Possession predictions',ground_truth:'Reference answers',smart_tagging:'Match-event tags'}[name] || name),path]));
    if (data.generated_at) node('p', `Report format ${data.schema_version}. The saved report also records which versions of these files were used.`, provenance, 'experiment-note');
  }
  async function open() {
    if (loaded || loading) return;
    loading = true; retry.hidden = true; content.replaceChildren();
    status.textContent = 'Loading the report…';
    content.setAttribute('aria-busy', 'true');
    try {
      const response = await fetchReport();
      if (!response.ok) throw new Error('The report could not be loaded.');
      const data = await response.json();
      if (data.available === false) {
        status.textContent = 'No report is available yet.';
        node('p', 'Generate output/diagnostics.json with python -m src.diagnostics, then restart the viewer to load it automatically. Use --diagnostics for a custom report path. See frontend/README.md for input paths.', content, 'chart-empty');
      } else {
        render(data);
        status.textContent = 'Showing the saved report. Exploring it does not change the data.';
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
