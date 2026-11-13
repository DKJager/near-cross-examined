import sys, os, io, re, shutil, pathlib, json, contextlib, subprocess, math, hashlib, csv
# Add lane root and src/ to sys.path
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

# Import modules to be tested
import thesis_doc
import verify
import export_csv
import dashboard

def test_main_check_ok():
    """thesis_doc.main(['--check']) should succeed and print DOCS OK line."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ret = thesis_doc.main(["--check"])
    out = buf.getvalue().strip().splitlines()
    assert ret == 0, "thesis_doc.main(--check) returned non-zero"
    assert out, "thesis_doc.main(--check) printed nothing"
    assert out[-1].startswith("DOCS OK:"), f"Last line not DOCS OK: {out[-1]}"

def test_tripwires_and_forecasts():
    """Tripwires + forecasts count, IDs, paths, ops and due dates."""
    # Load data
    m, p, f, t, man = thesis_doc.load()
    flat = verify.flatten(m)
    # Load tripwires and forecasts
    with open(os.path.join(_R, "tripwires.json")) as fp:
        tw = json.load(fp)
    with open(os.path.join(_R, "forecasts.json")) as fp:
        fc = json.load(fp)
    # counts
    total = len(tw["tripwires"]) + len(fc["forecasts"])
    assert total == 9, f"Expected 9 rows, got {total}"
    # IDs
    tw_ids = {it["id"] for it in tw["tripwires"]}
    fc_ids = {it["id"] for it in fc["forecasts"]}
    assert tw_ids == {"T1","T2","T3","T4","T5","T6"}, f"Tripwire IDs mismatch: {tw_ids}"
    assert fc_ids == {"F1","F2","F3"}, f"Forecast IDs mismatch: {fc_ids}"
    # check each item
    allowed_ops = {"<", "<=", ">", ">="}
    for item in tw["tripwires"] + fc["forecasts"]:
        path = item["path"]
        assert path in flat, f"path {path} not in metric flatten"
        op = item["op"]
        assert op in allowed_ops, f"op {op} not allowed"
        due = item["due"]
        assert due > "2026-11-14", f"due {due} not after 2026-11-14"

def test_backticked_tokens():
    """All backticked metric tokens are present in flatten and at least 25 distinct."""
    m, p, f, t, man = thesis_doc.load()
    flat = verify.flatten(m)
    # Gather documents
    docs = [
        thesis_doc.thesis(m, p, f, t),
        thesis_doc.tripwires(m, p, f, t, man),
        thesis_doc.weaknesses(m, p, f, t, man),
    ]
    tokens = set()
    pattern = re.compile(r"`([^`\s]+)`")
    for doc in docs:
        for tok in pattern.findall(doc):
            if "." in tok and "/" not in tok and not tok.endswith((".py",".json",".md")):
                tokens.add(tok)
    assert tokens, "No backticked tokens found"
    missing = [tok for tok in tokens if tok not in flat]
    assert not missing, f"Backticked tokens missing in metrics: {missing}"
    assert len(tokens) >= 25, f"Only {len(tokens)} distinct backticked tokens, need >=25"

def test_money_cases():
    """money() formatting matches spec for boundary values."""
    # Billion case
    assert thesis_doc.money(1_500_000_000) == "$1.50 billion", "Billion formatting failed"
    # Million case
    assert thesis_doc.money(2_340_000) == "$2.3 million", "Million formatting failed"
    # Small case
    assert thesis_doc.money(12345) == "$12,345", "Small integer formatting failed"
    # Test example from contract
    assert thesis_doc.money(59_295_359.42) == "$59.3 million", "Example money formatting failed"

def test_thesis_content():
    """THESIS.md contains required computed strings and panel size sentence."""
    m, p, f, t, man = thesis_doc.load()
    with open(os.path.join(_R, "THESIS.md")) as fp:
        txt = fp.read()
    # Money(apps.fees_usd_365d)
    apps = m["apps"]
    assert thesis_doc.money(apps["fees_usd_365d"]) in txt, "apps.fees_usd_365d money not found"
    # apps.x_gas_fees formatted as integer with commas
    assert f"{apps['x_gas_fees']:,.0f}" in txt, "apps.x_gas_fees formatting missing"
    # intents_share percent
    assert f"{apps['intents_share_30d']*100:.0f}%" in txt, "intents_share percent missing"
    # holders.cover_of_issuance_pct percent
    holders = m["holders"]
    assert f"{holders['cover_of_issuance_pct']:.0f}%" in txt, "holders.cover_of_issuance_pct percent missing"
    # valuation multiple
    valuation = m["valuation"]
    assert f"{valuation['mcap_to_intents_revenue_annualised']:,.0f}" in txt, "valuation multiple missing"
    # panel size sentence
    judges = len(p["judges"])
    claim_cnt = len(p["claims"])
    expected_sentence = f"This entry uses a {judges}-judge panel: {judges} judges from {judges} makers on {claim_cnt} claims."
    assert expected_sentence in txt, "Panel size sentence missing or incorrect"

def test_weaknesses_content():
    """WEAKNESSES.md has W1..W10 headings, 10 Source lines, and required texts."""
    m, p, f, t, man = thesis_doc.load()
    with open(os.path.join(_R, "WEAKNESSES.md")) as fp:
        txt = fp.read()
    # Check headings
    for i in range(1, 11):
        assert f"## W{i}" in txt, f"Missing heading W{i}"
    # Count Source lines
    source_lines = [line for line in txt.splitlines() if line.startswith("Source: ")]
    assert len(source_lines) == 10, f"Expected 10 Source lines, got {len(source_lines)}"
    # Required phrases
    assert "Staking is not measured" in txt, "Missing 'Staking is not measured'"
    assert "Fee-rate compression" in txt, "Missing 'Fee-rate compression'"

def test_tripwires_content():
    """TRIPWIRES.md contains required sections and computed counterfactual paragraphs."""
    m, p, f, t, tw = thesis_doc.load()
    with open(os.path.join(_R, "TRIPWIRES.md")) as fp:
        txt = fp.read()
    # Section headings
    assert "## Two counterfactuals" in txt, "Missing Two counterfactuals heading"
    # Counterfactual 1 paragraph
    paradox = m["paradox"]
    cf1_pat = re.compile(
        r"\*\*1\. If NEAR moved per transaction had not changed, NEAR-denominated transfer volume would have fallen about as far as transactions did\.\*\* "
        r"NEAR moved per transaction is ([\d\.]+) times what it was a year ago .*"
    )
    match = cf1_pat.search(txt)
    assert match, "Counterfactual 1 paragraph not found"
    # Verify the numeric value matches computed one (rounded to 1 decimal)
    expected_val = f"{paradox['near_per_txn_x']:.1f}"
    assert expected_val in match.group(0), f"Counterfactual 1 value mismatch: expected {expected_val}"
    # Ensure forbidden strings not present
    assert "6.3x" not in txt, "Forbidden string '6.3x' found"
    assert "paradox table above" not in txt, "Forbidden phrase 'paradox table above' found"
    # New sections
    assert "## How NEAR Intents is sampled" in txt, "Missing sampling section"
    assert "## Data integrity" in txt, "Missing data integrity section"

def test_no_forbidden_strings():
    """Public files must not contain forbidden strings."""
    forbidden = ["openrouter", "XXL", "6 of 6"]
    public_files = [
        os.path.join(_R, "README.md"),
        os.path.join(_R, "THESIS.md"),
        os.path.join(_R, "TRIPWIRES.md"),
        os.path.join(_R, "WEAKNESSES.md"),
        os.path.join(_R, "Makefile"),
        os.path.join(_R, "forecasts.json"),
        os.path.join(_R, "out", "index.html"),
        os.path.join(_R, "docs", "index.html"),
    ]
    # Add all *.py in lane root
    for fname in os.listdir(_R):
        if fname.endswith(".py"):
            public_files.append(os.path.join(_R, fname))
    # Add data files
    public_files.append(os.path.join(_R, "data", "MANIFEST.json"))
    # Add sql files
    sql_dir = os.path.join(_R, "sql")
    for f in os.listdir(sql_dir):
        if f.endswith(".sql"):
            public_files.append(os.path.join(sql_dir, f))
    for path in public_files:
        if not os.path.isfile(path):
            continue
        with open(path, "r", errors="ignore") as fp:
            content = fp.read()
        for bad in forbidden:
            if bad in content:
                raise AssertionError(f"Forbidden string '{bad}' found in {path}")

def test_weaknesses_stale_detection():
    """Changing WEAKNESSES.md makes thesis_doc report stale docs."""
    # Copy repo to temp dir
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        # copy needed files
        src_root = pathlib.Path(_R)
        dst_root = pathlib.Path(tmp)
        # copy out, data, forecasts, tripwires, panel, README, THESIS, TRIPWIRES, WEAKNESSES
        for rel in ["out", "data", "forecasts.json", "tripwires.json", "out/panel.json",
                    "README.md", "THESIS.md", "TRIPWIRES.md", "WEAKNESSES.md"]:
            src = src_root / rel
            dst = dst_root / rel
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        # modify WEAKNESSES.md slightly
        wk_path = dst_root / "WEAKNESSES.md"
        with open(wk_path, "r", encoding="utf-8") as fp:
            data = fp.read()
        # flip a character
        data = data.replace("Staking is not measured", "Staking is not measuredX")
        with open(wk_path, "w", encoding="utf-8") as fp:
            fp.write(data)
        # run thesis_doc.main in that dir
        cwd = os.getcwd()
        os.chdir(dst_root)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ret = thesis_doc.main(["--check"])
        out = buf.getvalue()
        os.chdir(cwd)
        assert ret == 1, "Expected exit code 1 for stale docs"
        assert "DOCS OUT OF DATE:" in out, "Missing DOCS OUT OF DATE line"
        assert "WEAKNESSES.md" in out, "WEAKNESSES.md not reported as stale"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_no_forbidden_imports():
    """Ensure listed python files contain no forbidden import patterns."""
    bad_patterns = [
        r"import\s+urllib",
        r"import\s+requests",
        r"import\s+subprocess",
        r"os\.environ",
        r"import\s+socket",
    ]
    py_files = ["thesis_doc.py", "export_csv.py", "verify.py", "dashboard.py", "metrics.py", "bq_fetch.py"]
    for fname in py_files:
        path = os.path.join(_R, fname)
        with open(path, "r", errors="ignore") as fp:
            content = fp.read()
        for pat in bad_patterns:
            if re.search(pat, content):
                raise AssertionError(f"Forbidden pattern '{pat}' found in {fname}")

if __name__ == "__main__":
    # Run all test_ functions
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
    print("PASS")
