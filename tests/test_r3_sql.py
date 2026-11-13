import sys, os, io, inspect, tempfile, pathlib, shutil, csv, hashlib, json, re, textwrap, importlib

# Ensure lane root and optional src/ are on import path.
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

# ----------------------------------------------------------------------
# Helper utilities used by the test suite.
# ----------------------------------------------------------------------
def _read_file(path: pathlib.Path) -> str:
    """Read a text file and return its content as a string."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _assert_msg(file: str, detail: str) -> str:
    """Standardise assertion messages."""
    return f"{file}: {detail}"

def _run_main(module, args):
    """Run a module's main function and capture its stdout."""
    stdout = io.StringIO()
    saved = sys.stdout
    try:
        sys.stdout = stdout
        ret = module.main(args)
    finally:
        sys.stdout = saved
    output = stdout.getvalue()
    return ret, output

def _tmp_dir():
    """Create a temporary directory that cleans itself up."""
    return tempfile.TemporaryDirectory()

# ----------------------------------------------------------------------
# (i) test_sql_files_filter_block_date
# ----------------------------------------------------------------------
def test_sql_files_filter_block_date():
    """Verify the three SQL files exist and contain required clauses."""
    sql_dir = pathlib.Path(_R) / "sql"
    expected = {
        "active_accounts_daily.sql": ["crypto_near_mainnet_us", "block_date", "@start_date"],
        "transactions_daily.sql": ["crypto_near_mainnet_us", "block_date", "@start_date"],
        "contract_usage_daily.sql": ["crypto_near_mainnet_us", "block_date", "@start_date"],
    }
    for fname, tokens in expected.items():
        path = sql_dir / fname
        assert path.is_file(), _assert_msg(fname, "file missing")
        content = _read_file(path)
        # First line must be a comment.
        first_line = content.splitlines()[0].strip()
        assert first_line.startswith("--"), _assert_msg(fname, "first line not a comment")
        # Ensure each required token appears.
        for token in tokens:
            assert token in content, _assert_msg(fname, f"missing token '{token}'")
        # Verify that after the word WHERE there is a block_date occurrence.
        where_idx = content.find("WHERE")
        assert where_idx != -1, _assert_msg(fname, "no WHERE clause")
        after_where = content[where_idx:]
        assert "block_date" in after_where, _assert_msg(fname, "block_date not after WHERE")

# ----------------------------------------------------------------------
# (ii) test_bq_fetch_no_option_prints_queries
# ----------------------------------------------------------------------
def test_bq_fetch_no_option_prints_queries():
    """Calling bq_fetch.main([]) must print each query and return 0."""
    import bq_fetch
    # Capture the output.
    ret, out = _run_main(bq_fetch, [])
    assert ret == 0, _assert_msg("bq_fetch.py", "non‑zero return")
    # Each query file should be printed with its path and SQL.
    for name, rel_path in bq_fetch.QUERIES.items():
        sql_path = pathlib.Path(_R) / rel_path
        sql_text = _read_file(sql_path)
        # The output contains the relative path preceded by '-- '.
        marker = f"-- {rel_path}"
        assert marker in out, _assert_msg("bq_fetch.py", f"missing marker '{marker}'")
        # The SQL text (ignoring leading comment lines) should appear.
        sql_body = "\n".join([ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")])
        assert sql_body.strip() in out, _assert_msg("bq_fetch.py", f"SQL for {name} not printed")

# ----------------------------------------------------------------------
# (iii) test_bq_fetch_from_fixture
# ----------------------------------------------------------------------
def test_bq_fetch_from_fixture(tmp_path):
    """Run bq_fetch with fixture CSVs and verify files, SHA256SUMS and MANIFEST."""
    import bq_fetch

    # ------------------------------------------------------------------
    # Prepare fixture CSVs (three rows + header).
    # ------------------------------------------------------------------
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    rows = [
        ["block_date", "value"],
        ["2022-01-01", "10"],
        ["2022-01-02", "20"],
        ["2022-01-03", "30"],
    ]
    for name in bq_fetch.QUERIES:
        csv_path = fixture_dir / f"{name}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            for row in rows:
                writer.writerow(row)

    # ------------------------------------------------------------------
    # Copy required real files into the temporary environment.
    # ------------------------------------------------------------------
    # out/metrics.json (used for date_range)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    shutil.copy2(os.path.join(_R, "out", "metrics.json"), out_dir / "metrics.json")
    # data/MANIFEST.json (initial manifest)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copy2(os.path.join(_R, "data", "MANIFEST.json"), data_dir / "MANIFEST.json")

    # ------------------------------------------------------------------
    # Run bq_fetch with the fixture directory and custom output folder.
    # ------------------------------------------------------------------
    out_folder = tmp_path / "outfiles"
    out_folder.mkdir()
    ret, out = _run_main(bq_fetch, ["--from-fixture", str(fixture_dir), "--out", str(out_folder)])
    assert ret == 0, _assert_msg("bq_fetch.py", "return code not zero for fixture mode")

    # ------------------------------------------------------------------
    # Verify each generated CSV file.
    # ------------------------------------------------------------------
    for key in bq_fetch.QUERIES:
        csv_path = out_folder / f"bq_{key}.csv"
        assert csv_path.is_file(), _assert_msg("bq_fetch.py", f"missing output {csv_path.name}")
        # Header line should be exactly "block_date,value"
        with open(csv_path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        assert first == "block_date,value", _assert_msg(csv_path.name, "header mismatch")
        # There should be three data rows.
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 4, _assert_msg(csv_path.name, "row count not 4 (header+3)")

    # ------------------------------------------------------------------
    # Verify SHA256SUMS content.
    # ------------------------------------------------------------------
    sums_path = out_folder / "SHA256SUMS"
    assert sums_path.is_file(), _assert_msg("bq_fetch.py", "SHA256SUMS missing")
    sums_lines = [ln.strip() for ln in sums_path.read_text().splitlines() if ln.strip()]
    # One line per CSV file, two spaces between hash and name.
    expected_names = {f"bq_{k}.csv" for k in bq_fetch.QUERIES}
    found_names = set()
    for line in sums_lines:
        parts = line.split("  ")
        assert len(parts) == 2, _assert_msg("SHA256SUMS", f"bad format line '{line}'")
        h, name = parts
        assert re.fullmatch(r"[0-9a-f]{64}", h), _assert_msg("SHA256SUMS", f"invalid hash '{h}'")
        found_names.add(name)
        # Compute hash ourselves and compare.
        file_path = out_folder / name
        with open(file_path, "rb") as f:
            data = f.read()
        calc = hashlib.sha256(data).hexdigest()
        assert calc == h, _assert_msg(name, "hash mismatch")
    assert expected_names == found_names, _assert_msg("SHA256SUMS", "missing or extra entries")

    # ------------------------------------------------------------------
    # Verify MANIFEST.json now contains entries for the three CSVs.
    # ------------------------------------------------------------------
    manifest_path = out_folder / "MANIFEST.json"
    assert manifest_path.is_file(), _assert_msg("bq_fetch.py", "MANIFEST.json missing after register")
    manifest = json.load(open(manifest_path, "r", encoding="utf-8"))
    for key in bq_fetch.QUERIES:
        fname = f"bq_{key}.csv"
        assert fname in manifest, _assert_msg("MANIFEST.json", f"entry for {fname} missing")
        entry = manifest[fname]
        for field in ("bytes", "fetched_at", "sha256", "url", "what"):
            assert field in entry, _assert_msg("MANIFEST.json", f"{fname} missing field {field}")

# ----------------------------------------------------------------------
# (iv) test_bq_fetch_run_without_credentials_returns_2
# ----------------------------------------------------------------------
def test_bq_fetch_run_without_credentials_returns_2():
    """When the BigQuery package is missing, bq_fetch.main(['--run']) returns 2."""
    import bq_fetch
    # Temporarily remove the google.cloud.bigquery module.
    default_data = pathlib.Path(_R) / "data"
    before = {k: (default_data / f"bq_{k}.csv").read_bytes() if (default_data / f"bq_{k}.csv").exists() else None for k in bq_fetch.QUERIES}
    saved = sys.modules.get("google.cloud.bigquery")
    sys.modules["google.cloud.bigquery"] = None
    try:
        ret, out = _run_main(bq_fetch, ["--run"])
    finally:
        # Restore original module state.
        if saved is None:
            sys.modules.pop("google.cloud.bigquery", None)
        else:
            sys.modules["google.cloud.bigquery"] = saved
    assert ret == 2, _assert_msg("bq_fetch.py", "expected return code 2 when credentials missing")
    expected_line = "bq_fetch.py: Google credentials or the google-cloud-bigquery package are missing; nothing was run"
    assert expected_line in out, _assert_msg("bq_fetch.py", "expected error message not printed")
    # Ensure the default data folder is unchanged (the committed BigQuery files, if any, stay as they were).
    for key in bq_fetch.QUERIES:
        csv_path = default_data / f"bq_{key}.csv"
        now = csv_path.read_bytes() if csv_path.exists() else None
        assert now == before[key], _assert_msg("bq_fetch.py", f"{csv_path.name} was created or changed by a failed --run")

def test_bq_fetch_from_fixture_keeps_existing_sums_lines(tmp_path):
    """Registering BigQuery files must keep the existing SHA256SUMS lines and refresh the MANIFEST.json line."""
    import hashlib, json, bq_fetch
    data = tmp_path / "data"; data.mkdir(); fx = tmp_path / "fx"; fx.mkdir()
    (data / "other.json").write_text("{}")
    (data / "MANIFEST.json").write_text("{}")
    def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    (data / "SHA256SUMS").write_text(f"{h(data / 'other.json')}  other.json\n{h(data / 'MANIFEST.json')}  MANIFEST.json\n")
    for k in bq_fetch.QUERIES:
        (fx / f"{k}.csv").write_text("block_date,value\n2026-01-01,5\n")
    assert bq_fetch.main(["--from-fixture", str(fx), "--out", str(data)]) == 0
    got = {ln.split()[1]: ln.split()[0] for ln in (data / "SHA256SUMS").read_text().splitlines()}
    assert got["other.json"] == h(data / "other.json"), "existing line lost"
    assert got["MANIFEST.json"] == h(data / "MANIFEST.json"), "MANIFEST.json hash not refreshed"
    for k in bq_fetch.QUERIES:
        assert got[f"bq_{k}.csv"] == h(data / f"bq_{k}.csv")
    assert len(got) == 5

# ----------------------------------------------------------------------
# Test runner – executes all test_* functions, providing a temporary
# directory for any that request a ``tmp_path`` argument.
# ----------------------------------------------------------------------
def _run_all_tests():
    # Discover all callables that start with ``test_`` in this module.
    current_module = sys.modules[__name__]
    for name, obj in list(vars(current_module).items()):
        if not name.startswith("test_"):
            continue
        if not callable(obj):
            continue
        sig = inspect.signature(obj)
        if "tmp_path" in sig.parameters:
            with _tmp_dir() as td:
                td_path = pathlib.Path(td)
                # The pytest fixture ``tmp_path`` is a pathlib.Path.
                obj(td_path)
        else:
            obj()

if __name__ == "__main__":
    _run_all_tests()
    print("PASS")
