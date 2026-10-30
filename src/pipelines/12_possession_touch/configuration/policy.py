"""Fixed ownership, stoppage and match-timeline settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PossessionPolicy:
    # Ownership: a touch is a player within reach of the ball. The opposing team takes
    # possession only by keeping the ball or by passing it on, not by a single touch.
    touch_distance_m: float = 1.5
    touch_gap_seconds: float = 1.0
    control_dwell_seconds: float = 1.5
    pass_window_seconds: float = 3
    # Stoppage: players walk instead of run, or the ball leaves the pitch.
    activity_window_seconds: float = 3
    stoppage_enter_mps: float = 1.1
    stoppage_exit_mps: float = 1.6
    minimum_stoppage_seconds: float = 3
    out_of_pitch_margin_m: float = 0.5
    out_of_pitch_window_seconds: float = 0.4
    set_piece_lead_seconds: float = 1
    # Published BAR-ATH timeline: inclusive graded halves and the kick-off frames.
    graded_halves: tuple[tuple[int, int], ...] = ((11185, 90651), (110808, 190197))
    kickoff_frames: tuple[int, ...] = (11185, 113742)
