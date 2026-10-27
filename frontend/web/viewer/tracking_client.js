/** HTTP boundary for the local recording API. */
export class TrackingClient {
  /** @param {typeof fetch} fetchRequest */
  constructor(fetchRequest) {
    this._fetch = fetchRequest;
  }

  /** @returns {Promise<import('./tracking_types.js').RecordingMetadata>} */
  async metadata() {
    const response = await this._fetch("/api/metadata");
    if (!response.ok) {
      throw new Error(`Cannot load recording metadata (HTTP ${response.status}).`);
    }
    return response.json();
  }

  /** @returns {Promise<import('./quality_types.js').QualityPayload>} */
  async quality() {
    const response = await this._fetch("/api/quality");
    if (!response.ok) {
      throw new Error(`Cannot load quality reports (HTTP ${response.status}).`);
    }
    return response.json();
  }

  /** @returns {Promise<import('./prediction_types.js').PredictionPayload>} */
  async predictions() {
    const response = await this._fetch("/api/predictions");
    if (!response.ok) {
      throw new Error(`Cannot load predictions (HTTP ${response.status}).`);
    }
    return response.json();
  }

  /**
   * @param {number} start
   * @param {number} count
   * @returns {Promise<import('./tracking_types.js').TrackingFrame[]>}
   */
  async frames(start, count) {
    const response = await this._fetch(`/api/frames?start=${start}&count=${count}`);
    if (!response.ok) {
      throw new Error(`Cannot load tracking positions (HTTP ${response.status}).`);
    }
    const payload = await response.json();
    return payload.frames;
  }
}
