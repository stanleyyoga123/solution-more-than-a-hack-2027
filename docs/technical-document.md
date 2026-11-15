# Technical document: possession labelling for Barcelona vs Athletic Club

Team: NO HALA MADRID

## Summary

The submission uses pipeline 11, `src/pipelines/11_possession_deadball`, to label
all 199,319 tactical-video frames as home possession (`H`), away possession (`A`),
dead ball (`D`) or outside the graded halves (`X`). Barcelona is the home team.
The method combines nearest-player proximity, sustained control and a separate
stoppage detector. It holds ownership through loose balls and missing tracking,
and changes the owner only after sustained evidence for the opposing team.

This is a deterministic rule-based algorithm with no training step. It uses raw
tactical tracking, EPTS metadata and automatic set-piece tags. The submission run
on 15 November 2026 took approximately 8 seconds on the local machine.

## Assets and training data

| Asset | Use |
| --- | --- |
| Tactical ATD (`BAR-ATH_tactical_atd.txt`) | Player and ball positions provide team distances, ball speed, player activity and evidence that the ball is outside the pitch. |
| EPTS metadata (`BAR-ATH_tactical_atd.xml`) | Provides frame rate (25 fps), pitch dimensions (105 × 68 m), slot-to-team mapping and frame count. |
| Smart Tagging (`BAR-ATH_tactical_smart_tagging.xml`) | Only automatic `SET PIECES` intervals are used, as a stoppage cue. Tag team labels and other phases are not used. |
| Tactical video and homography | Not inputs to pipeline 11; tracking coordinates already describe positions on the pitch. |
| Broadcast video, tracking and homography | Not inputs; the submission uses the tactical timeline. |

No labelled dataset is used to train this algorithm. The organisers' public
five-minute ground truth is used for evaluation; it is not read by inference.
The private ground truth is not used. The numeric settings are fixed in
`configuration/policy.py`; the pipeline README describes the speed thresholds as
physical round-number choices, not validated estimates.

Other approaches remain in the repository, including nearest-player baseline
(step 05), continuity (step 09), control confirmation (step 10) and touch-based
ownership (step 12). The submitted CSV comes from step 11. No other pipeline is
called or imported by it. Tracking-quality diagnostics in steps 07 and 08 are
also not inputs.

## Approach

### Tracking and timeline

The reader converts each ATD frame ID to a zero-based index by subtracting one.
It converts normalised x/y coordinates to metres using the metadata pitch size.
Each output row corresponds to a tactical-video frame.

The configured graded halves are frames 11185–90651 and 110808–190197,
inclusive. Frames outside these intervals are `X`. The second half kicks off at
113742, so frames 110808–113741 are `D`. Ownership starts afresh at each
kick-off; it does not carry across halftime.

### Team ownership

For each frame, the algorithm finds the nearest observed player from each team
to the ball. A team is a control candidate when:

- its nearest player is within 2 m of the ball;
- that player is at least 0.5 m closer than the opposing team's nearest player;
- the ball's measured speed is at most 12 m/s, or its speed is unavailable.

Ball speed is displacement between consecutive observed frames multiplied by
frame rate. A missing speed does not veto an otherwise valid candidate. If the
opposing team has no observed distance, its distance is treated as infinite.

At the start of each half, the first frame with an observed ball and a player
initialises ownership to the nearest player's team. This initial choice does
not require the control thresholds. Before that observation, the output is `D`.
Equal nearest-player distances are resolved by tracking slot order.

Once an owner exists, the opposing team must be a control candidate for 0.4 s
(10 consecutive frames at 25 fps) to take ownership. Confirmation backdates the
change to the first frame of that run. An interruption resets the pending
confirmation. Otherwise, the incumbent retains ownership, including through
arbitrarily long gaps in the ball track.

This separates proximity from a confirmed change of possession: a brief
challenge does not automatically transfer ownership, and losing sight of the
ball does not automatically end it.

### Dead-ball detection

The detector combines three cues:

1. **Low player activity.** Per-frame activity is the mean speed of tracked
   player slots between consecutive frames, excluding steps above 12 m/s. A
   centred 3 s moving average smooths this signal. The low-activity state starts
   below 1.1 m/s and persists until activity exceeds 1.6 m/s or is unknown.
2. **Ball outside the pitch.** The ball is more than 0.5 m beyond a pitch
   boundary in over half the frames of a centred 0.4 s window.
3. **Set-piece interval.** The frame lies in an automatic `SET PIECES` interval,
   extended 1 s earlier, and smoothed player activity is below 1.6 m/s.

The activity average requires at least 15 observed activity samples in its
75-frame window. Set-piece timestamps are converted from seconds to frames by
rounding; interval ends are exclusive.

The three masks are combined, then contiguous detected runs shorter than 3 s
(75 frames) are removed. Thus the minimum duration applies to the combined
mask, not to each cue independently. Within the post-kick-off graded timeline,
a retained stoppage overrides the ownership label with `D`.

Ownership inference continues beneath this mask. A stoppage does not reset the
owner or assign the restart team from the tag. When the stoppage ends, the
underlying ownership prediction becomes visible again.

## Missing and noisy observations

Missing ball or player positions cannot provide a control candidate. They reset
an opposing team's pending confirmation but do not clear established ownership.
Before any owner has been observed in a half, unavailable ownership is labelled
`D`; consequently, not every `D` frame is a positively detected stoppage.

No positions are interpolated. Finite off-pitch positions are retained for the
boundary cue. Ball speed requires consecutive frames with observed ball
positions. Player speeds also require consecutive frames; steps above 12 m/s
are discarded as likely slot changes or tracking noise. Shorter slot changes
can still affect the activity estimate. Unknown smoothed activity cannot start
a low-activity or tag-based stoppage, although the boundary cue can still apply.

Distances use team membership rather than a persistent player identity. Slot
continuity is used only to estimate player movement between adjacent frames.

## Possession rules implemented

- **Loose ball or missing ball.** Keep the incumbent owner until the opposition
  satisfies the confirmation rule.
- **Challenge, deflection or aerial duel.** Transfer ownership only after 10
  consecutive qualifying control frames. Ball speeds above 12 m/s prevent a
  candidate when speed is observed.
- **Kick-off.** Initialise from the nearest observed player's team independently
  in each half.
- **Other restarts.** Retain the underlying ownership state, allowing confirmed
  switches during a stoppage. Do not use the set-piece tag's team.
- **Dead ball.** Display `D` over detected stoppages and the configured second-half
  pre-kick-off interval, as well as frames awaiting initial ownership.

## Evaluation

The exact submission CSV was scored against the organisers' public ground truth
with pipeline 06 on 15 November 2026. This covers 7,500 graded frames (five
minutes) and 17 reference possessions.

| Measure | Pipeline 11 |
| --- | ---: |
| spellF1 | 0.4343 |
| macroF1 | 0.7775 |
| Predicted possessions in the public window | 18 |
| Reference possessions in the public window | 17 |

The organiser's format validator also accepted the exact team-named CSV. Across
that file, it reports 394 possessions averaging 9.3 s, treating `X` as a gap.
These whole-file statistics describe the predictions, not their accuracy.

The public window is too small to establish whole-match accuracy. Format
validation establishes that the file can be scored; it does not validate the
possession decisions or the stoppage thresholds.

## Limitations

- Proximity is a proxy for control. A nearby player may not actually control the
  ball, and the initial owner does not have to pass a distance threshold.
- A genuine turnover may be missed if ball tracking is absent or the opposition
  never supplies 10 consecutive qualifying frames. The previous owner can then
  persist too long.
- Unknown ball speed is allowed, which avoids rejecting intermittent tracking
  but can admit a control candidate during fast ball movement.
- Slow live play, such as a goalkeeper holding the ball, can be marked `D`.
  Stoppages with moving players can be missed, and detected runs shorter than
  3 s are discarded.
- Ownership can change during a detected stoppage because the two inference
  stages run independently. Restart ownership is not explicitly modelled.
- Kick-off and graded-half constants are specific to this match. Centred windows
  and backdated changes use future observations, so this is an offline method.
- Further work would evaluate the rules on independent labelled matches and
  improve turnover and restart inference when ball observations are sparse.

## Reproduction and submission

Use Python 3.12 and the dependencies pinned in `uv.lock`. Place the organisers'
three tactical input files under `data/tactical/`. From the repository root:

```bash
uv sync --frozen
source .venv/bin/activate

python -m src.pipelines.11_possession_deadball \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --smart-tagging data/tactical/BAR-ATH_tactical_smart_tagging.xml \
  --output-dir output/submission-pipeline11

cp -n output/submission-pipeline11/possession_deadball.csv \
  'output/submission-pipeline11/NO HALA MADRID.csv'
```

The pipeline writes `possession_deadball.csv` and
`possession_deadball.metadata.json`. Existing pipeline outputs are refused, so
use a fresh output directory for another run. The JSON records policy settings,
input paths, runtime information and label counts; only the team-named CSV is
uploaded in the possession-file field.

The submission was produced with Python 3.12.14, NumPy 2.5.4 and pandas 3.0.6.
The CSV has the header `frame,label`, followed by 199,319 rows numbered 0–199318:

| Label | Rows |
| --- | ---: |
| H | 53,050 |
| A | 38,186 |
| D | 67,621 |
| X | 40,462 |

The submission run and the earlier stored pipeline 11 CSV are byte-identical.
The SHA-256 of `NO HALA MADRID.csv` is:

```text
3b893cf7f843bbb271b5ccd19c45db83f9eb421f421285afe11ac730e38d7aee
```

To reproduce the public-window evaluation separately:

```bash
python -m src.pipelines.06_score_submission \
  --submission 'output/submission-pipeline11/NO HALA MADRID.csv' \
  --ground-truth data/BAR-ATH_possession_gt_public.csv \
  --output-dir output/submission-pipeline11
```

Run the organisers' `evaluation/validate_submission.py` from their repository
against the exact CSV before uploading it. That validator is not included in
this repository. Submit this document as `NO HALA MADRID.md` alongside the CSV
and the public code repository URL. Match assets and generated exports must
remain outside the public repository.
