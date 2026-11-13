#!/usr/bin/env python3
"""Score dated forecasts against metrics dict."""

import argparse
import json
import pathlib
import sys
from typing import Any, Optional


def get(metrics: dict[str, Any], path: str) -> Optional[float | int]:
    """Walk dotted path through nested dicts; return numeric leaf or None.

    Returns None when any step is missing or the final value is not int/float
    (bool counts as non‑numeric).
    """
    current: Any = metrics
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, bool):
        return None
    if isinstance(current, (int, float)):
        return current
    return None


def holds(value: Any, op: str, threshold: Any) -> bool:
    """Return value op threshold for op in {'<', '<=', '>', '>='}.

    Raises:
        ValueError: op not among the four supported comparison operators.
    """
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    raise ValueError(f"Unsupported operator: {op}")


def score_one(f: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Score a single forecast dict; return a result dict.

    The result contains keys: id, status, value, op, threshold, due, as_of, on_track.
    """
    as_of = metrics.get("as_of")
    value = get(metrics, f["path"])
    op = f["op"]
    threshold = f["threshold"]
    due = f["due"]
    result: dict[str, Any] = {
        "id": f["id"],
        "status": None,
        "value": value,
        "op": op,
        "threshold": threshold,
        "due": due,
        "as_of": as_of,
        "on_track": None,
    }

    if value is None:
        result["status"] = "NO_DATA"
        result["on_track"] = None
        return result

    on_track = holds(value, op, threshold)
    if as_of < due:
        result["status"] = "PENDING"
        result["on_track"] = on_track
    else:
        result["status"] = "HIT" if on_track else "MISS"
        result["on_track"] = on_track
    return result


def score(forecasts: list[dict[str, Any]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a list of score_one results, one per forecast, in order."""
    return [score_one(f, metrics) for f in forecasts]


def summary(results: list[dict[str, Any]]) -> str:
    """Return exactly 'SCORE: hits=<h> misses=<m> pending=<p> no_data=<n>'."""
    hits = sum(1 for r in results if r["status"] == "HIT")
    misses = sum(1 for r in results if r["status"] == "MISS")
    pending = sum(1 for r in results if r["status"] == "PENDING")
    no_data = sum(1 for r in results if r["status"] == "NO_DATA")
    return f"SCORE: hits={hits} misses={misses} pending={pending} no_data={no_data}"


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point: parse --forecasts and --metrics, print score lines, return 0."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--forecasts",
        default="forecasts.json",
        help="Path to forecasts JSON file",
    )
    parser.add_argument(
        "--metrics",
        default="out/metrics.json",
        help="Path to metrics JSON file",
    )
    args = parser.parse_args(argv)

    forecasts_path = pathlib.Path(args.forecasts)
    metrics_path = pathlib.Path(args.metrics)

    forecasts_data = json.load(forecasts_path.open())
    metrics_data = json.load(metrics_path.open())

    results = score(forecasts_data.get("forecasts") or forecasts_data.get("tripwires") or [], metrics_data)

    for r in results:
        print(
            f"{r['id']} {r['status']} on_track={r['on_track']} "
            f"value={r['value']} {r['op']} {r['threshold']} "
            f"due {r['due']} (as of {r['as_of']})"
        )
    print(summary(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
