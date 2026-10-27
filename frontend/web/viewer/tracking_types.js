/**
 * @typedef {Object} Observation
 * @property {string} entity_id
 * @property {"player" | "ball"} entity_type
 * @property {string} team_id
 * @property {number} pos_x
 * @property {number} pos_y
 *
 * @typedef {Object} TrackingFrame
 * @property {number} frame
 * @property {Observation[]} pixels
 * @property {Observation[]} normalized
 *
 * @typedef {Object} BirdseyeMetadata
 * @property {string} video_url
 * @property {number} width
 * @property {number} height
 * @property {number} fps
 * @property {number} frame_count
 * @property {number} start_frame
 *
 * @typedef {Object} RecordingMetadata
 * @property {number} fps
 * @property {number} frame_count
 * @property {{length: number, width: number, unit: string}} pitch_dimensions
 * @property {Record<string, string>} teams
 * @property {string} video_url
 * @property {number} video_width
 * @property {number} video_height
 * @property {number} default_frame
 * @property {BirdseyeMetadata | null} birdseye
 *
 * @typedef {Object} ViewerControls
 * @property {HTMLButtonElement} play
 * @property {HTMLButtonElement} previous
 * @property {HTMLButtonElement} next
 * @property {HTMLButtonElement} kickoff
 * @property {HTMLInputElement} timeline
 * @property {HTMLInputElement} frame
 * @property {HTMLSelectElement} speed
 * @property {HTMLInputElement} cameraLabels
 * @property {HTMLInputElement} pitchLabels
 * @property {HTMLInputElement} birdseyeLabels
 * @property {HTMLInputElement} birdseyeOverlay
 * @property {HTMLInputElement} overlay
 * @property {Document} keyboardTarget
 *
 * @typedef {Object} ViewerDependencies
 * @property {HTMLVideoElement} video
 * @property {ViewerControls} controls
 * @property {import('./viewer_view.js').ViewerView} view
 * @property {import('./frame_cache.js').FrameCache} cache
 * @property {import('./camera_renderer.js').CameraRenderer} camera
 * @property {import('./pitch_renderer.js').PitchRenderer} pitch
 * @property {import('./birdseye_playback.js').BirdseyePlayback} birdseye
 * @property {import('./birdseye_overlay.js').BirdseyeOverlay} birdseyeOverlay
 * @property {RecordingMetadata} metadata
 */
export {};
