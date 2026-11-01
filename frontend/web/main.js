import { mountDiagnostics } from "./diagnostics.js";
import { setupNavigation } from "./navigation.js";
import { mountExperiments } from "./experiments/dashboard.js";
import { TrackingClient } from "./viewer/tracking_client.js";
import { FrameCache } from "./viewer/frame_cache.js";
import { CameraRenderer } from "./viewer/camera_renderer.js";
import { PitchRenderer } from "./viewer/pitch_renderer.js";
import { ViewerController } from "./viewer/viewer_controller.js";
import { ViewerView } from "./viewer/viewer_view.js";
import { BirdseyePlayback } from "./viewer/birdseye_playback.js";
import { BirdseyeOverlay } from "./viewer/birdseye_overlay.js";
import { BirdseyeOverlayRenderer } from "./viewer/birdseye_overlay_renderer.js";
import { teamColours } from "./viewer/entity_markers.js";
import { QualityReviewController } from "./viewer/quality_review_controller.js";
import { QualityReviewView } from "./viewer/quality_review_view.js";
import { QualityTimeline } from "./viewer/quality_timeline.js";

async function startViewer() {
  const view = new ViewerView(document);
  const client = new TrackingClient(window.fetch.bind(window));
  try {
    const metadata = await client.metadata();
    const colours = teamColours(metadata.teams);
    const cache = new FrameCache(client, metadata.frame_count);
    const video = document.querySelector("#source-video");
    video.parentElement.style.aspectRatio = `${metadata.video_width} / ${metadata.video_height}`;
    view.initialize(metadata, colours);
    const camera = new CameraRenderer(
      document.querySelector("#camera-overlay"),
      metadata.video_width,
      metadata.video_height,
      colours,
    );
    const pitch = new PitchRenderer(
      document.querySelector("#pitch-map"),
      metadata.pitch_dimensions,
      colours,
    );
    const birdseyeOverlay = new BirdseyeOverlay(
      new BirdseyeOverlayRenderer(
        document.querySelector("#birdseye-overlay"),
        metadata.pitch_dimensions,
        metadata.birdseye,
        colours,
      ),
      cache,
    );
    const birdseye = new BirdseyePlayback(
      document.querySelector("#birdseye-video"),
      document.querySelector("#birdseye-status"),
      metadata.birdseye,
      metadata.fps,
      (frame) => birdseyeOverlay.showFrame(frame),
    );
    const controls = {
      play: document.querySelector("#play-pause"),
      previous: document.querySelector("#previous-frame"),
      next: document.querySelector("#next-frame"),
      kickoff: document.querySelector("#kickoff"),
      timeline: document.querySelector("#timeline"),
      frame: document.querySelector("#frame-input"),
      speed: document.querySelector("#playback-speed"),
      cameraLabels: document.querySelector("#show-camera-labels"),
      pitchLabels: document.querySelector("#show-pitch-labels"),
      birdseyeLabels: document.querySelector("#show-birdseye-labels"),
      birdseyeOverlay: document.querySelector("#show-birdseye-overlay"),
      overlay: document.querySelector("#show-overlay"),
      keyboardTarget: document,
      isActive: () => !document.querySelector("#tracking-panel").hidden,
    };
    const qualityReview = new QualityReviewController(
      client,
      new QualityReviewView(document.querySelector("#quality-review"), metadata.fps),
      new QualityTimeline(document.querySelector("#quality-timeline"), metadata.frame_count),
      (frame) => controller.seek(frame),
      (entityId) => controller.highlightEntity(entityId),
    );
    const controller = new ViewerController({
      video, controls, view, camera, pitch, birdseye, birdseyeOverlay, metadata, cache,
      qualityReview,
    });
    controller.start();
    qualityReview.start();
  } catch (error) {
    view.showStatus(`${error.message} Check the local server and reload this page.`, "error");
  }
}

const experiments = mountExperiments(document.querySelector("#experiments-panel"));
const diagnostics = mountDiagnostics(document.querySelector("#diagnostics-panel"));
setupNavigation(document, {
  openDiagnostics: () => diagnostics.open(),
  leaveTracking: () => document.querySelector("#source-video").pause(),
  openExperiments: () => experiments.open(),
});
startViewer();
