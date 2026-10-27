import { BALL_COLOUR } from "./entity_markers.js";
import { formatTime } from "./timeline.js";

/** Present recording state without controlling video or downloading data. */
export class ViewerView {
  /** @param {Document} document */
  constructor(document) {
    this._document = document;
  }

  /**
   * @param {import('./tracking_types.js').RecordingMetadata} metadata
   * @param {Map<string, string>} colours
   */
  initialize(metadata, colours) {
    const total = metadata.frame_count - 1;
    this._document.querySelector("#timeline").max = String(total);
    this._document.querySelector("#frame-input").max = String(total);
    this._document.querySelector("#frame-total").textContent = `/ ${total.toLocaleString()}`;
    this._document.querySelector("#timeline-end").textContent = formatTime(total / metadata.fps);
    this._document.querySelector("#source-details").textContent = (
      `${metadata.fps} FPS · ${metadata.video_width} × ${metadata.video_height}`
    );
    const pitch = metadata.pitch_dimensions;
    this._document.querySelector("#pitch-dimensions").textContent = (
      `${pitch.length} × ${pitch.width} m · x →  y ↓`
    );
    const legend = this._document.querySelector("#team-legend");
    for (const [id, name] of Object.entries(metadata.teams)) {
      legend.append(this._legendItem(name, colours.get(id)));
    }
    legend.append(this._legendItem("Ball", BALL_COLOUR));
  }

  enableControls() {
    for (const element of this._document.querySelectorAll(".transport [disabled]")) {
      element.disabled = false;
    }
  }

  /** @param {number} frame @param {number} fps */
  showFrame(frame, fps) {
    const seconds = frame / fps;
    this._document.querySelector("#source-time").textContent = formatTime(seconds, true);
    this._document.querySelector("#timeline-current").textContent = formatTime(seconds);
    this._document.querySelector("#timeline").value = String(frame);
    const input = this._document.querySelector("#frame-input");
    if (this._document.activeElement !== input) input.value = String(frame);
  }

  /** @param {boolean} playing */
  showPlaying(playing) {
    this._document.querySelector("#play-text").textContent = playing ? "Pause" : "Play";
    this._document.querySelector("#play-symbol").textContent = playing ? "Ⅱ" : "▶";
    this._document.querySelector("#play-pause").setAttribute(
      "aria-label", playing ? "Pause recording" : "Play recording",
    );
  }

  /** @param {number} camera @param {number} pitch */
  showCounts(camera, pitch) {
    this._document.querySelector("#camera-count").textContent = `${camera} players visible`;
    this._document.querySelector("#pitch-count").textContent = `${pitch} players tracked`;
  }

  clearCounts() {
    this._document.querySelector("#camera-count").textContent = "— players visible";
    this._document.querySelector("#pitch-count").textContent = "— players tracked";
  }

  /** @param {string} message @param {'ready' | 'loading' | 'error'} state */
  showStatus(message, state) {
    const status = this._document.querySelector("#sync-status");
    if (status.textContent === message && status.dataset.state === state) return;
    status.textContent = message;
    status.dataset.state = state;
  }

  /** @param {string} name @param {string} colour */
  _legendItem(name, colour) {
    const item = this._document.createElement("span");
    item.className = "legend-item";
    const dot = this._document.createElement("span");
    dot.className = "legend-dot";
    dot.style.backgroundColor = colour;
    const label = this._document.createElement("span");
    label.textContent = name;
    item.append(dot, label);
    return item;
  }
}
