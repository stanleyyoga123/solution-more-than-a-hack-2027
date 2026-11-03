"""Descriptive Smart Tagging evidence, never a classification score."""

from collections.abc import Sequence
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

SMART_TAGGING_FPS = 25


def read_events(path: Path) -> list[dict]:
    events = []
    for instance in ET.parse(path).getroot().iter("instance"):
        labels = {
            label.findtext("group"): label.findtext("text")
            for label in instance.findall("label")
        }
        phase = instance.findtext("code")
        team = labels.get("Team")
        events.append(
            {
                "start": round(float(instance.findtext("start")) * SMART_TAGGING_FPS),
                "stop": round(float(instance.findtext("end")) * SMART_TAGGING_FPS),
                "phase": phase,
                "category": labels.get("Type") or phase,
                "team": (
                    team
                    if team and team.upper() not in {"N/A", "UNKNOWN"}
                    else "Unknown / N/A"
                ),
            }
        )
    return sorted(events, key=lambda event: (event["start"], event["stop"]))


def nearby_events(events: list[dict], start: int, stop: int, window: int) -> list[dict]:
    return [
        event
        for event in events
        if event["start"] < stop + window and event["stop"] > start - window
    ]


def intervals(values: Sequence) -> list[dict]:
    result = []
    for frame, value in enumerate(values):
        if result and result[-1]["value"] == value:
            result[-1]["stop"] = frame + 1
        else:
            result.append({"start": frame, "stop": frame + 1, "value": value})
    return result


def event_summary(
    events: list[dict], truth: Sequence[str], prediction: Sequence[str], window: int
) -> dict:
    counts = Counter(event["category"] for event in events)
    public_counts = Counter()
    covered = set()
    for event in events:
        frames = range(max(0, event["start"]), min(len(truth), event["stop"]))
        if any(truth[i] in "HAD" for i in frames):
            public_counts[event["category"]] += 1
        if event["phase"].upper() == "SET PIECES":
            covered.update(i for i in frames if truth[i] in "HAD")
    stoppages = {
        "total": 0,
        "with_evidence": 0,
        "without_evidence": 0,
        "missed_with_evidence": 0,
        "missed_without_evidence": 0,
    }
    for run in intervals(truth):
        if run["value"] != "D":
            continue
        stoppages["total"] += 1
        nearby = bool(nearby_events(events, run["start"], run["stop"], window))
        suffix = "with_evidence" if nearby else "without_evidence"
        stoppages[suffix] += 1
        if any(prediction[i] != "D" for i in range(run["start"], run["stop"])):
            stoppages["missed_" + suffix] += 1
    return {
        "scope": "full_match_frequency_and_public_labelled_overlap",
        "frequency": [
            {
                "category": key,
                "full_match": counts[key],
                "public_overlap": public_counts[key],
            }
            for key in sorted(counts)
        ],
        "teams": dict(Counter(event["team"] for event in events)),
        "set_piece_frames": {
            state: sum(truth[i] == state for i in covered) for state in "HAD"
        },
        "stoppages": stoppages,
        "window_frames": window,
        "timestamp_fps": SMART_TAGGING_FPS,
    }
