import { formatTime } from "./timeline.js";
import { qualityEventColour } from "./quality_model.js";

/** Render quality reports and details without controlling playback or data access. */
export class QualityReviewView {
  /** @param {HTMLElement} root @param {number} fps */
  constructor(root, fps) {
    this._root = root;
    this._document = root.ownerDocument;
    this._fps = fps;
  }

  get controls() {
    return {
      category: this._query("#quality-category"),
      entity: this._query("#quality-entity"),
      highlight: this._query("#quality-highlight"),
      previous: this._query("#quality-previous"),
      next: this._query("#quality-next"),
      previousPage: this._query("#quality-page-previous"),
      nextPage: this._query("#quality-page-next"),
      before: this._query("#quality-before"),
      after: this._query("#quality-after"),
      clear: this._query("#quality-clear"),
      list: this._query("#quality-events"),
      timeline: this._query("#quality-timeline"),
    };
  }

  /** @param {import('./quality_types.js').QualityPayload} payload @param {string[]} entities */
  showReports(payload, entities) {
    const summary = payload.summary;
    this._query("#quality-summary").textContent = (
      `${summary.flagged_samples.toLocaleString()} flagged samples · `
      + `${summary.trajectory_episodes.toLocaleString()} motion episodes · `
      + `${summary.gap_count.toLocaleString()} gaps`
    );
    const availability = [];
    if (!payload.available.trajectories) availability.push("Step 07 report unavailable");
    if (!payload.available.gaps) availability.push("Step 08 report unavailable");
    this.showStatus(availability.length ? availability.join(". ") + "." : (
      "Reports loaded. Select an event to inspect its footage."
    ));
    const entityControl = this.controls.entity;
    for (const entity of entities) {
      const option = this._document.createElement("option");
      option.value = entity;
      option.textContent = this._entityLabel(entity);
      entityControl.append(option);
    }
    const counts = summary.status_counts;
    this._query("#quality-gap-counts").textContent = (
      `${counts.implausible.toLocaleString()} implausible · `
      + `${counts.uncertain.toLocaleString()} uncertain · `
      + `${counts.plausible.toLocaleString()} plausible gaps`
    );
  }

  /** @param {string} message @param {boolean} [error] */
  showStatus(message, error = false) {
    const status = this._query("#quality-status");
    status.textContent = message;
    status.dataset.state = error ? "error" : "ready";
  }

  /**
   * @param {import('./quality_types.js').QualityEvent[]} events
   * @param {string|null} selectedId
   * @param {number} page
   * @param {number} total
   * @param {boolean} ready
   */
  showList(events, selectedId, page, total, ready) {
    const list = this.controls.list;
    list.replaceChildren();
    for (const event of events) {
      const item = this._document.createElement("li");
      const button = this._document.createElement("button");
      button.type = "button";
      button.className = "quality-event";
      button.dataset.eventId = event.id;
      button.disabled = !ready;
      button.setAttribute("aria-pressed", String(event.id === selectedId));
      const title = this._document.createElement("span");
      title.className = "quality-event-title";
      const dot = this._document.createElement("span");
      dot.className = "legend-dot";
      dot.style.backgroundColor = qualityEventColour(event);
      title.append(dot, this._document.createTextNode(
        `${this._entityLabel(event.entity_id)} · ${this._eventLabel(event)}`,
      ));
      const time = this._document.createElement("span");
      time.className = "quality-event-time";
      time.textContent = `${formatTime(event.start_frame / this._fps, true)} · `
        + `${event.start_frame}–${event.end_frame}`;
      button.append(title, time);
      item.append(button);
      list.append(item);
    }
    if (!total) {
      const empty = this._document.createElement("li");
      empty.className = "quality-empty";
      empty.textContent = "No events match these filters.";
      list.append(empty);
    }
    const pages = Math.max(1, Math.ceil(total / 50));
    this._query("#quality-page").textContent = (
      `Page ${page + 1} of ${pages} · ${total.toLocaleString()} events`
    );
    this.controls.previousPage.disabled = page === 0;
    this.controls.nextPage.disabled = page >= pages - 1;
  }

  /**
   * @param {import('./quality_types.js').QualityEvent|null} event
   * @param {number} currentFrame
   * @param {boolean} ready
   */
  showSelection(event, currentFrame, ready) {
    const title = this._query("#quality-selection-title");
    const metrics = this._query("#quality-metrics");
    metrics.replaceChildren();
    this.controls.clear.disabled = event === null;
    this.controls.before.disabled = !ready || event === null
      || (event.kind === "gap" && event.left_frame === null);
    this.controls.after.disabled = !ready || event === null
      || (event.kind === "gap" && event.right_frame === null);
    if (event === null) {
      title.textContent = "Select a motion episode or gap";
      this._query("#quality-selection-note").textContent = (
        "Use the event list, timeline lanes, or previous/next event controls."
      );
      this._query("#quality-current-context").textContent = "";
      return;
    }
    title.textContent = `${this._entityLabel(event.entity_id)} · ${this._eventLabel(event)}`;
    this._metric(metrics, "Frames", `${event.start_frame}–${event.end_frame} (inclusive)`);
    this._metric(metrics, "Video time", `${formatTime(event.start_frame / this._fps, true)}–`
      + formatTime(event.end_frame / this._fps, true));
    if (event.kind === "motion") {
      this._metric(metrics, "Flagged samples", event.sample_count.toLocaleString());
      this._metric(metrics, "Peak speed", this._number(event.peak_speed_mps, "m/s"));
      this._metric(metrics, "Peak acceleration", this._number(event.peak_acceleration_mps2, "m/s²"));
      this._metric(metrics, "Checks", [
        event.speed_flag ? "speed" : "",
        event.acceleration_flag ? "acceleration" : "",
      ].filter(Boolean).join(", "));
      this._query("#quality-selection-note").textContent = (
        "Adjacent flags are grouped into an episode. Selection jumps to its peak sample."
      );
    } else {
      this._metric(metrics, "Missing duration", this._number(event.gap_seconds, "s"));
      this._metric(metrics, "Reason", event.reason.replaceAll("_", " "));
      this._metric(metrics, "Required speed", this._number(event.required_speed_mps, "m/s"));
      this._metric(metrics, "Forward / backward error", (
        `${this._number(event.forward_error_m, "m")} / `
        + this._number(event.backward_error_m, "m")
      ));
      this._query("#quality-selection-note").textContent = (
        "Null positions have no marker. Inspect the observed boundaries; continuity is not verified identity."
      );
    }
    this.showFrame(event, currentFrame);
  }

  /** @param {import('./quality_types.js').QualityEvent|null} event @param {number} frame */
  showFrame(event, frame) {
    if (event === null) return;
    const inside = frame >= event.start_frame && frame <= event.end_frame;
    this._query("#quality-current-context").textContent = (
      `Frame ${frame} · ${inside ? "inside" : "outside"} selected interval`
    );
  }

  /**
   * @param {import('./quality_types.js').QualityEvent|null} previous
   * @param {import('./quality_types.js').QualityEvent|null} next
   * @param {boolean} ready
   */
  setNavigation(previous, next, ready) {
    this.controls.previous.disabled = !ready || previous === null;
    this.controls.next.disabled = !ready || next === null;
  }

  /** @param {HTMLDListElement} list @param {string} label @param {string} value */
  _metric(list, label, value) {
    const term = this._document.createElement("dt");
    term.textContent = label;
    const description = this._document.createElement("dd");
    description.textContent = value;
    list.append(term, description);
  }

  /** @param {number|null} value @param {string} unit */
  _number(value, unit) {
    return value === null ? "Unavailable" : `${value.toFixed(2)} ${unit}`;
  }

  /** @param {string} entity */
  _entityLabel(entity) {
    return entity === "ball" ? "Ball" : entity.replace(/^player_/, "Player ");
  }

  /** @param {import('./quality_types.js').QualityEvent} event */
  _eventLabel(event) {
    return event.kind === "motion" ? "Motion warning" : `${event.status} gap`;
  }

  /** @param {string} selector */
  _query(selector) {
    return this._root.querySelector(selector);
  }
}
