import test from "node:test";
import assert from "node:assert/strict";
import {gapHistogram, renderTimeline, renderGapHistogram, renderSpellScores} from "../../../frontend/web/diagnostic_charts.js";
function drawing() {
  const document = {
    createElement: (tag) => node(tag),
    createElementNS: (_, tag) => node(tag),
  };
  function node(tag) {
    return {
      tag,
      ownerDocument: document,
      attrs: {},
      style: {},
      focus() {},
      children: [],
      events: {},
      textContent: "",
      setAttribute(key, value) {
        this.attrs[key] = value;
      },
      append(...nodes) {
        this.children.push(...nodes);
      },
      replaceChildren(...nodes) {
        this.children = nodes;
      },
      addEventListener(event, handler) {
        this.events[event] = handler;
      },
    };
  }
  const root = node("div");
  const all = () => {
    const result = [];
    const walk = (n) => {
      result.push(n);
      n.children.forEach(walk);
    };
    walk(root);
    return result;
  };
  return { root, all };
}

test("histogram counts duplicate durations and includes the maximum in the last bin", () => {
  const points = [{seconds: 1}, {seconds: 1}, {seconds: 2}];
  const bins = gapHistogram(points);
  assert.equal(bins.length, 30);
  assert.equal(bins[15].count, 2);
  assert.equal(bins[29].count, 1);
  assert.equal(bins.reduce((sum, bin) => sum + bin.count, 0), 3);
  assert.deepEqual(gapHistogram([]), []);
  const {root, all} = drawing(), output = {};
  renderGapHistogram(root, points, output);
  assert.equal(all().filter(n => n.tag === "rect").length, 30);
  const svg = all().find(n => n.tag === "svg");
  svg.events.keydown({key: "End", preventDefault() {}});
  assert.match(output.textContent, /1.93–2.00 s.*1 gap.*3 total gaps/);
});
test("timeline retains half-open intervals and keyboard access to trailing gap", () => {
  const {root, all} = drawing(), output = {};
  renderTimeline(root, [{start:0,stop:25,value:true},{start:25,stop:100,value:false}], 100, 25, output);
  assert.deepEqual(all().filter(n => n.tag === "rect").map(n => n.attrs.width), [135,405]);
  const svg = all().find(n => n.tag === "svg");
  svg.events.keydown({key:"ArrowRight",preventDefault() {}});
  assert.match(output.textContent, /Missing.*1.00–4.00 s.*25–100/);
});
test("spell scores preserve zero and exact bar values", () => {
  const {root, all} = drawing();
  renderSpellScores(root, {0.3:{f1:0},0.4:{f1:0.5}}, {});
  assert.deepEqual(all().filter(n => n.tag === "rect").map(n => n.attrs.width), [0,240]);
  assert.ok(all().some(n => n.textContent === "0.0000"));
});

test("subsecond histogram axes retain meaningful precision", () => {
  const {root, all} = drawing();
  renderGapHistogram(root, [{seconds:0.04,fraction:1}], {});
  assert.ok(all().some(n => n.tag === 'text' && n.textContent === '0.040'));
});

import {mountDiagnostics} from '../../../frontend/web/diagnostics.js';
test('loading is announced, duplicate opens share one request, and failures can retry', async () => {
  const {root, all} = drawing();
  let resolve, requests = 0;
  const pending = new Promise(done => resolve = done);
  const dashboard = mountDiagnostics(root, () => { requests++; return pending; });
  const first = dashboard.open();
  await dashboard.open();
  assert.equal(requests, 1);
  assert.ok(all().some(n => n.textContent === 'Loading the report…' && n.attrs.role === 'status'));
  resolve({ok:false}); await first;
  const retry = all().find(n => n.tag === 'button');
  assert.equal(retry.hidden, false);
  await retry.events.click();
  assert.equal(requests, 2);
});
test('missing report shows configuration guidance without charts', async () => {
  const {root, all} = drawing();
  await mountDiagnostics(root, async () => ({ok:true,json:async()=>({available:false})})).open();
  assert.ok(all().some(n => n.textContent.includes('python -m src.diagnostics')));
  assert.equal(all().filter(n => n.tag === 'svg').length, 0);
});


test('full diagnostic page renders comparable scopes, empty group and compact cases', async () => {
  const {root, all} = drawing();
  const group={frames:4,samples:3,visible:3,missing:1,excluded_ball:1,excluded_players:0,median_metres:2,ecdf:[{metres:2,fraction:1}]};
  const data={frame_count:12,fps:25,overview:{duration_seconds:.48,tracking_rows:24,usable_rows:20,ball_visible_frames:9,mean_visible_players:1},ball_visibility:[],possession:[],gap_ecdf:[],spell_f1:{'.5':{f1:.5}},spell_f1_mean:.5,sources:{},geometry:{labelled_frames:12,states:{H:group,A:group,D:group}},events:{frequency:[{category:'Corner',full_match:4,public_overlap:1}],set_piece_frames:{H:0,A:1,D:3},teams:{'Unknown / N/A':4},window_frames:125,stoppages:{total:1,with_evidence:1,without_evidence:0,missed_with_evidence:1,missed_without_evidence:0}},failures:[{start:0,stop:4,categories:['Missed stoppage'],ground_truth:'D',predicted:'H',ball_visibility_percent:75,events:[],description:'Review timing'}]};
  let inspected;
  await mountDiagnostics(root,async()=>({ok:true,json:async()=>data}),(item)=>inspected=item).open();
  assert.ok(all().some(n=>n.textContent==='Nothing to compare (0 of 0)'));
  assert.ok(all().some(n=>n.textContent==='100.0% (1 of 1)'));
  assert.ok(all().some(n=>n.textContent==='Predicted possession across the recording'));
  const button=all().find(n=>n.attrs['aria-label']==='Watch frames 0–4 in Viewer');
  button.events.click();assert.equal(inspected.start,0);
  assert.ok(all().some(n=>n.textContent==='Home possession (H)'));
});
