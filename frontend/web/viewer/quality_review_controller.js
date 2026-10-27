import {
  adjacentQualityEvent,
  eventSeekFrame,
  filterQualityEvents,
  nearestQualityEvent,
  qualityEvents,
} from "./quality_model.js";

const PAGE_SIZE = 50;

/** Coordinate report filtering and selection with the existing source-frame clock. */
export class QualityReviewController {
  /**
   * @param {import('./tracking_client.js').TrackingClient} client
   * @param {import('./quality_review_view.js').QualityReviewView} view
   * @param {import('./quality_timeline.js').QualityTimeline} timeline
   * @param {(frame:number)=>void} seek
   * @param {(entityId:string|null)=>void} highlight
   */
  constructor(client, view, timeline, seek, highlight) {
    this._client = client;
    this._view = view;
    this._timeline = timeline;
    this._seek = seek;
    this._highlight = highlight;
    /** @type {import('./quality_types.js').QualityEvent[]} */
    this._events = [];
    /** @type {import('./quality_types.js').QualityEvent[]} */
    this._filtered = [];
    /** @type {import('./quality_types.js').QualityEvent|null} */
    this._selected = null;
    this._frame = 0;
    this._page = 0;
    this._ready = false;
  }

  async start() {
    this._bindControls();
    try {
      const payload = await this._client.quality();
      this._events = qualityEvents(payload);
      const entities = [...new Set(this._events.map((event) => event.entity_id))];
      entities.sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
      this._view.showReports(payload, entities);
      this._applyFilters();
    } catch (error) {
      this._view.showStatus(`Quality reports could not load: ${error.message}`, true);
      this._render();
    }
  }

  /** @param {boolean} ready */
  setReady(ready) {
    this._ready = ready;
    this._render();
  }

  /** @param {number} frame */
  showFrame(frame) {
    this._frame = frame;
    this._timeline.showFrame(frame);
    this._view.showFrame(this._selected, frame);
    this._showNavigation();
  }

  _bindControls() {
    const controls = this._view.controls;
    controls.category.addEventListener("change", () => this._applyFilters());
    controls.entity.addEventListener("change", () => this._applyFilters());
    controls.highlight.addEventListener("change", () => this._updateHighlight());
    controls.previous.addEventListener("click", () => this._navigate(-1));
    controls.next.addEventListener("click", () => this._navigate(1));
    controls.previousPage.addEventListener("click", () => this._changePage(-1));
    controls.nextPage.addEventListener("click", () => this._changePage(1));
    controls.clear.addEventListener("click", () => {
      this._selected = null;
      this._updateHighlight();
      this._render();
    });
    controls.before.addEventListener("click", () => this._seekBoundary(false));
    controls.after.addEventListener("click", () => this._seekBoundary(true));
    controls.list.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-event-id]");
      if (!button || !this._ready) return;
      const selected = this._filtered.find((item) => item.id === button.dataset.eventId);
      if (selected) this._select(selected);
    });
    controls.timeline.addEventListener("click", (event) => {
      if (!this._ready) return;
      const point = this._timeline.pointAt(event);
      const selected = nearestQualityEvent(this._filtered, point.frame, point.lane);
      if (selected) this._select(selected);
    });
  }

  _applyFilters() {
    const controls = this._view.controls;
    this._filtered = filterQualityEvents(
      this._events, controls.category.value, controls.entity.value,
    );
    this._page = 0;
    if (this._selected && !this._filtered.some((event) => event.id === this._selected.id)) {
      this._selected = null;
      this._updateHighlight();
    }
    this._render();
  }

  /** @param {number} direction */
  _navigate(direction) {
    const event = adjacentQualityEvent(
      this._filtered, this._selected?.id ?? null, this._frame, direction,
    );
    if (event && this._ready) this._select(event);
  }

  /** @param {number} offset */
  _changePage(offset) {
    const lastPage = Math.max(0, Math.ceil(this._filtered.length / PAGE_SIZE) - 1);
    this._page = Math.max(0, Math.min(lastPage, this._page + offset));
    this._renderList();
  }

  /** @param {import('./quality_types.js').QualityEvent} event */
  _select(event) {
    this._selected = event;
    const index = this._filtered.findIndex((item) => item.id === event.id);
    this._page = Math.floor(index / PAGE_SIZE);
    this._seek(eventSeekFrame(event));
    this._updateHighlight();
    this._render();
  }

  /** @param {boolean} after */
  _seekBoundary(after) {
    if (!this._ready || this._selected === null) return;
    const event = this._selected;
    const frame = event.kind === "motion"
      ? (after ? event.end_frame : event.start_frame)
      : (after ? event.right_frame : event.left_frame);
    if (frame !== null) this._seek(frame);
  }

  _updateHighlight() {
    const entity = this._view.controls.highlight.checked && this._selected !== null
      ? this._selected.entity_id : null;
    this._highlight(entity);
  }

  _render() {
    this._timeline.setEvents(this._filtered, this._selected?.id ?? null);
    this._renderList();
    this._view.showSelection(this._selected, this._frame, this._ready);
    this._showNavigation();
  }

  _renderList() {
    const start = this._page * PAGE_SIZE;
    this._view.showList(
      this._filtered.slice(start, start + PAGE_SIZE), this._selected?.id ?? null,
      this._page, this._filtered.length, this._ready,
    );
  }

  _showNavigation() {
    const previous = adjacentQualityEvent(
      this._filtered, this._selected?.id ?? null, this._frame, -1,
    );
    const next = adjacentQualityEvent(
      this._filtered, this._selected?.id ?? null, this._frame, 1,
    );
    this._view.setNavigation(previous, next, this._ready);
  }
}
