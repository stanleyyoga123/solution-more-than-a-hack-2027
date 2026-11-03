"""Allowlisted diagnostics projection; local filesystem paths stay on disk."""

from pathlib import Path


def pick(value: dict, keys: str) -> dict:
    return {key: value[key] for key in keys.split() if key in value}


def public_report(document: dict) -> dict:
    result = pick(
        document, "schema_version generated_at timeline fps frame_count spell_f1_mean"
    )
    result["sources"] = {
        key: Path(value).name
        for key, value in document.get("sources", {}).items()
        if key in {"tracking", "metadata", "baseline", "ground_truth", "smart_tagging"}
    }
    result["overview"] = pick(
        document.get("overview", {}),
        "duration_seconds tracking_rows usable_rows ball_visible_frames mean_visible_players",
    )
    for name, fields in [
        ("ball_visibility", "start stop value"),
        ("possession", "start stop value"),
        ("gap_ecdf", "seconds fraction"),
    ]:
        result[name] = [pick(row, fields) for row in document.get(name, [])]
    result["spell_f1"] = {
        key: pick(value, "f1") for key, value in document.get("spell_f1", {}).items()
    }
    result["parameters"] = pick(
        document.get("parameters", {}),
        "event_window_seconds transition_tolerance_frames prediction_policy",
    )
    result["source_sha256"] = {
        key: value
        for key, value in document.get("source_sha256", {}).items()
        if key in result["sources"]
    }
    geometry = document.get("geometry")
    result["geometry"] = None
    if geometry:
        result["geometry"] = pick(geometry, "scope labelled_frames")
        result["geometry"]["states"] = {}
        for state in "HAD":
            if state not in geometry["states"]:
                continue
            group = geometry["states"][state]
            summary = pick(
                group,
                "frames samples excluded_ball excluded_players visible missing median_metres",
            )
            summary["ecdf"] = [
                pick(point, "metres fraction") for point in group.get("ecdf", [])
            ]
            result["geometry"]["states"][state] = summary
    events = document.get("events")
    result["events"] = None
    if events:
        result["events"] = pick(events, "scope window_frames timestamp_fps")
        result["events"]["frequency"] = [
            pick(row, "category full_match public_overlap")
            for row in events["frequency"]
        ]
        result["events"]["teams"] = dict(events["teams"])
        result["events"]["set_piece_frames"] = pick(events["set_piece_frames"], "H A D")
        result["events"]["stoppages"] = pick(
            events["stoppages"],
            "total with_evidence without_evidence missed_with_evidence missed_without_evidence",
        )
    if "failures" in document:
        result["failures"] = []
        for case in document["failures"]:
            row = pick(
                case,
                "start stop categories ground_truth predicted ball_visibility_percent description",
            )
            row["events"] = [
                pick(event, "start stop category phase team")
                for event in case["events"]
            ]
            result["failures"].append(row)
    return result
