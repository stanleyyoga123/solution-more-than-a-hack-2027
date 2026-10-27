"""Fixed detector and motion gates chosen without possession labels."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VisionPolicy:
    sample_stride: int = 25
    max_control_frames: int = 200
    image_size: int = 1280
    confidence: float = 0.25
    confidence_margin: float = 0.1
    pitch_padding_m: float = 2
    maximum_speed_mps: float = 45
    anchor_seconds: float = 1
    anchor_padding_m: float = 2
    interpolation_seconds: float = 1.2
    maximum_samples: int = 0
    cpu_threads: int = 4
