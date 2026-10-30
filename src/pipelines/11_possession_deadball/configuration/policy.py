"""Fixed ownership, stoppage and match-timeline settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PossessionPolicy:
    # Ownership: a team needs a nearby player, a clear lead and plausible ball speed.
    control_distance_m: float = 2
    control_advantage_m: float = 0.5
    control_ball_speed_mps: float = 12
    control_confirmation_seconds: float = 0.4
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
