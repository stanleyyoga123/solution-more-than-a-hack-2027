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
  assert.match(output.textContent, /1.93–2.00 s.*1 gaps.*3 total gaps/);
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
  assert.ok(all().some(n => n.textContent === 'Loading diagnostics…' && n.attrs.role === 'status'));
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
