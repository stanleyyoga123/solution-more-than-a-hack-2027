# Synthetic registry demonstration

These four hand-authored frames and Pipeline 05-shaped metadata are synthetic.
No tracking dataset or algorithm execution produced them. The score fixture
illustrates a perfect prediction against the same four-frame CSV, with two team
possessions (lengths two and one frames) and a mean duration of 0.06 seconds at
25 FPS. It is not evidence of Pipeline 05 performance.

The evaluator identity in the sample manifest explicitly says
`hand-authored-synthetic-fixture`. Unit tests also construct schema-shaped 09,
10 and 11 examples in `tests/fixtures/experiment_tracking.py`.
