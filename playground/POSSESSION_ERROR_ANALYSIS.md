# Possession error diagnosis and algorithm fixes

## Result and selected candidate

The strongest interval-scoring candidate from this investigation is **p07**, which
adds collective-stoppage detection and bounded retention to f03:

| Candidate | spellF1 | macroF1 | False-turnover errors / 125 | Stoppage errors / 511 |
| --- | ---: | ---: | ---: | ---: |
| Previous f03 | 0.545455 | 0.702514 | 125 | 511 |
| p07: collective stoppage retention | **0.612500** | 0.817409 | 125 | **20** |
| q05: goalkeeper quarantine plus stoppages | 0.554839 | **0.836143** | **0** | 22 |
| t05: segmented goalkeeper quarantine plus stoppages | 0.554839 | **0.836143** | **0** | 22 |

p07 improves spellF1 by 0.067045 (6.70 percentage points) and macroF1 by
0.114895 (11.49 points) against f03. It corrects 491 graded frames and introduces
nine errors, reducing total wrong frames from 1,723 to 1,241 out of 7,500.
It changes 18,896 labels over the entire recording; unlabelled changes are not
validated by these scores. The current `output/prediction.csv` is preserved.

The identity correction fixes the targeted false home possession, confirming
its data-quality mechanism, but worsens interval scoring elsewhere. It remains
an experiment and is not included in the strongest spellF1 candidate.

## Investigated intervals and evidence

Times below use the original tactical video at 25 fps, not the displayed match
clock. Frame intervals are zero-based and end-exclusive.

- False home possession: **[15641, 15766), 10:25.64–10:30.64**. Public label A;
  f03 predicts H for all 125 frames.
- Missed stoppage: **[15889, 16400), 10:35.56–10:56.00**. Public label D;
  f03 predicts A, then H, then A for all 511 frames.

Source evidence includes original ATD and XML, a full numerical trace in
`possession_fixes_002/evidence.csv`, Smart Tags, sampled tactical-video frames,
and projected tracking overlays. Local video illustrations are in
`playground/artifacts/possession_diagnosis_001/`: `turnover.jpg`, `stoppage.jpg`,
`ball_projection.jpg`, and `player_projection.jpg`. These match-derived files
are ignored by Git; the prose records aggregate findings rather than embedding
gated footage in the repository.

## Root cause 1: an identity discontinuity contaminates control evidence

The first numerical trace appeared to show an interception-versus-proximity
problem. At frame 15641, physical nearest distances favor away (1.62 m) over
home (4.54 m), but arrival-equivalent distances favor home (1.08 m versus 3.30 m).
The decoder confirms home control from the forecast. Later, 84 frames have no
qualifying control candidate, yet an available nearest-player observation keeps
the incumbent alive. This is how the wrong label persists.

A proximity gate is not enough: after eight frames the input itself places a
home-labelled slot beside the ball. At frame 15660, projected ATD ball coordinates
align with the visible away goalkeeper, while home slot 24 is 0.615 m from the
ball. Away goalkeeper slot 46 is displaced about 4.73 m away. The overlay shows
home slot 3 correctly on the pressing forward, so this is not a global team swap.

The XML labels slot 24 as a Barcelona **Goalkeeper**, and slot 46 as an Atletic
**Goalkeeper**. Slot 24 was at (15.31, 39.66) m at frame 15452, disappeared for
151 frames, then reappeared at (97.72, 35.38) m at frame 15604. That requires
**82.52 m in 6.08 seconds = 13.57 m/s**, above the existing 12 m/s player bound.
The 151 absent samples span 6.04 seconds; the two observed endpoints are
6.08 seconds apart. Slot 46 remains on the away goal side during this episode.

Two code paths allow this contamination:

1. `playground/features.py` checks player speed only for consecutive frames.
   A long missing interval bypasses that check.
2. `playground/creative/interception.py` replaces unavailable or implausible
   velocity with zero, but continues using the reappeared position. A corrupted
   location can therefore become a strong control candidate.

This is evidence of a likely identity/position discontinuity, not an identified
real player's movement. Slots are generic tracks, not verified shirt identities.
The implemented quality check applies to arbitrary eligible slots; slot 24 is
only an observed diagnostic example, never a hardcoded inference exception.

### Why the identity fix is not selected globally

The fixed q batch quarantines an unreachable reappearance's entire continuous
observed run. It removes all 125 target errors. However, the first anomalous run
is [15604, 89031), far longer than the visible identity error. Six goalkeeper
quarantines exclude **191,014 player-frame observations** across the recording.
Discarding such long runs can erase valid recovered trajectories.

The fixed t follow-up splits observed runs at consecutive jumps exceeding the
same 12 m/s bound. It was motivated by this exclusion audit, not a threshold
search. It shortens the initial suspect segment to [15604, 15920), but does not
solve recovery globally: goalkeeper-only mode excludes 197,504 player-frame
observations across 265 segments. Additional noisy discontinuities and incorrect
trusted anchors can still cause prolonged exclusions. Its public goalkeeper
scores match q; the all-player variants perform worse.

Therefore the identity failure is diagnosed, and the targeted correction works,
but reliable recovery/re-identification remains unresolved. No team labels or
raw coordinates were overwritten, and no exclusion branch was promoted as a
full-match correction.

## Root cause 2: a moving ball during a stoppage looks like live control

In the labelled stoppage, the ball is observed in **511/511 frames**. It has
median speed **2.76 m/s** and median one-second displacement **2.88 m**. The
existing stationary detector requires speed at most 0.8 m/s and displacement
at most 0.5 m, so it never supplies a dead cue. Median player speed is about
**1.00 m/s**, but slow collective movement alone is insufficient under that rule.
There is no out-of-pitch cue or relevant restart tag. The pure-occlusion bridge
also cannot apply because the ball remains visible.

The sampled footage shows contact, a player down, and subsequent regrouping,
consistent with a foul-related stoppage. The ball continues rolling and is
retrieved/moved while play is stopped. Neither ATD nor the available Smart Tags
explicitly supplies the referee's decision. The decoder mistakes apparent
player–ball proximity during that period for live possession.

### Implemented stoppage change

The new seed requires two seconds of observed, in-pitch ball movement no faster
than 12 m/s, farther than two metres from every player, while at least eight
players are visible and their median speed is at most 1.5 m/s. It uses collective
slowdown plus lack of a nearby controller, without requiring a perfectly still
ball. Once confirmed, p07 retains the stoppage through missing observations,
until supported restart motion or a fixed 20-second maximum.

In the target clip, p07 predicts D on **[15909, 16409)**:

- It starts **0.80 seconds late**, leaving 20 incorrect frames.
- It correctly marks **491/511 stoppage frames (96.1%)**.
- It ends **0.36 seconds late**, introducing nine errors after the true restart.
- The audit's release reason is **retention_limit**. It reaches the 20-second
  cap; it does not successfully recognize the actual restart in this example.

That last point matters: the gain demonstrates useful stoppage-entry evidence,
not a solved restart detector. Slow live build-ups can resemble stoppages, and
this heuristic has not been independently validated over the unlabelled match.

## Experimental sequence and validation

Three sequential, explicitly fixed batches were run: 11 physical-control/stoppage
variants, six whole-run quarantine variants, and six tracklet variants, including
reference anchors. Each branch changes one component from its named parent.
Later batches followed newly traced data-quality mechanisms and exclusion
artifacts; they are not represented as having been planned before the entire
investigation. No speed-threshold sweep, possession-label fitting, frame-specific
rule, or player-ID exception was used.

Every batch writes all prediction CSVs and hashes before reading possession
labels. Review ranges are used only in post-inference evaluation. Step 06 remains
unchanged. Public labels motivated error selection, so all score comparisons are
**exploratory debugging on the same five-minute window**, not a fresh holdout.

The p batch ran twice (`possession_fixes_001` and `_002`), about 26.4 seconds each.
All 11 predictions, scores, evidence traces, masks, audits, review files, source
protocols and hash manifests reproduced exactly. Its f03 reference also matched
the earlier fragmentation artifact. q and t each ran once, about 21.7–21.9
seconds; their references reproduced the p/f03 predictions. Negative results
and extensive exclusion counts remain recorded rather than discarded.

**348 tests passed**, including 64 new tests for these changes. Black formatting
and whitespace checks passed. Independent correctness and style reviews covered
both implementations and integration tests; accepted string-wrapping findings
were resolved. Tests verify source preservation, missing-data behavior, mask
retention, post-gap elapsed time, trusted-anchor handling, feature rebuilding,
prediction freezing, independent review ranges, and safe output publication.

## Run and inspect

Implementation and commands:

- [Physical control and stoppage experiments](possession_fixes/README.md)
- [Reacquisition and tracklet experiments](reacquisition/README.md)

To inspect the strongest spellF1 candidate:

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/possession_fixes_002/p07_collective_hold/possession.csv
```

To compare the identity-corrected candidate, which has higher macroF1 but lower
spellF1:

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/reacquisition_tracklets_001/t05_goalkeepers_and_stoppage/possession.csv
```

The viewer must be restarted when changing its prediction input. Existing
`output/prediction.csv` and source tracking remain unchanged.

## Complete experiment records

Parent-relative changes and reviewed-interval errors use different references:
main score/error deltas compare each named parent; reviewed intervals compare
with f03. The following generated records preserve every tested variant.

## Batch P: physical control and collective stoppages

Known public errors motivated this batch. All settings and comparisons were fixed before new scores; all submissions were frozen before GT was read. Review ranges never enter inference.

| Experiment | Parent | spellF1 | Δ f03 | macroF1 | Spells | D recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| p00_original_baseline | none | 0.325581 | -0.219873 | 0.620733 | 26 | 21.38% |
| p01_r06_reference | p00_original_baseline | 0.533333 | -0.012121 | 0.702218 | 16 | 34.85% |
| p02_f03_reference | p01_r06_reference | 0.545455 | +0.000000 | 0.702514 | 16 | 34.85% |
| p03_physical_gate | p02_f03_reference | 0.484848 | -0.060606 | 0.662591 | 16 | 28.18% |
| p04_physical_candidates | p02_f03_reference | 0.484848 | -0.060606 | 0.664742 | 16 | 28.18% |
| p05_physical_initialization | p04_physical_candidates | 0.484848 | -0.060606 | 0.664742 | 16 | 28.18% |
| p06_collective_seeds | p02_f03_reference | 0.581818 | +0.036364 | 0.774184 | 16 | 54.25% |
| p07_collective_hold | p06_collective_seeds | 0.612500 | +0.067045 | 0.817409 | 15 | 68.28% |
| p08_gate_and_hold | p07_collective_hold | 0.550000 | +0.004545 | 0.785066 | 15 | 61.61% |
| p09_physical_and_hold | p07_collective_hold | 0.550000 | +0.004545 | 0.787266 | 15 | 61.61% |
| p10_initialization_and_hold | p09_physical_and_hold | 0.550000 | +0.004545 | 0.787266 | 15 | 61.61% |

### p00_original_baseline: Original step 05 baseline

**Parent:** none. **Change:** reference.

**Hypothesis:** Reproduce the original baseline independently.

**Method:** Check against a separate step 05 invocation.

**Result:** spellF1 0.325581 (+0.000000 versus parent), macroF1 0.620733. Changed 0 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 graded errors.

**Structure:** 26 predicted versus 17 true possessions, 5 split true spells and 3 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 63/125 graded frames wrong (f03: 125). Corrected 62 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511). Corrected 0 f03 errors; introduced 0 errors.

### p01_r06_reference: Previous r06 reference

**Parent:** p00_original_baseline. **Change:** reference_anchor.

**Hypothesis:** Reproduce the earlier interception and occlusion predictor.

**Method:** Reference anchor; not a one-component change from step 05.

**Result:** spellF1 0.533333 (+0.207752 versus parent), macroF1 0.702218. Changed 34,653 full-recording labels and 1,039 graded labels. Corrected 585 parent errors and introduced 159 graded errors.

**Structure:** 16 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125). Corrected 0 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511). Corrected 0 f03 errors; introduced 0 errors.

### p02_f03_reference: Current f03 uncertainty-gap reference

**Parent:** p01_r06_reference. **Change:** reference_anchor.

**Hypothesis:** Reproduce the current strongest public spellF1 candidate.

**Method:** Run existing r06, classify uncertainty, and join supported same-team gaps.

**Result:** spellF1 0.545455 (+0.012121 versus parent), macroF1 0.702514. Changed 1,813 full-recording labels and 2 graded labels. Corrected 2 parent errors and introduced 0 graded errors.

**Structure:** 16 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125). Corrected 0 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511). Corrected 0 f03 errors; introduced 0 errors.

### p03_physical_gate: Require physical proximity for forecast-based control

**Parent:** p02_f03_reference. **Change:** control_candidate_gate.

**Hypothesis:** Winning a projected interception race does not establish current control.

**Method:** Reject arrival-based candidates unless the selected team is within two actual metres and at least 0.5 m closer than the opponent. Keep the existing incumbent, confirmation, smoothing, and gap handling.

**Result:** spellF1 0.484848 (-0.060606 versus parent), macroF1 0.662591. Changed 9,353 full-recording labels and 307 graded labels. Corrected 23 parent errors and introduced 238 graded errors.

**Structure:** 16 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 117/125 graded frames wrong (f03: 125). Corrected 8 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511). Corrected 0 f03 errors; introduced 0 errors.

### p04_physical_candidates: Use physical proximity for control confirmation

**Parent:** p02_f03_reference. **Change:** control_candidate_geometry.

**Hypothesis:** Observed proximity may identify current control better than future arrival.

**Method:** Replace only control-candidate distances with original pitch distances. Keep arrival-nearest initialization and the existing speed and duration rules.

**Result:** spellF1 0.484848 (-0.060606 versus parent), macroF1 0.664742. Changed 7,859 full-recording labels and 325 graded labels. Corrected 41 parent errors and introduced 238 graded errors.

**Structure:** 16 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 117/125 graded frames wrong (f03: 125). Corrected 8 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511). Corrected 0 f03 errors; introduced 0 errors.

### p05_physical_initialization: Use physical nearest-team observations for initialization

**Parent:** p04_physical_candidates. **Change:** incumbent_initialization.

**Hypothesis:** A forecast-nearest fallback can start possession on the wrong team.

**Method:** Feed original nearest-team codes into incumbent initialization and observation-gap handling; retain physical control confirmation.

**Result:** spellF1 0.484848 (+0.000000 versus parent), macroF1 0.664742. Changed 1,303 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 graded errors.

**Structure:** 16 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 117/125 graded frames wrong (f03: 125). Corrected 8 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511). Corrected 0 f03 errors; introduced 0 errors.

### p06_collective_seeds: Detect sustained collective slowdown with an uncontrolled ball

**Parent:** p02_f03_reference. **Change:** collective_stoppage_entry.

**Hypothesis:** Players may stop after a foul while the ball continues rolling.

**Method:** Require two seconds of at least eight visible players with median speed at most 1.5 m/s and a visible in-pitch ball beyond two metres from every player, moving no faster than 12 m/s. Inject qualifying seed runs as D.

**Result:** spellF1 0.581818 (+0.036364 versus parent), macroF1 0.774184. Changed 8,639 full-recording labels and 285 graded labels. Corrected 285 parent errors and introduced 0 graded errors.

**Structure:** 16 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125). Corrected 0 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 226/511 graded frames wrong (f03: 511). Corrected 285 f03 errors; introduced 0 errors.

### p07_collective_hold: Retain collective stoppages until supported restart motion

**Parent:** p06_collective_seeds. **Change:** collective_stoppage_retention.

**Hypothesis:** Retrieving a ball after a stoppage need not restore live possession.

**Method:** Hold a confirmed collective seed through uncertainty, up to 20 seconds. Release on 0.4 seconds of observed physical control, in-pitch ball motion at least 2 m/s, and either renewed collective movement or ball speed at least 8 m/s. Motion above 45 m/s is not release evidence.

**Result:** spellF1 0.612500 (+0.030682 versus parent), macroF1 0.817409. Changed 11,752 full-recording labels and 215 graded labels. Corrected 206 parent errors and introduced 9 graded errors.

**Structure:** 15 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125). Corrected 0 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 20/511 graded frames wrong (f03: 511). Corrected 491 f03 errors; introduced 0 errors.

### p08_gate_and_hold: Physical control gate with collective stoppage retention

**Parent:** p07_collective_hold. **Change:** control_candidate_gate.

**Hypothesis:** Physical ownership checks and stoppage detection may complement each other.

**Method:** Reject arrival-based candidates unless the selected team is within two actual metres and at least 0.5 m closer than the opponent. Keep the existing incumbent, confirmation, smoothing, and gap handling.

**Result:** spellF1 0.550000 (-0.062500 versus parent), macroF1 0.785066. Changed 6,810 full-recording labels and 291 graded labels. Corrected 23 parent errors and introduced 238 graded errors.

**Structure:** 15 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 117/125 graded frames wrong (f03: 125). Corrected 8 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 20/511 graded frames wrong (f03: 511). Corrected 491 f03 errors; introduced 0 errors.

### p09_physical_and_hold: Physical control candidates with collective stoppage retention

**Parent:** p07_collective_hold. **Change:** control_candidate_geometry.

**Hypothesis:** Physical control candidates may complement collective stoppage retention.

**Method:** Replace only control-candidate distances with original pitch distances. Keep arrival-nearest initialization and the existing speed and duration rules.

**Result:** spellF1 0.550000 (-0.062500 versus parent), macroF1 0.787266. Changed 6,126 full-recording labels and 309 graded labels. Corrected 41 parent errors and introduced 238 graded errors.

**Structure:** 15 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 117/125 graded frames wrong (f03: 125). Corrected 8 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 20/511 graded frames wrong (f03: 511). Corrected 491 f03 errors; introduced 0 errors.

### p10_initialization_and_hold: Physical initialization and control with collective stoppages

**Parent:** p09_physical_and_hold. **Change:** incumbent_initialization.

**Hypothesis:** Physical initialization may avoid unsupported ownership after stoppages.

**Method:** Feed original nearest-team codes into incumbent initialization and observation-gap handling; retain physical control confirmation.

**Result:** spellF1 0.550000 (+0.000000 versus parent), macroF1 0.787266. Changed 1,238 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 graded errors.

**Structure:** 15 predicted versus 17 true possessions, 1 split true spells and 2 merged predictions under positive same-team overlap diagnostics.

**Review [15641, 15766):** 117/125 graded frames wrong (f03: 125). Corrected 8 f03 errors; introduced 0 errors.

**Review [15889, 16400):** 20/511 graded frames wrong (f03: 511). Corrected 491 f03 errors; introduced 0 errors.

### Limits

These are exploratory results on the repeatedly inspected public five-minute window, not an independent holdout. Physical proximity does not prove control, and collective slowdown does not prove a foul. A target-clip improvement can coincide with a worse global score. Full-match changes remain unverified. No candidate is automatically promoted and the viewer default is preserved.

## Batch Q: whole-run quarantine

These hypotheses follow a traced identity discontinuity. No player ID, target frame, or possession label enters inference. All six predictions were frozen before new scores; this remains exploratory public-window debugging.

| Experiment | Parent | spellF1 | macroF1 | Spells | D recall |
| --- | --- | ---: | ---: | ---: | ---: |
| q00_f03_reference | none | 0.545455 | 0.702514 | 16 | 34.85% |
| q01_collective_reference | q00_f03_reference | 0.612500 | 0.817409 | 15 | 68.28% |
| q02_all_player_quarantine | q00_f03_reference | 0.484848 | 0.701932 | 16 | 34.85% |
| q03_goalkeeper_quarantine | q02_all_player_quarantine | 0.529032 | 0.714805 | 14 | 34.85% |
| q04_all_and_stoppage | q02_all_player_quarantine | 0.447059 | 0.781622 | 17 | 76.92% |
| q05_goalkeepers_and_stoppage | q03_goalkeeper_quarantine | 0.554839 | 0.836143 | 14 | 76.92% |

### q00_f03_reference: Existing f03 reference

**Parent:** none. **Change:** reference.

**Hypothesis:** Reproduce the earlier uncertainty-gap candidate.

**Method:** Existing interception, control confirmation and f03 gap repair.

**Result:** spellF1 0.545455 (+0.000000 versus parent), macroF1 0.702514. Changed 0 full-recording and 0 graded labels. Corrected 0 parent errors; introduced 0 errors.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511).

### q01_collective_reference: Existing p07 collective-stoppage reference

**Parent:** q00_f03_reference. **Change:** collective_stoppage_reference.

**Hypothesis:** Reproduce the strongest candidate from the preceding fixed batch.

**Method:** Add the unchanged collective seed and retention rule from p07.

**Result:** spellF1 0.612500 (+0.067045 versus parent), macroF1 0.817409. Changed 18896 full-recording and 500 graded labels. Corrected 491 parent errors; introduced 9 errors.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 20/511 graded frames wrong (f03: 511).

### q02_all_player_quarantine: Quarantine impossible player reappearances

**Parent:** q00_f03_reference. **Change:** reacquisition_quality.

**Hypothesis:** A track reappearing beyond physical reach can create false team control.

**Method:** For every player, compare a post-gap run's first point with the last trusted point using actual elapsed time. If required average speed exceeds 12 m/s, exclude the entire contiguous run from inference, retain the trusted anchor, and recompute player-dependent features. Preserve source data.

**Result:** spellF1 0.484848 (-0.060606 versus parent), macroF1 0.701932. Changed 2736 full-recording and 409 graded labels. Corrected 125 parent errors; introduced 130 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511).

### q03_goalkeeper_quarantine: Restrict impossible-reappearance quarantine to metadata goalkeepers

**Parent:** q02_all_player_quarantine. **Change:** quarantine_scope.

**Hypothesis:** A role-restricted correction may avoid excluding useful outfield tracks.

**Method:** Apply the same 12 m/s post-gap test only to slots whose XML position_type is Goalkeeper. No player identifiers or target timestamps enter the rule.

**Result:** spellF1 0.529032 (+0.044184 versus parent), macroF1 0.714805. Changed 829 full-recording and 129 graded labels. Corrected 129 parent errors; introduced 0 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511).

### q04_all_and_stoppage: All-player quarantine plus collective stoppages

**Parent:** q02_all_player_quarantine. **Change:** collective_stoppage.

**Hypothesis:** Removing identity corruption may complement stoppage detection.

**Method:** Add the unchanged collective seed and retention rule from p07.

**Result:** spellF1 0.447059 (-0.037790 versus parent), macroF1 0.781622. Changed 22357 full-recording and 1177 graded labels. Corrected 634 parent errors; introduced 434 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 22/511 graded frames wrong (f03: 511).

### q05_goalkeepers_and_stoppage: Goalkeeper quarantine plus collective stoppages

**Parent:** q03_goalkeeper_quarantine. **Change:** collective_stoppage.

**Hypothesis:** Role-restricted identity correction may complement stoppage detection.

**Method:** Add the unchanged collective seed and retention rule from p07.

**Result:** spellF1 0.554839 (+0.025806 versus parent), macroF1 0.836143. Changed 21940 full-recording and 762 graded labels. Corrected 618 parent errors; introduced 144 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 22/511 graded frames wrong (f03: 511).

### Limits

The entire continuous observation run is quarantined after an impossible reappearance. A wrong old anchor can therefore discard a valid new run, and real identity swaps with physically plausible displacement remain undetected. No coordinates or team identities are imputed or overwritten. Collective stoppage rules remain hypotheses. The same public window motivated and evaluates this debugging work; full-match reliability requires independent evidence. No candidate is automatically promoted.

## Batch T: physically segmented quarantine

These hypotheses follow a traced identity discontinuity. No player ID, target frame, or possession label enters inference. All six predictions were frozen before new scores; this remains exploratory public-window debugging.

| Experiment | Parent | spellF1 | macroF1 | Spells | D recall |
| --- | --- | ---: | ---: | ---: | ---: |
| t00_f03_reference | none | 0.545455 | 0.702514 | 16 | 34.85% |
| t01_collective_reference | t00_f03_reference | 0.612500 | 0.817409 | 15 | 68.28% |
| t02_all_player_quarantine | t00_f03_reference | 0.424242 | 0.710107 | 16 | 34.85% |
| t03_goalkeeper_quarantine | t02_all_player_quarantine | 0.529032 | 0.714805 | 14 | 34.85% |
| t04_all_and_stoppage | t02_all_player_quarantine | 0.341176 | 0.723117 | 17 | 76.31% |
| t05_goalkeepers_and_stoppage | t03_goalkeeper_quarantine | 0.554839 | 0.836143 | 14 | 76.92% |

### t00_f03_reference: Existing f03 reference

**Parent:** none. **Change:** reference.

**Hypothesis:** Reproduce the earlier uncertainty-gap candidate.

**Method:** Existing interception, control confirmation and f03 gap repair.

**Result:** spellF1 0.545455 (+0.000000 versus parent), macroF1 0.702514. Changed 0 full-recording and 0 graded labels. Corrected 0 parent errors; introduced 0 errors.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511).

### t01_collective_reference: Existing p07 collective-stoppage reference

**Parent:** t00_f03_reference. **Change:** collective_stoppage_reference.

**Hypothesis:** Reproduce the strongest candidate from the preceding fixed batch.

**Method:** Add the unchanged collective seed and retention rule from p07.

**Result:** spellF1 0.612500 (+0.067045 versus parent), macroF1 0.817409. Changed 18896 full-recording and 500 graded labels. Corrected 491 parent errors; introduced 9 errors.

**Review [15641, 15766):** 125/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 20/511 graded frames wrong (f03: 511).

### t02_all_player_quarantine: Quarantine impossible player reappearances

**Parent:** t00_f03_reference. **Change:** reacquisition_quality.

**Hypothesis:** A track reappearing beyond physical reach can create false team control.

**Method:** For every player, compare a post-gap run's first point with the last trusted point using actual elapsed time. If required average speed exceeds 12 m/s, exclude the entire contiguous run from inference, retain the trusted anchor, and recompute player-dependent features. Preserve source data. Split observed runs at consecutive jumps above the same 12 m/s bound; apply quarantine to these physically continuous tracklets. A later reachable tracklet can restore the trusted identity.

**Result:** spellF1 0.424242 (-0.121212 versus parent), macroF1 0.710107. Changed 9014 full-recording and 1298 graded labels. Corrected 321 parent errors; introduced 343 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511).

### t03_goalkeeper_quarantine: Restrict impossible-reappearance quarantine to metadata goalkeepers

**Parent:** t02_all_player_quarantine. **Change:** quarantine_scope.

**Hypothesis:** A role-restricted correction may avoid excluding useful outfield tracks.

**Method:** Apply the same 12 m/s post-gap test only to slots whose XML position_type is Goalkeeper. No player identifiers or target timestamps enter the rule. Split observed runs at consecutive jumps above the same 12 m/s bound; apply quarantine to these physically continuous tracklets. A later reachable tracklet can restore the trusted identity.

**Result:** spellF1 0.529032 (+0.104790 versus parent), macroF1 0.714805. Changed 6688 full-recording and 1018 graded labels. Corrected 342 parent errors; introduced 196 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 511/511 graded frames wrong (f03: 511).

### t04_all_and_stoppage: All-player quarantine plus collective stoppages

**Parent:** t02_all_player_quarantine. **Change:** collective_stoppage.

**Hypothesis:** Removing identity corruption may complement stoppage detection.

**Method:** Add the unchanged collective seed and retention rule from p07. Split observed runs at consecutive jumps above the same 12 m/s bound; apply quarantine to these physically continuous tracklets. A later reachable tracklet can restore the trusted identity.

**Result:** spellF1 0.341176 (-0.083066 versus parent), macroF1 0.723117. Changed 25362 full-recording and 1504 graded labels. Corrected 609 parent errors; introduced 838 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 18/511 graded frames wrong (f03: 511).

### t05_goalkeepers_and_stoppage: Goalkeeper quarantine plus collective stoppages

**Parent:** t03_goalkeeper_quarantine. **Change:** collective_stoppage.

**Hypothesis:** Role-restricted identity correction may complement stoppage detection.

**Method:** Add the unchanged collective seed and retention rule from p07. Split observed runs at consecutive jumps above the same 12 m/s bound; apply quarantine to these physically continuous tracklets. A later reachable tracklet can restore the trusted identity.

**Result:** spellF1 0.554839 (+0.025806 versus parent), macroF1 0.836143. Changed 21389 full-recording and 762 graded labels. Corrected 618 parent errors; introduced 144 errors.

**Review [15641, 15766):** 0/125 graded frames wrong (f03: 125).

**Review [15889, 16400):** 22/511 graded frames wrong (f03: 511).

### Limits

The entire selected segment is quarantined after an impossible reappearance: an observed run by default, or a physically continuous tracklet with splitting enabled. A wrong old anchor can discard a valid new segment, and real identity swaps with physically plausible displacement remain undetected. No coordinates or team identities are imputed or overwritten. Collective stoppage rules remain hypotheses. The same public window motivated and evaluates this debugging work; full-match reliability requires independent evidence. No candidate is automatically promoted.
