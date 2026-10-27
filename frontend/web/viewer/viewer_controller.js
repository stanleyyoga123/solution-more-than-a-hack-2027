import { frameAtTime, frameSeekTime } from "./timeline.js";

/** Coordinate tracking and rendered footage from the source video's frame clock. */
export class ViewerController {
  /** @param {import('./tracking_types.js').ViewerDependencies} dependencies */
  constructor({
    video, controls, view, cache, camera, pitch, birdseye, birdseyeOverlay, metadata,
    qualityReview, predictions,
  }) {
    this._video = video;
    this._controls = controls;
    this._view = view;
    this._cache = cache;
    this._camera = camera;
    this._pitch = pitch;
    this._birdseye = birdseye;
    this._birdseyeOverlay = birdseyeOverlay;
    this._birdseyeOverlay.setLabels(controls.birdseyeLabels.checked);
    this._birdseyeOverlay.setVisible(controls.birdseyeOverlay.checked);
    this._metadata = metadata;
    this._qualityReview = qualityReview;
    this._predictions = predictions;
    this._currentFrame = -1;
    this._cameraLabels = controls.cameraLabels.checked;
    this._pitchLabels = controls.pitchLabels.checked;
    this._overlay = true;
  }

  start() {
    if (!("requestVideoFrameCallback" in this._video)) {
      this._view.showStatus(
        "This browser needs requestVideoFrameCallback support for synchronized playback.",
        "error",
      );
      return;
    }
    this._bindControls();
    this._birdseye.start();
    this._pitch.clear();
    this._video.addEventListener("loadedmetadata", () => {
      this._view.enableControls();
      this._qualityReview.setReady(true);
      this._predictions.setReady(true);
      this.seek(this._metadata.default_frame);
    }, { once: true });
    this._video.addEventListener("seeking", () => {
      this._currentFrame = -1;
      this._predictions.suspend();
      this._clearTracking();
      this._birdseye.suspend("Seeking source frame…");
      this._view.showStatus("Seeking source frame…", "loading");
    });
    this._video.addEventListener("seeked", () => {
      this._displayFrame(this._frameAt(this._video.currentTime));
    });
    this._video.addEventListener("play", () => {
      this._view.showPlaying(true);
      this._syncBirdseye();
    });
    this._video.addEventListener("playing", () => this._syncBirdseye());
    this._video.addEventListener("ratechange", () => this._syncBirdseye());
    this._video.addEventListener("pause", () => {
      this._view.showPlaying(false);
      if (!this._video.seeking) {
        this._displayFrame(this._frameAt(this._video.currentTime));
      }
    });
    this._video.addEventListener("ended", () => this._view.showPlaying(false));
    this._video.addEventListener("waiting", () => {
      this._birdseye.suspend("Waiting for source video…");
    });
    this._video.addEventListener("error", () => {
      this._qualityReview.setReady(false);
      this._predictions.setReady(false);
      this._clearTracking();
      this._birdseye.suspend("Source video unavailable.");
      this._view.showStatus(
        "Cannot load the source video. Check the server's video path and browser codec support.",
        "error",
      );
    });
    this._requestVideoFrame();
    this._video.src = this._metadata.video_url;
  }

  /** Pause and seek to a zero-based source frame. @param {number} frame */
  seek(frame) {
    const target = Math.max(0, Math.min(this._metadata.frame_count - 1, frame));
    this._video.pause();
    this._currentFrame = -1;
    this._predictions.suspend();
    this._clearTracking();
    this._birdseye.suspend("Seeking source frame…");
    this._controls.frame.value = String(target);
    this._view.showFrame(target, this._metadata.fps);
    this._qualityReview.showFrame(target);
    this._view.showStatus("Seeking source frame…", "loading");
    this._video.currentTime = frameSeekTime(target, this._metadata.fps);
  }

  /** Highlight an observed entity without creating positions across missing data.
   * @param {string|null} entityId
   */
  highlightEntity(entityId) {
    this._camera.setHighlightedEntity(entityId);
    this._pitch.setHighlightedEntity(entityId);
    this._birdseyeOverlay.setHighlightedEntity(entityId);
    this._redrawCurrentFrame();
  }

  async _togglePlayback() {
    if (!this._video.paused) {
      this._video.pause();
      return;
    }
    if (this._video.ended) this._video.currentTime = 0;
    try {
      await this._video.play();
    } catch (error) {
      this._view.showStatus(`Playback could not start: ${error.message}`, "error");
    }
  }

  _requestVideoFrame() {
    this._video.requestVideoFrameCallback((_, details) => {
      if (!this._video.seeking) this._displayFrame(this._frameAt(details.mediaTime));
      this._requestVideoFrame();
    });
  }

  /** @param {number} seconds */
  _frameAt(seconds) {
    return frameAtTime(seconds, this._metadata.fps, this._metadata.frame_count);
  }

  /** @param {number} frame */
  async _displayFrame(frame) {
    this._currentFrame = frame;
    this._syncBirdseye(frame);
    this._view.showFrame(frame, this._metadata.fps);
    this._qualityReview.showFrame(frame);
    this._predictions.showFrame(frame);
    const cached = this._cache.peek(frame);
    if (cached) {
      this._renderTracking(cached);
    } else {
      this._clearTracking();
      this._view.showStatus("Loading positions for this frame…", "loading");
      try {
        const positions = await this._cache.get(frame);
        if (this._currentFrame !== frame || this._video.seeking) return;
        this._renderTracking(positions);
      } catch (error) {
        if (this._currentFrame !== frame || this._video.seeking) return;
        this._video.pause();
        this._view.showStatus(`${error.message} Seek to retry.`, "error");
        return;
      }
    }
    // A failed prefetch will be surfaced if that chunk is actually needed.
    this._cache.prefetch(frame).catch(() => {});
  }

  /** @param {import('./tracking_types.js').TrackingFrame} positions */
  _renderTracking(positions) {
    const visible = this._camera.render(
      positions.pixels,
      this._cameraLabels,
      this._overlay,
    );
    this._pitch.render(positions.normalized, this._pitchLabels);
    const tracked = positions.normalized.filter(
      (entity) => entity.entity_type === "player",
    ).length;
    this._view.showCounts(visible, tracked);
    const message = tracked === 0
      ? "Synchronized · no player positions in this frame"
      : "Synchronized to source frame";
    this._view.showStatus(message, "ready");
  }

  _clearTracking() {
    this._camera.clear();
    this._pitch.clear();
    this._view.clearCounts();
  }

  /** @param {number} offset */
  _stepFrame(offset) {
    const frame = this._currentFrame < 0
      ? this._frameAt(this._video.currentTime)
      : this._currentFrame;
    this.seek(frame + offset);
  }

  _bindControls() {
    const controls = this._controls;
    controls.play.addEventListener("click", () => this._togglePlayback());
    controls.previous.addEventListener("click", () => this._stepFrame(-1));
    controls.next.addEventListener("click", () => this._stepFrame(1));
    controls.kickoff.addEventListener("click", () => this.seek(this._metadata.default_frame));
    controls.timeline.addEventListener("input", () => this.seek(Number(controls.timeline.value)));
    controls.frame.addEventListener("change", () => {
      const frame = controls.frame.valueAsNumber;
      if (!Number.isInteger(frame)) {
        controls.frame.value = String(this._frameAt(this._video.currentTime));
        return;
      }
      this.seek(frame);
    });
    controls.frame.addEventListener("keydown", (event) => {
      if (event.key === "Enter") controls.frame.blur();
    });
    controls.speed.addEventListener("change", () => {
      this._video.playbackRate = Number(controls.speed.value);
    });
    controls.cameraLabels.addEventListener("change", () => {
      this._cameraLabels = controls.cameraLabels.checked;
      this._redrawCurrentFrame();
    });
    controls.pitchLabels.addEventListener("change", () => {
      this._pitchLabels = controls.pitchLabels.checked;
      this._redrawCurrentFrame();
    });
    controls.overlay.addEventListener("change", () => {
      this._overlay = controls.overlay.checked;
      this._redrawCurrentFrame();
    });
    controls.birdseyeLabels.addEventListener("change", () => {
      this._birdseyeOverlay.setLabels(controls.birdseyeLabels.checked);
    });
    controls.birdseyeOverlay.addEventListener("change", () => {
      this._birdseyeOverlay.setVisible(controls.birdseyeOverlay.checked);
    });
    controls.keyboardTarget.addEventListener("keydown", (event) => {
      if (event.target.closest("input, select, button, a")) return;
      if (event.code === "Space") {
        event.preventDefault();
        this._togglePlayback();
      }
      if (event.code === "ArrowLeft" || event.code === "ArrowRight") {
        event.preventDefault();
        this._stepFrame(event.code === "ArrowLeft" ? -1 : 1);
      }
    });
  }

  _redrawCurrentFrame() {
    if (this._currentFrame >= 0 && !this._video.seeking) {
      this._displayFrame(this._currentFrame);
    }
  }

  /** @param {number} frame */
  _syncBirdseye(frame = this._frameAt(this._video.currentTime)) {
    if (this._video.seeking) return;
    this._birdseye.sync(
      frame,
      !this._video.paused && !this._video.ended,
      this._video.playbackRate,
    );
  }
}
