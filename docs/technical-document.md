# Technical document: possession labelling for Barcelona vs Athletic Club

Team: No Hala Madrid

## Summary

The submission labels each of the 199,319 tactical-video frames `H`, `A`, `D` or
`X`. It uses only the tracking data, the match metadata and the set-piece tags.
Possession comes from which team's players touch the ball and whether they keep it
or pass it on. Stoppages come from slow player movement, a ball beyond the lines
and set-piece tags. The method is deterministic, has no training step, and runs
in about 5 seconds. It is implemented in `src/pipelines/12_possession_touch`.

## Assets used and dropped

| Asset | Used | How or why not |
| --- | --- | --- |
| Tactical ATD (`BAR-ATH_tactical_atd.txt`) | Yes | Player and ball positions give touches, player speed and the ball's position relative to the lines. |
| EPTS metadata (`BAR-ATH_tactical_atd.xml`) | Yes | Frame rate, pitch size (105 × 68 m), slot-to-team mapping and frame count. |
| Smart Tagging (`BAR-ATH_tactical_smart_tagging.xml`) | Partly | Only the `SET PIECES` intervals, as a stoppage cue. The team tags and the other phases are not used, because phases are not possessions. |
| Tactical video, homography | No | The ATD is already in pitch coordinates, so neither is needed. |
| Broadcast video, ATD, homography | No | No mapping to the tactical frames is provided. |

No hand-labelled data is used. The public 5 minutes of ground truth is used to
score and sanity-check the pipeline. The private ground truth is not used.

Earlier attempts live in the repository as steps 05, 09, 10 and 11: a
nearest-player baseline, a continuity model, a control-confirmation model and a
model with dead-ball detection. A soft-evidence two-state model was tried and
dropped, because its score moved between 0.29 and 0.53 with its own settings.
Steps 07 and 08 measure tracking quality and are not inputs to the submission.

## Approach

### Timeline

The graded halves are frames 11185 to 90651 and 110808 to 190197. Frames outside
them are `X`. The second half is graded from 110808 but kicks off at 113742, so
frames 110808 to 113741 are `D`. Ownership restarts at each kick-off.

### Possession

A frame is a touch when the nearest tracked player is within 1.5 m of the ball.
Touches by the same team less than 1 s apart form one contact, so a short gap in
the ball track does not end it.

The team of the first contact in a half owns the ball. The other team takes
possession when one of its contacts either:

- lasts at least 1.5 s, because the player keeps the ball, or
- is followed by another touch from the same team within 3 s, because it
  completed a pass.

The change is dated to the first frame of that contact. Any other contact is a
touch without control and changes nothing. Ownership holds through any gap in
the ball track.

### Stoppages

Frames inside a stoppage are `D`. A stoppage is a run of at least 3 s that comes
from any of these cues:

- The mean speed of all tracked players, averaged over 3 s, is below 1.1 m/s. The
  stoppage lasts until that speed rises above 1.6 m/s.
- The ball is more than 0.5 m beyond the pitch lines for most of a 0.4 s window.
- The frame is inside a `SET PIECES` tag, starting 1 s early, and the 3 s player
  speed is below 1.6 m/s.

## Missing and noisy tracking

- The ball is missing on 41% of graded frames. Missing frames are never touches.
  Contacts bridge gaps of up to 1 s, and ownership holds through longer gaps.
- Tracking slots are not players. Slots appear, vanish and swap identity, so the
  method uses only team membership and distances, never a persistent player.
- A step faster than 12 m/s between consecutive frames is an identity switch. It
  is left out of the player speed.
- Unknown player speed never starts a stoppage. A frame missing from the source
  leaves its speed unknown.
- Positions are used as given, with no interpolation. Finite positions outside
  the pitch are kept, because they are the evidence for a ball beyond the lines.

## Possession rules implemented

- **Loose ball.** Possession stays with the last team that held it.
- **Challenge, deflection, aerial duel.** A single touch by the other team does
  not change possession. It changes only if that team keeps the ball for 1.5 s or
  touches it again within 3 s.
- **Restart.** The first team to touch the ball after kick-off owns it until the
  other team takes possession by the rule above. After other stoppages the previous owner keeps the
  ball until the other team takes it, so a restart by the other team is picked up
  by its first held or passed contact. The set-piece tag's team is not used.
- **Dead ball.** `D` is a detected stoppage. No owner is named for it.

## Results and how far to trust them

On the public 5 minutes (17 possessions), scored with the official metrics:

| Step | spellF1 | macroF1 | Possessions predicted |
| --- | --- | --- | --- |
| 05 nearest-player baseline | 0.3256 | 0.6207 | 26 |
| 09 continuity | 0.0441 | 0.4575 | 128 |
| 10 control confirmation | 0.3676 | 0.6479 | 20 |
| 11 ownership with dead ball | 0.4343 | 0.7775 | 18 |
| **12 touch ownership (submitted)** | **0.5333** | **0.8066** | **13** |

Seventeen possessions cannot rank methods. The bootstrap range for spellF1 is
0.29 to 0.58 for step 11 and 0.35 to 0.71 for step 12, so the ranges overlap.
Three checks make the improvement more likely to be real:

- Across 27 settings of touch distance, held-ball time and pass window, every one
  scored above step 11 on the public window.
- Over the whole match, step 12 predicts 272 possessions with a mean of 13.4 s.
  Step 11 predicts 394 with a mean of 9.3 s. The public ground truth has a mean of
  14.2 s.
- Where an automatic Smart Tagging phase names the team in possession, step 12
  agrees on 79.0% of frames and step 11 on 76.7%. Those tags come from the same
  tracking, so this checks consistency, not accuracy.

The settings come from the rule text and a sweep on the 17 public possessions.
The held-ball time matters most. Values of 1 s to 2 s score the same, and 3 s or
more falls to about the step 11 score.

## Limitations

- A handover without a touch of 1.5 s or a second touch within 3 s is missed.
  The method predicts 13 possessions on the public window where the ground truth
  has 17, and it merges two short true possessions into their neighbours.
- A touch needs the ball in the tracking. A real handover can leave no touch.
- Slow live play, such as a goalkeeper holding the ball, can be marked `D`. A dead
  ball while players still move quickly is missed.
- The timeline constants (kick-off and graded-half frames) are specific to this
  match. All other values are in `configuration/policy.py`.
- The dating of changes uses the future, so the output is an offline result.
- With more time: validate on more labelled minutes, use ball speed and direction
  to separate a deflection from a pass, and use the restart tag's team.

## Reproduction

Python 3.12 and [uv](https://docs.astral.sh/uv/) are required. Dependencies are
pinned in `uv.lock`. Place the organisers' tactical files under `data/tactical/`.

```bash
uv sync --frozen
source .venv/bin/activate

python -m src.pipelines.12_possession_touch \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --smart-tagging data/tactical/BAR-ATH_tactical_smart_tagging.xml \
  --output-dir output/submission
```

The run writes `output/submission/possession_touch.csv`, the submitted file, and a
metadata JSON. It refuses to overwrite, so use a fresh directory. Two runs produce
byte-identical CSVs. With pandas 3.0.6 and numpy 2.5.4 as locked, the file has this
SHA-256:

```text
c26870bcb1f1d62760e734b8e825af93aaf1a63e75dfd4c86b938e114f06e49e
```

It has 199,319 rows with 53,750 `H`, 37,486 `A`, 67,621 `D` and 40,462 `X`. The
organisers' `validate_submission.py` accepts it. To score it on the public window:

```bash
python -m src.pipelines.06_score_submission \
  --submission output/submission/possession_touch.csv \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --output-dir output/submission
```
