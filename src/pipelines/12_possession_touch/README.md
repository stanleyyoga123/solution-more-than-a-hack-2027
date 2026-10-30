# 12 — Touch-based ownership with dead-ball detection

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Step 12 labels every frame `H`, `A`, `D` or `X`. It keeps the stoppage detector of
[step 11](../11_possession_deadball/README.md) and replaces its ownership rule.
Step 11 hands the ball over after 0.4 s of closer opposing proximity, so a tackle,
a deflection or a pass through traffic splits one possession into several. Step 12
follows the rule in the organisers' challenge text: a single touch is not a change
of possession, and the opposing team needs to keep the ball or pass it on. It is
independent of steps 01–11: it reads the raw ATD, the matching EPTS XML and the
Smart Tagging XML.

## Run and score

From the repository root, with the project environment active:

```bash
python -m src.pipelines.12_possession_touch \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --smart-tagging data/tactical/BAR-ATH_tactical_smart_tagging.xml \
  --output-dir output/possession-12

python -m src.pipelines.06_score_submission \
  --submission output/possession-12/possession_touch.csv \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --output-dir output/possession-12
```

Each run writes `possession_touch.csv` (`frame,label`, one row per metadata-declared
frame) and `possession_touch.metadata.json` (policy, inputs, runtime versions, label
counts). Existing outputs are refused, so use a fresh directory. Logs go to stderr and
published paths to stdout.

## Method

**Timeline.** Same as step 11. The graded halves are frames 11185–90651 and
110808–190197, and frames outside them are `X`. The second half is graded from
110808 but kicks off at 113742, so frames 110808–113741 are `D`. Ownership restarts
at each kick-off.

**Touches.** A frame is a touch when the nearest tracked player is within 1.5 m of
the ball. Touches by the same team less than 1 s apart form one contact, so a ball
that drops out of the tracking for a moment does not end it.

**Ownership.** The team of the first contact owns the half. A contact by the other
team takes possession when either:

- it lasts at least 1.5 s, because the player keeps the ball, or
- the same team touches the ball again within 3 s of the contact ending, because
  it completed a pass.

Other contacts are touches without control and change nothing. A change is dated to
the first frame of the contact that takes possession, and ownership holds through any
gap in the ball track.

**Stoppages.** Unchanged from step 11: a run of at least 3 s where the mean player
speed over 3 s stays below 1.1 m/s until it exceeds 1.6 m/s, where the ball is more
than 0.5 m beyond the lines, or where a set-piece tag from 1 s early overlaps slow play.
Stoppage frames are `D`. All values are in `configuration/policy.py`.

## Results

On the public 5 minutes (17 possessions), scored by step 06:

| Step | spellF1 | macroF1 | Predicted possessions |
| --- | --- | --- | --- |
| 05 baseline | 0.3256 | 0.6207 | 26 |
| 11 ownership and dead ball | 0.4343 | 0.7775 | 18 |
| 12 touch ownership and dead ball | 0.5333 | 0.8066 | 13 |

Read this with care. The 5-minute bootstrap interval for spellF1 is 0.29–0.58 for
step 11 and 0.35–0.71 for step 12, so the public score alone does not show that step
12 is better. These sweeps show how much depends on the settings:

- Across 27 combinations of touch distance (1.2, 1.5, 2 m), held-ball time (0.6, 1,
  1.5 s) and pass window (2, 3, 5 s), every one scored above step 11 on the public
  window: 0.44 to 0.58, median about 0.50. The weakest is only just above step 11.
- Held-ball time is the setting that matters. spellF1 is 0.47 at 0.5 s, 0.53 at 1 s,
  1.5 s and 2 s, and 0.43 at 3 s or more, level with step 11. 1.5 s sits on the
  plateau and reads the rule's "a few seconds" literally.
- Each rule needs the other. Held-ball time alone scores 0.39, the pass rule alone
  0.41, and letting every touch change possession 0.27.

Over the whole match step 12 predicts 272 possessions with a mean of 13.4 s, against
394 and 9.3 s for step 11. The public ground truth has a mean of 14.2 s. Where an
automatic Smart Tagging phase names the team in possession, step 12 agrees on 79.0%
of frames and step 11 on 76.7%. Those tags come from the same tracking, so this is a
consistency check and not an accuracy measure.

## Limitations

- A pass that changes hands without the receiver being within 1.5 m for at least
  1.5 s, or touching twice within 3 s, is missed. Step 12 predicts 13 possessions
  where the public ground truth has 17, and merges two short truth possessions
  (8 s and 3 s) into their neighbours.
- A touch needs the ball in the tracking. The ball is missing on 41% of graded
  frames, so a real handover can leave no touch at all.
- The settings were chosen from the physical rule text and a sweep on 17
  possessions. The public window cannot rank them, so treat 1.5 s and 3 s as
  starting points.
- Slow live play, such as a keeper holding the ball, can be marked `D`. A dead
  ball while players still move quickly is missed.
- Timeline constants are specific to BAR-ATH, and the offline dating of changes uses
  the future.

## Code organization

```text
12_possession_touch/
├── __main__.py                  # CLI arguments and logging
├── pipeline.py                  # Wiring, per-half timeline
├── configuration/policy.py      # Touch, stoppage and timeline settings
├── models/possession_features.py
├── evidence/
│   ├── tracking_loader.py       # Proximity, ball position, player speed
│   └── set_piece_tags.py        # Smart Tagging set-piece frame windows
├── inference/
│   ├── ownership.py             # Contacts and possession changes
│   └── dead_ball.py             # Stoppage detection
└── export/submission.py         # Submission and sidecar serialization
```

Production imports use only this package and `src/utilities/`. Step 11's evidence and
stoppage code is copied here, not imported, because pipelines may not depend on each
other.

```bash
python -m pytest tests/src/pipelines/12_possession_touch
python -m black --check src/pipelines/12_possession_touch \
  tests/src/pipelines/12_possession_touch tests/fixtures/possession_touch.py
```
