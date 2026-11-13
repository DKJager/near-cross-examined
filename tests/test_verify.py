import sys, os, json, math, pathlib, contextlib, io
# Add lane root and optional src/ to import path
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

# Import the module under test
import verify

# ----------------------------------------------------------------------
# Test clauses for verify.py as specified in the contract.
# Each clause is implemented as a separate test_ function with at
# least one assert statement (including a helpful message).
# ----------------------------------------------------------------------


def test_1_flatten():
    """(i) flatten example from the spec."""
    data = {"a": {"b": 1, "c": "x"}, "d": 2.5, "e": True}
    expected = {"a.b": 1, "d": 2.5}
    result = verify.flatten(data)
    assert isinstance(result, dict), "flatten should return a dict"
    assert result == expected, f"flatten result {result!r} != expected {expected!r}"


def test_2_same_nan():
    """(ii) NaN equals NaN in same(); also a normal close comparison."""
    a = math.nan
    b = math.nan
    assert verify.same(a, b), "same should treat NaN as equal"
    # Numbers that are close enough
    assert verify.same(1.0000000001, 1.0), "same should be true for close numbers"
    # Numbers that are not close
    assert not verify.same(1.01, 1.0), "same should be false for numbers differing > rel_tol"


def test_3_compare_equal_and_diff():
    """(iii) compare returns [] for identical dicts and a DIFF line for 1% change."""
    committed = {"a": {"b": 1.0}}
    rebuilt_same = {"a": {"b": 1.0}}
    rebuilt_diff = {"a": {"b": 1.01}}  # 1% difference, far above rel_tol
    # No differences
    assert verify.compare(committed, rebuilt_same) == [], "compare should return empty list when equal"
    # One difference
    diff_list = verify.compare(committed, rebuilt_diff)
    expected = ["DIFF a.b committed=1.0 rebuilt=1.01"]
    assert diff_list == expected, f"compare diff list {diff_list!r} != expected {expected!r}"


def test_4_compare_missing():
    """(iv) compare reports missing paths in both directions."""
    committed = {"a": {"b": 1, "c": 2}}
    rebuilt = {"a": {"b": 1, "d": 3}}
    result = verify.compare(committed, rebuilt)
    # Expected missing entries, sorted alphabetically
    # sorted by path: a.c before a.d
    expected = [
        "MISSING_IN_REBUILT a.c",
        "MISSING_IN_COMMITTED a.d"
    ]
    assert result == expected, f"compare missing list {result!r} != expected {expected!r}"


def test_5_check_citations():
    """(v) check_citations flags wrong values and absent paths, passes correct ones."""
    # Metrics with two numeric leaves
    metrics = {"x": {"y": 10}, "z": 5}
    panel = {
        "claims": [
            {
                "id": "c1",
                "evidence": [
                    {"path": "x.y", "value": 10},      # correct
                    {"path": "z", "value": 6}          # wrong value
                ]
            },
            {
                "id": "c2",
                "evidence": [
                    {"path": "missing.path", "value": 1}  # absent path
                ]
            },
            {
                "id": "c3"  # no evidence key => zero citations, should not produce BAD_CITATION
            }
        ]
    }
    result = verify.check_citations(panel, metrics)
    expected = [
        "BAD_CITATION c1 z",
        "BAD_CITATION c2 missing.path"
    ]
    assert result == expected, f"check_citations result {result!r} != expected {expected!r}"


def test_6_main_success(tmp_path):
    """(vi) main() with injected compute returns 0 and prints a line starting with VERIFY OK."""
    # Prepare committed metrics JSON
    committed = {"a": {"b": 1}, "c": 2}
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(committed))

    # Panel referencing the same numbers
    panel = {
        "claims": [
            {
                "id": "claim1",
                "evidence": [
                    {"path": "a.b", "value": 1},
                    {"path": "c", "value": 2}
                ]
            }
        ]
    }
    panel_path = tmp_path / "panel.json"
    panel_path.write_text(json.dumps(panel))

    # Compute function returns exactly the committed dict (no changes)
    def compute(_):
        return {"a": {"b": 1}, "c": 2}

    # Capture stdout
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ret = verify.main(
            argv=[
                "--metrics", str(metrics_path),
                "--panel", str(panel_path)
            ],
            compute=compute
        )
    out = buf.getvalue().strip().splitlines()
    # Expect return code 0
    assert ret == 0, f"main should return 0 on success, got {ret}"
    # Expect at least one line starting with VERIFY OK
    assert any(line.startswith("VERIFY OK:") for line in out), f"No VERIFY OK line in output: {out}"
    # Ensure the last line is the VERIFY OK line (spec prints only that line on success)
    assert out[-1].startswith("VERIFY OK:"), f"Last line should be VERIFY OK, got {out[-1]}"


def test_7_main_failure(tmp_path):
    """(vii) main() with injected compute that changes a number returns 1 and prints VERIFY FAILED."""
    # Committed metrics
    committed = {"a": {"b": 1}, "c": 2}
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(committed))

    # Panel references the original numbers
    panel = {
        "claims": [
            {
                "id": "claim1",
                "evidence": [
                    {"path": "a.b", "value": 1},
                    {"path": "c", "value": 2}
                ]
            }
        ]
    }
    panel_path = tmp_path / "panel.json"
    panel_path.write_text(json.dumps(panel))

    # Compute returns a dict with a changed number (triggering a DIFF)
    def compute(_):
        return {"a": {"b": 1.5}, "c": 2}

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ret = verify.main(
            argv=[
                "--metrics", str(metrics_path),
                "--panel", str(panel_path)
            ],
            compute=compute
        )
    out = buf.getvalue().strip().splitlines()
    # Return code should be 1
    assert ret == 1, f"main should return 1 on failure, got {ret}"
    # The last line must be exactly "VERIFY FAILED: 1 problems"
    assert out[-1] == "VERIFY FAILED: 1 problems", f"Last line mismatch: {out[-1]!r}"
    # Ensure a DIFF line appears before the final line
    diff_lines = [line for line in out if line.startswith("DIFF")]
    assert diff_lines, f"No DIFF line found in output: {out}"


# ----------------------------------------------------------------------
# Runner: call every test_ function (including those that accept fixtures).
# Pytest will supply tmp_path automatically; when run as a script we mimic
# that by creating a temporary directory ourselves for the functions that
# request it.
# ----------------------------------------------------------------------
def _run_test(func):
    """Execute a test function, providing a temporary directory if required."""
    import inspect
    sig = inspect.signature(func)
    if "tmp_path" in sig.parameters:
        # Create a temporary directory using pathlib's TemporaryDirectory context
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td)
            func(path)
    else:
        func()


def _collect_tests():
    """Yield all callables whose name starts with 'test_'."""
    for name, obj in globals().items():
        if name.startswith("test_") and callable(obj):
            yield obj


if __name__ == "__main__":
    # Execute each test; any AssertionError will abort the script.
    for test_func in _collect_tests():
        _run_test(test_func)
    # All assertions passed – print the required PASS token.
    print("PASS")
