import sys, os, json, pathlib, io, contextlib, tempfile, math, inspect, re

# Insert lane root and optional src/ to import path as required by the contract.
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

# Import the module under test.
import score

# ----------------------------------------------------------------------
# Helper utilities for the tests.
# ----------------------------------------------------------------------


def _load_json(path: pathlib.Path):
    """Load a JSON file and return the parsed object."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _run_score_main(forecasts_path: pathlib.Path, metrics_path: pathlib.Path):
    """Execute score.main() with the supplied file paths, capturing stdout."""
    argv = [
        "--forecasts",
        str(forecasts_path),
        "--metrics",
        str(metrics_path),
    ]
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        ret = score.main(argv=argv)
    output = capture.getvalue()
    return ret, output


# ----------------------------------------------------------------------
# Test clauses – one function per numbered clause in the SPEC.
# Each contains at least one plain assert with a helpful message.
# ----------------------------------------------------------------------


def test_get():
    """(i) score.get() returns numeric values, None for missing or bool."""
    metrics_sample = {
        "a": {"b": 1.5, "c": True},
        "d": 2,
        "e": {"f": {"g": 3}},
    }
    assert score.get(metrics_sample, "a.b") == 1.5, "Existing float path should be returned"
    assert score.get(metrics_sample, "d") == 2, "Top‑level int should be returned"
    assert score.get(metrics_sample, "e.f.g") == 3, "Deeply nested int should be returned"
    # Bool is not considered numeric.
    assert score.get(metrics_sample, "a.c") is None, "Bool leaf must yield None"
    # Missing intermediate key.
    assert score.get(metrics_sample, "x.y") is None, "Missing top‑level key yields None"
    # Missing leaf under existing parent.
    assert score.get(metrics_sample, "e.f.z") is None, "Missing leaf under existing dict yields None"


def test_holds():
    """(ii) score.holds() works for all operators and rejects unknown ops."""
    # All four valid operators.
    assert score.holds(5, "<", 10) is True, "< operator failed for true case"
    assert score.holds(10, "<=", 10) is True, "<= operator failed for equality case"
    assert score.holds(15, ">", 10) is True, "> operator failed for true case"
    assert score.holds(10, ">=", 10) is True, ">= operator failed for equality case"
    # False cases.
    assert score.holds(20, "<", 10) is False, "< operator false case failed"
    assert score.holds(5, ">", 10) is False, "> operator false case failed"
    # Invalid operator must raise ValueError.
    try:
        score.holds(1, "==", 1)
    except ValueError:
        pass
    else:
        assert False, "Invalid operator should raise ValueError"


def test_score_one():
    """(iii) score_one() yields correct status for PENDING, HIT, MISS, NO_DATA."""
    base_metrics = {
        "as_of": "2026-01-15",
        "val": {"num": 42},
    }

    # PENDING: as_of earlier than due.
    forecast_pending = {
        "id": "X1",
        "path": "val.num",
        "op": "<",
        "threshold": 100,
        "due": "2026-12-31",
        "side": "bear",
        "statement": "test",
    }
    res_pending = score.score_one(forecast_pending, base_metrics)
    assert res_pending["status"] == "PENDING", "Expected PENDING status"
    assert res_pending["on_track"] is True, "Pending on_track should reflect holds()"

    # HIT: as_of on/after due and condition holds.
    forecast_hit = dict(forecast_pending)
    forecast_hit.update({"id": "X2", "due": "2026-01-01"})  # due before as_of
    res_hit = score.score_one(forecast_hit, base_metrics)
    assert res_hit["status"] == "HIT", "Expected HIT when condition satisfied after due"
    assert res_hit["on_track"] is True, "HIT on_track must be True"

    # MISS: after due but condition fails.
    forecast_miss = dict(forecast_pending)
    forecast_miss.update({"id": "X3", "op": ">", "threshold": 100, "due": "2026-01-01"})
    res_miss = score.score_one(forecast_miss, base_metrics)
    assert res_miss["status"] == "MISS", "Expected MISS when condition fails after due"
    assert res_miss["on_track"] is False, "MISS on_track must be False"

    # NO_DATA: missing metric path.
    forecast_nodata = dict(forecast_pending)
    forecast_nodata.update({"id": "X4", "path": "val.missing", "due": "2026-12-31"})
    res_nodata = score.score_one(forecast_nodata, base_metrics)
    assert res_nodata["status"] == "NO_DATA", "Expected NO_DATA for absent metric"
    assert res_nodata["on_track"] is None, "NO_DATA on_track must be None"


def test_summary():
    """(iv) summary() produces correctly formatted aggregate string."""
    results = [
        {"status": "HIT"},
        {"status": "MISS"},
        {"status": "PENDING"},
        {"status": "NO_DATA"},
        {"status": "HIT"},
    ]
    txt = score.summary(results)
    # Expected counts: hits=2, misses=1, pending=1, no_data=1
    expected = "SCORE: hits=2 misses=1 pending=1 no_data=1"
    assert txt == expected, f"Summary mismatch: got {txt!r}, expected {expected!r}"


def test_main(tmp_path):
    """(v) main() prints per‑forecast lines and a final summary line."""
    # Create a tiny metrics JSON.
    metrics_obj = {
        "as_of": "2026-06-01",
        "active": {"avg_30d": 120000},
        "fee_usd": {"avg_30d": 20000},
        "vol_near": {"avg_30d": 50000000},
    }
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics_obj), encoding="utf-8")

    # Create a forecasts JSON mirroring the lane‑root spec.
    forecasts_obj = {
        "made": "2026-11-12",
        "forecasts": [
            {
                "id": "F1",
                "side": "bear",
                "statement": "",
                "path": "active.avg_30d",
                "op": "<",
                "threshold": 150000,
                "due": "2027-02-12",
            },
            {
                "id": "F2",
                "side": "bear",
                "statement": "",
                "path": "fee_usd.avg_30d",
                "op": "<",
                "threshold": 25000,
                "due": "2027-02-12",
            },
            {
                "id": "F3",
                "side": "bull",
                "statement": "",
                "path": "vol_near.avg_30d",
                "op": ">=",
                "threshold": 40000000,
                "due": "2027-02-12",
            },
        ],
    }
    forecasts_path = tmp_path / "forecasts.json"
    forecasts_path.write_text(json.dumps(forecasts_obj), encoding="utf-8")

    # Run the CLI.
    ret, out = _run_score_main(forecasts_path, metrics_path)
    assert ret == 0, "score.main() should exit with status 0 on success"

    lines = out.strip().splitlines()
    # Expect three result lines + one summary line.
    assert len(lines) == 4, f"Expected 4 output lines, got {len(lines)}"

    # Verify the last line matches the summary function.
    expected_summary = score.summary(score.score(forecasts_obj["forecasts"], metrics_obj))
    assert lines[-1] == expected_summary, "Final line must be the exact summary string"


def test_forecast_ids():
    """(vi) forecasts.json at lane root loads and contains the three expected IDs."""
    forecasts_path = pathlib.Path(_R) / "forecasts.json"
    assert forecasts_path.is_file(), "forecasts.json must exist at repository root"
    data = _load_json(forecasts_path)
    ids = [f["id"] for f in data.get("forecasts", [])]
    assert ids == ["F1", "F2", "F3"], f"Forecast IDs mismatch: {ids!r}"


def test_score_source():
    """(vii) score.py must not import forbidden modules."""
    src_path = pathlib.Path(_R) / "score.py"
    text = src_path.read_text(encoding="utf-8")
    forbidden = ["urllib", "requests", "boto3", "socket", "subprocess", "environ"]
    for token in forbidden:
        assert token not in text, f"Forbidden token '{token}' found in score.py"


def test_verify_source():
    """(viii) verify.py must not import forbidden modules."""
    src_path = pathlib.Path(_R) / "verify.py"
    text = src_path.read_text(encoding="utf-8")
    forbidden = ["urllib", "requests", "boto3", "socket", "subprocess", "environ"]
    for token in forbidden:
        assert token not in text, f"Forbidden token '{token}' found in verify.py"


# ----------------------------------------------------------------------
# Runner for the GATE harness.
# ----------------------------------------------------------------------


def _run_all():
    """Execute every test_ function, providing a fresh temporary directory where needed."""
    # Collect functions defined in this module whose name starts with 'test_'.
    test_funcs = [obj for name, obj in globals().items() if name.startswith("test_") and callable(obj)]

    # Create a single temporary directory for functions that request tmp_path.
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = pathlib.Path(td)
        for fn in test_funcs:
            # Inspect the signature to decide whether to pass tmp_path.
            if "tmp_path" in inspect.signature(fn).parameters:
                fn(tmp_dir)
            else:
                fn()


if __name__ == "__main__":
    _run_all()
    print("PASS")
