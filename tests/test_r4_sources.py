"""Two verification modes: offline from the committed files, online from a fresh download (verify_online.py)."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import verify  # noqa: E402

COMMITTED = ["MANIFEST.json", "SHA256SUMS", "DERIVED_SHA256SUMS", "RAW_NOT_COMMITTED.txt",
             "bq_active_accounts_daily.csv", "bq_contract_usage_daily.csv", "bq_transactions_daily.csv"]


def _shipped_copy(tmp_path):
    """A copy that holds only what the public repository ships (no source files)."""
    (tmp_path / "data").mkdir()
    (tmp_path / "out").mkdir()
    for n in COMMITTED:
        shutil.copy(ROOT / "data" / n, tmp_path / "data" / n)
    for n in ("metrics.json", "panel.json"):
        shutil.copy(ROOT / "out" / n, tmp_path / "out" / n)
    return tmp_path


def _args(root):
    return ["--mode", "offline", "--metrics", str(root / "out/metrics.json"), "--panel", str(root / "out/panel.json"),
            "--sums-dir", str(root / "data")]


def test_offline_mode_passes_on_the_shipped_files_only(tmp_path, capsys):
    root = _shipped_copy(tmp_path)
    assert verify.main(_args(root)) == 0
    out = capsys.readouterr().out
    assert "VERIFY OK (offline)" in out and "hashed but not shipped" in out


def test_offline_mode_catches_a_changed_number(tmp_path, capsys):
    root = _shipped_copy(tmp_path)
    p = root / "out" / "metrics.json"
    m = json.loads(p.read_text())
    m["active"]["avg_30d"] += 1
    p.write_text(json.dumps(m))
    assert verify.main(_args(root)) == 1
    assert "DERIVED_HASH_MISMATCH out/metrics.json" in capsys.readouterr().out


def test_offline_mode_catches_a_changed_bigquery_file(tmp_path, capsys):
    root = _shipped_copy(tmp_path)
    p = root / "data" / "bq_transactions_daily.csv"
    p.write_text(p.read_text().replace("2026-04-02,", "2026-04-02,9", 1))
    assert verify.main(_args(root)) == 1
    out = capsys.readouterr().out
    assert "HASH_MISMATCH bq_transactions_daily.csv" in out


def test_recorded_derived_hashes_are_current():
    assert verify.check_derived(str(ROOT / "out/metrics.json"), str(ROOT / "out/panel.json"),
                                str(ROOT / "data/DERIVED_SHA256SUMS")) == []


def test_bigquery_numbers_rebuild_from_the_committed_csv_alone():
    m = json.loads((ROOT / "out/metrics.json").read_text())["crosscheck"]
    b = verify.bq_only(str(ROOT / "data"))
    assert b["bq_txns_largest_drop_date"] == m["bq_txns_largest_drop_date"]
    assert abs(b["bq_txns_largest_daily_drop_pct"] - m["bq_txns_largest_daily_drop_pct"]) < 1e-9
    assert b["bq_txns_bigquery_days"] == m["bq_txns_bigquery_days"]


def test_every_unshipped_source_file_is_hashed_and_none_is_tracked_by_git():
    names = verify.uncommitted_names(str(ROOT / "data"))
    assert len(names) >= 15
    sums = (ROOT / "data" / "SHA256SUMS").read_text()
    for n in names:
        assert f"  {n}\n" in sums, f"{n} is not hashed in SHA256SUMS"
    if (ROOT / ".git").exists():
        tracked = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        leaked = [t for t in tracked if os.path.basename(t) in names]
        assert leaked == [], f"source files are tracked by git: {leaked}"
    if (ROOT / ".gitignore").exists():
        gi = (ROOT / ".gitignore").read_text()
        for n in names:
            assert f"data/{n}" in gi


def test_verify_never_touches_the_network_and_online_is_a_separate_script():
    assert "urllib" not in (ROOT / "verify.py").read_text()
    out = subprocess.run([sys.executable, "verify_online.py", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "--tol" in out.stdout


@pytest.mark.skipif(not (ROOT / "data" / "charts_raw.json").exists(), reason="needs the source files (python3 fetch.py)")
def test_as_of_ends_every_series_on_the_same_day():
    import metrics
    m = metrics.compute(str(ROOT / "data" / "charts_raw.json"), as_of="2026-10-01")
    assert m["as_of"] == "2026-10-01"
