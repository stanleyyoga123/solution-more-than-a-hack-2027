import { TrackingClient } from "./viewer/tracking_client.js";
import { FrameCache } from "./viewer/frame_cache.js";
import { CameraRenderer } from "./viewer/camera_renderer.js";
import { PitchRenderer } from "./viewer/pitch_renderer.js";
import { ViewerController } from "./viewer/viewer_controller.js";
import { ViewerView } from "./viewer/viewer_view.js";
import { teamColours } from "./viewer/entity_markers.js";

async function startViewer() {
  const view = new ViewerView(document);
  const client = new TrackingClient(window.fetch.bind(window));
  try {
    const metadata = await client.metadata();
    const colours = teamColours(metadata.teams);
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
      overlay: document.querySelector("#show-overlay"),
      keyboardTarget: document,
    };
    const controller = new ViewerController({
      video, controls, view, camera, pitch, metadata,
      cache: new FrameCache(client, metadata.frame_count),
    });
    controller.start();
  } catch (error) {
    view.showStatus(`${error.message} Check the local server and reload this page.`, "error");
  }
}

startViewer();
