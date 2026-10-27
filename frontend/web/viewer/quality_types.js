/**
 * @typedef {Object} MotionEpisode
 * @property {string} id
 * @property {'motion'} kind
 * @property {string} entity_id
 * @property {'player'|'ball'} entity_type
 * @property {string} team_id
 * @property {number} start_frame
 * @property {number} end_frame
 * @property {number} peak_frame
 * @property {number} peak_speed_mps
 * @property {number|null} peak_acceleration_mps2
 * @property {boolean} speed_flag
 * @property {boolean} acceleration_flag
 * @property {number} sample_count
 *
 * @typedef {Object} GapAssessment
 * @property {string} id
 * @property {'gap'} kind
 * @property {string} entity_id
 * @property {'player'|'ball'} entity_type
 * @property {string} team_id
 * @property {number} start_frame
 * @property {number} end_frame
 * @property {number} missing_frames
 * @property {number} gap_seconds
 * @property {number|null} left_frame
 * @property {number|null} right_frame
 * @property {number|null} endpoint_distance_m
 * @property {number|null} required_speed_mps
 * @property {number|null} forward_error_m
 * @property {number|null} backward_error_m
 * @property {'plausible'|'implausible'|'uncertain'} status
 * @property {string} reason
 *
 * @typedef {MotionEpisode|GapAssessment} QualityEvent
 *
 * @typedef {Object} QualityPayload
 * @property {{trajectories:boolean,gaps:boolean}} available
 * @property {{flagged_samples:number,trajectory_episodes:number,gap_count:number,
 * status_counts:{plausible:number,implausible:number,uncertain:number}}} summary
 * @property {Omit<MotionEpisode,'kind'>[]} episodes
 * @property {Omit<GapAssessment,'kind'>[]} gaps
 */
export {};
