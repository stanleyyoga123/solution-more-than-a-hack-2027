"""Reproducible diagnostic candidates from public label runs."""

from collections.abc import Sequence

from src.diagnostics.events import intervals, nearby_events


def failure_cases(
    truth: Sequence[str],
    prediction: Sequence[str],
    visible: Sequence[bool],
    events: list[dict],
    window: int,
    tolerance: int,
) -> list[dict]:
    """Use raw predictions; X is abstention, never an invented possession."""
    findings = []
    # Work separately inside each graded window to avoid crossing unlabelled gaps.
    for window_run in intervals([value in "HAD" for value in truth]):
        if not window_run["value"]:
            continue
        start, stop = window_run["start"], window_run["stop"]
        actual = intervals(truth[start:stop])
        predicted = intervals(prediction[start:stop])
        for run in actual + predicted:
            run["start"] += start
            run["stop"] += start
        for run in actual:
            if run["value"] in "HA":
                overlaps = [
                    p
                    for p in predicted
                    if p["value"] in "HA"
                    and p["start"] < run["stop"]
                    and p["stop"] > run["start"]
                ]
                if len(overlaps) > 1:
                    findings.append(
                        (run["start"], run["stop"], "Candidate possession split")
                    )
        for run in predicted:
            if run["value"] in "HA":
                overlaps = [
                    g
                    for g in actual
                    if g["value"] in "HA"
                    and g["start"] < run["stop"]
                    and g["stop"] > run["start"]
                ]
                if len(overlaps) > 1:
                    findings.append(
                        (run["start"], run["stop"], "Candidate possession merge")
                    )
        # Typed, one-to-one transition matching, maximum-cardinality chronological pairs.
        gt = [
            (r["start"], actual[i - 1]["value"], r["value"])
            for i, r in enumerate(actual)
            if i
        ]
        pr = [
            (r["start"], predicted[i - 1]["value"], r["value"])
            for i, r in enumerate(predicted)
            if i and r["value"] in "HAD" and predicted[i - 1]["value"] in "HAD"
        ]
        # Earliest compatible pairs maximize cardinality for each transition type
        # under a fixed symmetric tolerance, without stranding later boundaries.
        matched_g, matched_p = set(), set()
        for kind in sorted({transition[1:] for transition in gt}):
            actual_indices = [
                i for i, transition in enumerate(gt) if transition[1:] == kind
            ]
            predicted_indices = [
                i for i, transition in enumerate(pr) if transition[1:] == kind
            ]
            left = right = 0
            while left < len(actual_indices) and right < len(predicted_indices):
                i, j = actual_indices[left], predicted_indices[right]
                difference = gt[i][0] - pr[j][0]
                if difference > tolerance:
                    right += 1
                elif difference < -tolerance:
                    left += 1
                else:
                    matched_g.add(i)
                    matched_p.add(j)
                    left += 1
                    right += 1
        for transitions, matched, category in [
            (gt, matched_g, "Missed transition"),
            (pr, matched_p, "Spurious transition"),
        ]:
            for index, transition in enumerate(transitions):
                if index not in matched:
                    frame = transition[0]
                    findings.append(
                        (
                            max(start, frame - tolerance),
                            min(stop, frame + tolerance + 1),
                            category,
                        )
                    )
    pairs = list(zip(truth, prediction))
    for run in intervals(pairs):
        actual, predicted = run["value"]
        if actual in "HA" and predicted == "D":
            findings.append((run["start"], run["stop"], "False stoppage"))
        elif actual == "D" and predicted != "D":
            findings.append((run["start"], run["stop"], "Missed stoppage"))
    # Partition on evidence boundaries; categories can coexist on each interval.
    boundaries = sorted(
        {bound for start, stop, _ in findings for bound in (start, stop)}
        | {r["start"] for r in intervals(pairs)}
        | {len(truth)}
    )
    cases = []
    for start, stop in zip(boundaries, boundaries[1:]):
        categories = sorted(
            {category for left, right, category in findings if left <= start < right}
        )
        if not categories or truth[start] not in "HAD":
            continue
        context = nearby_events(events, start, stop, window)
        cases.append(
            {
                "start": start,
                "stop": stop,
                "categories": categories,
                "ground_truth": truth[start],
                "predicted": prediction[start],
                "ball_visibility_percent": 100
                * sum(bool(v) for v in visible[start:stop])
                / (stop - start),
                "events": context,
                "description": "; ".join(categories)
                + ". Review timing and tracking availability; candidate evidence only.",
            }
        )
    return cases
