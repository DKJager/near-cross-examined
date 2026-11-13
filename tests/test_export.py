import sys, os, pathlib, json, hashlib, csv, inspect, tempfile

# Add lane root and optional src/ to import path
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

from export_csv import export_charts, export_intents, write_sums, sums_lines
from verify import check_sums, main as verify_main
import verify

def test_export_charts(tmp_path: pathlib.Path):
    """Fixture charts_raw.json → CSV, check return count and exact output."""
    data = {
        "charts": [
            {"date": "2026-11-08T00:00:00.000Z", "txns": "5", "multichain_txns": None},
            {"date": "2026-11-09T00:00:00.000Z", "near_price": "4.5", "txns": "7"},
        ]
    }
    src = tmp_path / "charts_raw.json"
    dst = tmp_path / "nearblocks_daily.csv"
    src.write_text(json.dumps(data))
    rc = export_charts(str(src), str(dst))
    assert rc == 2, f"export_charts returned {rc}, expected 2 rows"
    expected = (
        "date,near_price,market_cap,total_supply,circulating_supply,blocks,gas_fee,gas_used,txns,txn_volume,txn_volume_usd,txn_fee,txn_fee_usd,new_accounts,active_accounts,deleted_accounts,new_contracts,active_contracts,unique_contracts,multichain_txns\n"
        "2026-11-08T00:00:00.000Z,,,,,,,,5,,,,,,,,,,,\n"
        "2026-11-09T00:00:00.000Z,4.5,,,,,,,7,,,,,,,,,,,\n"
    )
    actual = dst.read_text()
    assert actual == expected, "CSV output does not match expected exact text"

def test_export_intents(tmp_path: pathlib.Path):
    """Fixture intents_days.json → CSV, check return count and exact output."""
    rows = [
        {
            "date": "2025-11-09",
            "swaps": 12784,
            "usd": 32835822.393300097,
            "pages": 13,
            "top_origin": [],
        }
    ]
    src = tmp_path / "intents_days.json"
    dst = tmp_path / "intents_sundays.csv"
    src.write_text(json.dumps(rows))
    rc = export_intents(str(src), str(dst))
    assert rc == 1, f"export_intents returned {rc}, expected 1 row"
    expected = "date,swaps,usd,pages\n2025-11-09,12784,32835822.393300097,13\n"
    actual = dst.read_text()
    assert actual == expected, "CSV output for intents does not match expected exact text"

def test_write_sums_and_check_sums(tmp_path: pathlib.Path):
    """Create files a.txt, b.json, .hidden; test sums_lines, write_sums, and verify.check_sums."""
    # create files
    a = tmp_path / "a.txt"
    b = tmp_path / "b.json"
    hidden = tmp_path / ".hidden"
    a.write_bytes(b"a\n")
    b.write_bytes(b"{}\n")
    hidden.write_bytes(b"secret")
    # expected hashes
    def sha256_path(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    expected_lines = [f"{sha256_path(a)}  a.txt", f"{sha256_path(b)}  b.json"]
    # test sums_lines
    lines = sums_lines(str(tmp_path))
    assert lines == expected_lines, f"sums_lines returned {lines}, expected {expected_lines}"
    # first write_sums
    cnt1 = write_sums(str(tmp_path))
    assert cnt1 == 2, f"write_sums first call returned {cnt1}, expected 2"
    # file content
    sums_path = tmp_path / "SHA256SUMS"
    content = sums_path.read_text().splitlines()
    assert content == expected_lines, "SHA256SUMS content mismatch after first write"
    # second write_sums should still list 2 (does not list itself)
    cnt2 = write_sums(str(tmp_path))
    assert cnt2 == 2, f"write_sums second call returned {cnt2}, expected 2"
    # verify.check_sums initially empty
    problems0 = check_sums(str(tmp_path))
    assert problems0 == [], f"Initial check_sums returned {problems0}, expected empty list"
    # modify a.txt to cause mismatch
    a.write_bytes(b"changed")
    problems1 = check_sums(str(tmp_path))
    assert problems1 == ["HASH_MISMATCH a.txt"], f"After modifying a.txt got {problems1}"
    # add unlisted file c.txt
    c = tmp_path / "c.txt"
    c.write_bytes(b"new")
    problems2 = check_sums(str(tmp_path))
    # order may vary, ensure both messages present
    assert "UNLISTED_DATA_FILE c.txt" in problems2, f"Missing UNLISTED_DATA_FILE in {problems2}"
    # delete b.json to cause missing entry
    b.unlink()
    problems3 = check_sums(str(tmp_path))
    assert "HASH_FILE_MISSING b.json" in problems3, f"Missing HASH_FILE_MISSING in {problems3}"
    # remove SHA256SUMS to test missing file case
    sums_path.unlink()
    problems4 = check_sums(str(tmp_path))
    expected_missing = f"SUMS_MISSING {os.path.join(str(tmp_path), 'SHA256SUMS')}"
    assert problems4 == [expected_missing], f"Expected missing list {expected_missing}, got {problems4}"

def test_verify_main_with_injected_compute(tmp_path: pathlib.Path):
    """Run verify.main with injected compute and a bad SHA256SUMS; expect exit code 1."""
    # create dummy metrics.json and panel.json (empty but valid JSON)
    (tmp_path / "out").mkdir()
    metrics_path = tmp_path / "out" / "metrics.json"
    panel_path = tmp_path / "out" / "panel.json"
    metrics_path.write_text("{}")
    panel_path.write_text('{"claims": []}')
    # create data folder with a file and a wrong hash line
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    bad_file = data_dir / "bad.txt"
    bad_file.write_bytes(b"content")
    # compute correct hash then write wrong hash line
    correct_hash = hashlib.sha256(bad_file.read_bytes()).hexdigest()
    wrong_hash = "0"*64
    sums_path = data_dir / "SHA256SUMS"
    sums_path.write_text(f"{wrong_hash}  bad.txt\n")
    # run verify.main with compute that returns empty dict
    rc = verify_main(
        [
            f"--data={str(data_dir)}",
            f"--metrics={str(metrics_path)}",
            f"--panel={str(panel_path)}",
            f"--sums-dir={str(data_dir)}",
        ],
        compute=lambda _: {}
    )
    assert rc == 1, f"verify.main should return 1 due to hash mismatch, got {rc}"

def test_real_data_sums():
    """On the real lane, verify.check_sums('data') should be empty and SHA256SUMS list ≥16 files."""
    cwd = os.getcwd()
    try:
        os.chdir(_R)
        problems = check_sums("data")
        assert problems == [], f"Real data check_sums returned problems: {problems}"
        sums_file = pathlib.Path("data") / "SHA256SUMS"
        lines = [ln for ln in sums_file.read_text().splitlines() if ln.strip()]
        names = [ln.split("  ", 1)[1] for ln in lines]
        assert "nearblocks_daily.csv" in names, "nearblocks_daily.csv missing from SHA256SUMS"
        assert "intents_sundays.csv" in names, "intents_sundays.csv missing from SHA256SUMS"
        assert len(names) >= 16, f"Expected at least 16 entries in SHA256SUMS, got {len(names)}"
    finally:
        os.chdir(cwd)

if __name__ == "__main__":
    # Run all test_* functions; provide a fresh TemporaryDirectory for any that request tmp_path.
    for name, func in list(globals().items()):
        if callable(func) and name.startswith("test_"):
            sig = inspect.signature(func)
            if "tmp_path" in sig.parameters:
                with tempfile.TemporaryDirectory() as td:
                    tmp_path = pathlib.Path(td)
                    func(tmp_path)
            else:
                func()
    print("PASS")
