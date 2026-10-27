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
 * @typedef {Object} RecordingMetadata
 * @property {number} fps
 * @property {number} frame_count
 * @property {{length: number, width: number, unit: string}} pitch_dimensions
 * @property {Record<string, string>} teams
 * @property {string} video_url
 * @property {number} video_width
 * @property {number} video_height
 * @property {number} default_frame
 *
 * @typedef {Object} ViewerControls
 * @property {HTMLButtonElement} play
 * @property {HTMLButtonElement} previous
 * @property {HTMLButtonElement} next
 * @property {HTMLButtonElement} kickoff
 * @property {HTMLInputElement} timeline
 * @property {HTMLInputElement} frame
 * @property {HTMLSelectElement} speed
 * @property {HTMLInputElement} labels
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
 * @property {RecordingMetadata} metadata
 */
export {};
