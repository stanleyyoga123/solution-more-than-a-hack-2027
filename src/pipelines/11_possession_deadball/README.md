# 11 — Ownership with dead-ball detection

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Step 11 labels every frame `H`, `A`, `D` or `X`. It keeps the team-ownership rule
of [step 10](../10_possession_control/README.md) and adds a stoppage detector, so
`D` means a detected stoppage instead of a missing ball. It is independent of
steps 01–10: it reads the raw ATD, the matching EPTS XML and the Smart Tagging XML.

## Run and score

From the repository root, with the project environment active:

```bash
python -m src.pipelines.11_possession_deadball \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --smart-tagging data/tactical/BAR-ATH_tactical_smart_tagging.xml \
  --output-dir output/possession-11

python -m src.pipelines.06_score_submission \
  --submission output/possession-11/possession_deadball.csv \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --output-dir output/possession-11
```

Each run writes `possession_deadball.csv` (`frame,label`, one row per
metadata-declared frame) and `possession_deadball.metadata.json` (policy, inputs,
runtime versions, label counts). Existing outputs are refused, so use a fresh
directory. Logs go to stderr and published paths to stdout.

## Method

**Timeline.** The published graded halves are frames 11185–90651 and
110808–190197. Frames outside them are `X`. The second half is graded from
110808 but kicks off at 113742, so frames 110808–113741 are `D`. Ownership
restarts at each kick-off.

**Ownership.** Same evidence and rule as step 10: a team controls the ball when
its nearest player is within 2 m, at least 0.5 m closer than the opposing
nearest player, and the ball moves at 12 m/s or less. An opposing team must
control for 0.4 s to take ownership, and the change is backdated to its first
frame. Unlike step 10, losing the ball never ends ownership. The incumbent holds
through any gap in the ball track until the opposing team is confirmed.

**Stoppages.** A frame is `D` inside a stoppage. A stoppage is a run of at least
3 s that comes from any of these cues:

- The mean speed of all tracked players, averaged over 3 s, is below 1.1 m/s.
  The stoppage lasts until that speed rises above 1.6 m/s. Steps faster than
  12 m/s are identity switches and are ignored.
- The ball is beyond the pitch lines by more than 0.5 m for most of 0.4 s.
- The frame is within an automatic set-piece tag, starting 1 s early, and the
  3 s player speed is below 1.6 m/s.

Unknown player speed never starts a stoppage. All values are in
`configuration/policy.py`.

## Limitations

- Slow live play, such as a keeper holding the ball, can be marked `D`. A dead
  ball while players still move quickly is missed.
- The speed cues were chosen from physical round numbers, and the public ground
  truth holds only four stoppages, so the thresholds are not validated.
- The timeline constants are specific to BAR-ATH.
- Nearest-player proximity is a possession proxy, and backdating makes the output
  an offline result.
- The restart team after a stoppage comes from proximity, not from the tag team.

## Code organization

```text
11_possession_deadball/
├── __main__.py                  # CLI arguments and logging
├── pipeline.py                  # Wiring, per-half timeline
├── configuration/policy.py      # Ownership, stoppage and timeline settings
├── models/possession_features.py
├── evidence/
│   ├── tracking_loader.py       # Proximity, ball position, player speed
│   └── set_piece_tags.py        # Smart Tagging set-piece frame windows
├── inference/
│   ├── ownership.py             # Candidate selection and ownership state
│   └── dead_ball.py             # Stoppage detection
└── export/submission.py         # Submission and sidecar serialization
```

Production imports use only this package and `src/utilities/`. Step 10's logic is
copied here, not imported, because pipelines may not depend on each other.

```bash
python -m pytest tests/src/pipelines/11_possession_deadball
python -m black --check src/pipelines/11_possession_deadball \
  tests/src/pipelines/11_possession_deadball
```
