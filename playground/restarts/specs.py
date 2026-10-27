"""Fixed restart hypotheses, each compared with its named parent."""

from dataclasses import dataclass, replace

from playground.experiment_spec import ExperimentSpec


@dataclass(frozen=True)
class RestartSpec(ExperimentSpec):
    method: str = "reference"
    extend_before: bool = False
    include_boundary: bool = False
    release_on_control: bool = False
    integrated: bool = False


BASELINE = RestartSpec(
    id="s00_original_baseline",
    parent_id="",
    title="Original step 05 reference",
    changed_component="reference",
    hypothesis="Reproduce the unmodified baseline.",
    rationale="Checked against an independently generated step 05 submission.",
)
ANCHOR = RestartSpec(
    id="s01_occlusion_reference",
    parent_id=BASELINE.id,
    title="Previous r06 interception and occlusion reference",
    changed_component="reference_anchor",
    hypothesis="Reproduce the previous strongest spellF1 result.",
    rationale=(
        "This reference combines prior interception, control and occlusion rules; "
        "it is not a single-component change from s00."
    ),
)
WINDOW = replace(
    ANCHOR,
    id="s02_whole_restart_window",
    parent_id=ANCHOR.id,
    title="Treat entire restart windows as dead ball",
    changed_component="whole_window_dead",
    hypothesis="Test the direct-tag assumption as a deliberately coarse control.",
    rationale=(
        "Set D throughout every recognized set-piece interval, without motion "
        "confirmation. This may erase live play because event windows are not "
        "verified stoppage intervals."
    ),
    method="window",
)
SEEDS = replace(
    ANCHOR,
    id="s03_typed_stationary_seeds",
    parent_id=ANCHOR.id,
    title="Require stationary ball evidence at a plausible restart location",
    changed_component="typed_stationary_dead",
    hypothesis="Restart type and observed stillness can support precise D frames.",
    rationale=(
        "Within each known event window require 0.4 seconds of observed ball "
        "speed at most 1 m/s, gated by restart-specific geometry. Unknown "
        "teams remain usable for stoppage evidence."
    ),
    method="seeds",
)
LATCH = replace(
    SEEDS,
    id="s04_seeded_restart_state",
    parent_id=SEEDS.id,
    title="Retain the first confirmed stoppage until motion resumes",
    changed_component="stoppage_persistence",
    hypothesis="A confirmed stoppage can persist while tracking loses the ball.",
    rationale=(
        "Use only the first qualifying seed per event and retain D through "
        "missing observations. End at 0.2 seconds of observed in-pitch motion "
        "between 2 and 45 m/s, backdated to that run's start, capped by the "
        "event end or 20 seconds after the seed."
    ),
    method="latch",
)
BACKTRACK = replace(
    LATCH,
    id="s05_backtrack_supported_stop",
    parent_id=LATCH.id,
    title="Extend a confirmed stoppage backward through compatible uncertainty",
    changed_component="stoppage_onset",
    hypothesis="The tracker may miss the beginning of a stoppage before a still ball appears.",
    rationale=(
        "Extend at most eight seconds before the first confirmed seed across "
        "missing or stationary geometry-compatible observations; stop at "
        "contradictory observed play. This can precede the tag window."
    ),
    extend_before=True,
)
BOUNDARY = replace(
    LATCH,
    id="s06_boundary_entry",
    parent_id=LATCH.id,
    title="Also accept observed out-of-pitch entry evidence",
    changed_component="stoppage_entry",
    hypothesis="Out-of-play geometry can seed a restart without a visible stationary ball.",
    rationale=(
        "For throw-ins, corners and goal kicks, also accept 0.2 seconds outside "
        "the pitch by at least 0.25 m with compatible event geometry. Free "
        "kicks and kickoffs still require stationary evidence."
    ),
    include_boundary=True,
)
CONTROL_RELEASE = replace(
    LATCH,
    id="s07_control_supported_release",
    parent_id=LATCH.id,
    title="Recognize a slower restart near an observed player",
    changed_component="stoppage_release",
    hypothesis="A short controlled restart may not immediately reach 2 m/s.",
    rationale=(
        "After seed confirmation, also permit sustained in-pitch motion of "
        "at least 0.8 m/s with an observed player within two actual metres. "
        "The upper plausible ball-speed bound still applies."
    ),
    release_on_control=True,
)
INTEGRATED = replace(
    LATCH,
    id="s08_reset_control_state",
    parent_id=LATCH.id,
    title="Use inferred stoppages inside the possession state machine",
    changed_component="stoppage_integration",
    hypothesis="Resetting the incumbent at a stoppage may improve restart ownership.",
    rationale=(
        "Inject the same inferred D mask before control confirmation instead "
        "of only overwriting final labels. Preserve explicit D through smoothing "
        "and the existing occlusion bridge."
    ),
    integrated=True,
)
BOUNDARY_BACKTRACK = replace(
    BOUNDARY,
    id="s09_boundary_backtrack",
    parent_id=BOUNDARY.id,
    title="Backtrack confirmed stationary or boundary stoppages",
    changed_component="stoppage_onset",
    hypothesis="Additional entry evidence may complement bounded backward extension.",
    rationale=BACKTRACK.rationale,
    extend_before=True,
)
DEAD_GAPS = replace(
    ANCHOR,
    id="s10_restart_dead_gap_bridge",
    parent_id=ANCHOR.id,
    title="Remove short unsupported live islands within a tagged stoppage",
    changed_component="dead_gap_continuity",
    hypothesis="Brief live labels between two D intervals may fragment one restart.",
    rationale=(
        "Within a single restart window, bridge live runs up to two seconds "
        "bounded by D only if no observed ball has plausible motion at least "
        "2 m/s or nearby player-control evidence. Preserve X and other labels."
    ),
    method="dead_gaps",
)

RESTART_EXPERIMENTS = (
    BASELINE,
    ANCHOR,
    WINDOW,
    SEEDS,
    LATCH,
    BACKTRACK,
    BOUNDARY,
    CONTROL_RELEASE,
    INTEGRATED,
    BOUNDARY_BACKTRACK,
    DEAD_GAPS,
)
