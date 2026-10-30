# Synthetic standalone control recording

`tracking.txt` and `metadata.xml` describe 100 frames at 10 FPS on a 100 × 60 m
pitch with one tracking slot per team. Source frames are one-based; the expected
submission frames are zero-based. Raw speed is deliberately unrelated to motion.

The recording contains leading unknown evidence, home control, a short ball
occlusion, confirmed away control, an unsupported brief home challenge, a long
occlusion that expires the incumbent, and newly established home control. Its
last 20 frames retain home control of a stationary ball just outside the pitch.
It requires no licensed match assets.

`expected_intervals.json` contains half-open `[start, end, label]` intervals,
frozen from the playground's isolated control-candidate and control-confirmation
functions with default policy, an empty dead mask, and direct H/A/D label mapping.
No gap prefilling, vote smoothing or stoppage detection contributes to this
reference. The test suite reads static expectations without importing playground.
