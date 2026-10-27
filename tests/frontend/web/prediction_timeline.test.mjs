import test from "node:test";
import assert from "node:assert/strict";
import { PredictionTimeline } from "../../../frontend/web/viewer/prediction_timeline.js";

function timelineFixture(frameCount) {
  let painted = [];
  function canvas() {
    const rectangles = [];
    const context = {
      clearRect() { rectangles.length = 0; },
      fillRect(x, y, width, height) {
        rectangles.push({ x, y, width, height, colour: this.fillStyle });
      },
      drawImage(background) { painted = background.rectangles.map((item) => ({ ...item })); },
      beginPath() {}, moveTo() {}, lineTo() {}, stroke() {},
    };
    return {
      width: 100, height: 40, rectangles,
      ownerDocument: { createElement: canvas },
      getContext: () => context,
      getBoundingClientRect: () => ({ left: 10, width: 100 }),
    };
  }
  const timeline = new PredictionTimeline(canvas(), frameCount);
  return { timeline, painted: () => painted };
}

test("prediction timeline preserves gaps and paints inclusive one-frame intervals through the recording end", () => {
  const fixture = timelineFixture(10);
  fixture.timeline.setSegments([
    { start_frame: 0, end_frame: 0, label: "H" },
    { start_frame: 9, end_frame: 9, label: "X" },
  ]);
  const intervals = fixture.painted().slice(1);
  assert.deepEqual(intervals.map(({ x, width }) => ({ x, width })), [
    { x: 0, width: 10 }, { x: 90, width: 10 },
  ]);
  fixture.timeline.showFrame(9);
  assert.equal(fixture.timeline.frameAt({ clientX: 110 }), 9);
  assert.equal(fixture.timeline.frameAt({ clientX: 60 }), 5);
});

test("a single-frame prediction spans the timeline and every click selects frame zero", () => {
  const fixture = timelineFixture(1);
  fixture.timeline.setSegments([{ start_frame: 0, end_frame: 0, label: "A" }]);
  assert.equal(fixture.painted().at(-1).width, 100);
  for (const clientX of [0, 10, 60, 110, 120]) {
    assert.equal(fixture.timeline.frameAt({ clientX }), 0);
  }
});
