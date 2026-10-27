import { clipFrameAtSourceFrame, sourceFrameAtClipTime } from "./clip_timeline.js";
import { frameAtTime, frameSeekTime } from "./timeline.js";

/** Keep rendered footage following the source clock and hide stale frames. */
export class BirdseyePlayback {
  /**
   * @param {HTMLVideoElement} video
   * @param {HTMLElement} status
   * @param {import('./tracking_types.js').BirdseyeMetadata | null} clip
   * @param {number} sourceFps
   * @param {(sourceFrame: number | null) => void} onFrame
   */
  constructor(video, status, clip, sourceFps, onFrame) {
    this._video = video;
    this._status = status;
    this._clip = clip;
    this._sourceFps = sourceFps;
    this._onFrame = onFrame;
    /** @type {number | null} */
    this._targetFrame = null;
    /** @type {number | null} */
    this._decodedSourceFrame = null;
    /** @type {number | null} */
    this._reportedFrame = null;
    this._loaded = false;
    this._playing = false;
    this._buffering = false;
    this._failed = false;
    this._playPending = false;
    this._playBlocked = false;
    this._intentVersion = 0;
  }

  start() {
    this._video.muted = true;
    this._onFrame(null);
    this._hide("Loading bird’s-eye footage…", "loading");
    if (this._clip === null) {
      this._hide("Render pipeline 04 to add bird’s-eye footage.", "unavailable");
      return;
    }
    this._video.addEventListener("loadedmetadata", () => {
      this._loaded = true;
      this._align();
    });
    this._video.addEventListener("seeked", () => {
      if (!this._playing) {
        this._decodedSourceFrame = this._pausedSourceFrame();
      }
      this._align();
    });
    this._video.addEventListener("canplay", () => {
      this._buffering = false;
      this._align();
    });
    this._video.addEventListener("waiting", () => {
      if (this._failed) return;
      this._buffering = true;
      this._hide("Buffering bird’s-eye footage…", "loading");
    });
    this._video.addEventListener("error", () => {
      this._failed = true;
      this._intentVersion += 1;
      this._playing = false;
      this._targetFrame = null;
      this._video.pause();
      this._hide("Cannot load bird’s-eye footage. Check the video path and reload.", "error");
    });
    this._requestVideoFrame();
    this._video.src = this._clip.video_url;
  }

  /**
   * Follow a decoded source frame; the source video owns playback state.
   * @param {number} sourceFrame
   * @param {boolean} playing
   * @param {number} playbackRate
   */
  sync(sourceFrame, playing, playbackRate) {
    if (this._failed) return;
    if (playing !== this._playing) this._intentVersion += 1;
    if (!playing || !this._playing) this._playBlocked = false;
    this._playing = playing;
    this._video.playbackRate = playbackRate;
    if (this._clip === null) return;
    this._targetFrame = clipFrameAtSourceFrame(sourceFrame, this._sourceFps, this._clip);
    if (this._targetFrame === null) {
      this._intentVersion += 1;
      this._video.pause();
      this._hide("This source frame is outside the rendered clip.", "unavailable");
      return;
    }
    this._align();
  }

  /**
   * Hide the previous image while the source is seeking, buffering or unavailable.
   * @param {string} message
   */
  suspend(message) {
    this._intentVersion += 1;
    this._playing = false;
    this._targetFrame = null;
    this._decodedSourceFrame = null;
    this._video.pause();
    if (this._clip !== null && !this._failed) this._hide(message, "loading");
  }

  _align() {
    if (this._targetFrame === null || this._failed || this._clip === null) return;
    if (!this._loaded) {
      this._hide("Loading bird’s-eye footage…", "loading");
      return;
    }
    if (this._video.seeking) {
      this._decodedSourceFrame = null;
      this._hide("Synchronizing bird’s-eye footage…", "loading");
      return;
    }
    const current = frameAtTime(
      this._video.currentTime,
      this._clip.fps,
      this._clip.frame_count,
    );
    const tolerance = this._playing ? 1 : 0;
    if (Math.abs(current - this._targetFrame) > tolerance) {
      if (!this._playing) this._video.pause();
      this._decodedSourceFrame = null;
      this._hide("Synchronizing bird’s-eye footage…", "loading");
      this._video.currentTime = frameSeekTime(this._targetFrame, this._clip.fps);
      return;
    }
    if (this._buffering || this._video.readyState < 2) {
      this._hide("Buffering bird’s-eye footage…", "loading");
      return;
    }
    if (this._playBlocked) return;
    this._video.hidden = false;
    this._status.hidden = true;
    this._status.dataset.state = "ready";
    if (!this._playing && this._decodedSourceFrame === null) {
      this._decodedSourceFrame = this._pausedSourceFrame();
    }
    this._publishFrame();
    if (!this._playing) {
      this._video.pause();
    } else if (this._video.paused && !this._playPending) {
      this._play();
    }
  }

  _pausedSourceFrame() {
    const seconds = this._video.ended
      ? frameSeekTime(this._clip.frame_count - 1, this._clip.fps)
      : this._video.currentTime;
    return sourceFrameAtClipTime(seconds, this._sourceFps, this._clip);
  }

  _requestVideoFrame() {
    this._video.requestVideoFrameCallback((_, details) => {
      this._decodedSourceFrame = sourceFrameAtClipTime(
        details.mediaTime,
        this._sourceFps,
        this._clip,
      );
      this._publishFrame();
      this._requestVideoFrame();
    });
  }

  _publishFrame() {
    const hidden = this._video.hidden || this._video.seeking || this._failed;
    const frame = hidden ? null : this._decodedSourceFrame;
    if (frame === this._reportedFrame) return;
    this._reportedFrame = frame;
    this._onFrame(frame);
  }

  async _play() {
    this._playPending = true;
    const version = this._intentVersion;
    try {
      await this._video.play();
    } catch (error) {
      // A newer seek or pause can cancel an outstanding play request normally.
      const currentRequest = version === this._intentVersion;
      if (error.name !== "AbortError" && currentRequest && this._playing) {
        this._playBlocked = true;
        this._hide("Bird’s-eye playback could not start. Pause and play to retry.", "error");
      }
    } finally {
      this._playPending = false;
      if (!this._playing || this._targetFrame === null) this._video.pause();
    }
  }

  /** @param {string} message @param {'loading' | 'unavailable' | 'error'} state */
  _hide(message, state) {
    this._video.hidden = true;
    this._publishFrame();
    this._status.hidden = false;
    this._status.textContent = message;
    this._status.dataset.state = state;
  }
}
