import sys, os, pathlib, shutil, json, re, inspect, tempfile

# Ensure lane root and optional src/ are on import path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_ROOT, os.path.join(_ROOT, "src")]

def _copy_out(tmp_path: pathlib.Path) -> None:
    """Copy the real ``out`` directory into *tmp_path* for an isolated build."""
    src = pathlib.Path(_ROOT) / "out"
    dst = tmp_path / "out"
    shutil.copytree(src, dst)

def _load_metrics(path: pathlib.Path) -> dict:
    """Load a metrics.json file from *path*."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _extract_tiles(html: str) -> list[tuple[str, str, str]]:
    """Return a list of (label, value, note) tuples from the built KPI tiles."""
    pattern = re.compile(
        r'<div class="kpi"><div class="l">(.*?)</div>'
        r'<div class="n">(.*?)</div>'
        r'<div class="d">(.*?)</div></div>',
        flags=re.DOTALL,
    )
    return [(l.strip(), v.strip(), d.strip()) for l, v, d in pattern.findall(html)]

def _expected_tiles(metrics: dict) -> list[tuple[str, str, str]]:
    """Compute the expected 12 KPI tuples from *metrics* according to the spec."""
    m = metrics
    # Helper shortcuts
    a = m["active"]
    tx = m["txns"]
    fee = m["fee_usd"]
    vol = m["vol_usd"]
    sup = m["supply"]
    fees = m["fees"]
    apps = m["apps"]
    intents_daily = m["intents_daily"]
    holders = m["holders"]
    valuation = m["valuation"]
    cross = m["crosscheck"]
    # Formatted strings
    def fmt(v):
        return f"{v:,}"
    return [
        ("Active accounts, 30-day mean", f"{a['avg_30d']:,.0f}", f"{a['yoy_pct']:+.0f}% vs a year ago"),
        ("Transactions per day", f"{tx['avg_30d']:,.0f}", f"{tx['yoy_pct']:+.0f}%"),
        ("Fees per day, USD", f"${fee['avg_30d']:,.0f}", f"{fee['yoy_pct']:+.0f}%"),
        ("Transfer value per day, USD", f"${vol['avg_30d']/1e6:,.0f}M", f"{vol['yoy_pct']:+.0f}%"),
        ("Supply growth, 12 months", f"{sup['growth_pct']:.1f}%", f"≈ ${fees['issuance_usd_365d']/1e6:,.0f}M issued vs ${fees['fees_usd_365d']/1e6:,.1f}M fees"),
        ("Market cap ÷ annual gas fees", f"{fees['mcap_to_fees']:,.0f}×", ""),
        ("App fees, last 365 days", f"${apps['fees_usd_365d']/1e6:,.1f}M", f"{apps['x_gas_fees']:,.0f}× the chain's gas fees"),
        ("NEAR Intents share of app fees", f"{apps['intents_share_30d']*100:.0f}%", "last 30 days"),
        ("NEAR's Intents revenue, a year at today's pace", f"${intents_daily['revenue_annualised']/1e6:,.1f}M", f"{intents_daily['revenue_yoy_pct']:+.0f}% vs a year ago"),
        ("Buybacks cover of new issuance", f"{holders['cover_of_issuance_pct']:.0f}%", f"since {holders['first_day']}"),
        ("Market cap ÷ Intents revenue", f"{valuation['mcap_to_intents_revenue_annualised']:,.0f}×", f"{valuation['mcap_to_app_fees']:,.0f}× app fees"),
        ("Gas fees, two providers", f"{cross['gas_fees_abs_diff_pct']:.2f}% apart", "NearBlocks vs DefiLlama, 365 days"),
    ]

def test_tile_exact_value(tmp_path: pathlib.Path):
    """dashboard.py: verify that the page contains exactly the expected KPI tiles."""
    import dashboard
    _copy_out(tmp_path)
    cwd = tmp_path
    # Ensure build runs in the temporary copy
    cwd_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        dashboard.build()
    finally:
        os.chdir(cwd_cwd)
    html_path = cwd / "out" / "index.html"
    assert html_path.is_file(), "dashboard.py: index.html was not created"
    html = html_path.read_text(encoding="utf-8")
    tiles = _extract_tiles(html)
    assert len(tiles) == 12, f"dashboard.py: expected 12 KPI tiles, found {len(tiles)}"
    real_metrics = _load_metrics(pathlib.Path(_ROOT) / "out" / "metrics.json")
    expected = _expected_tiles(real_metrics)
    assert tiles == expected, f"dashboard.py: KPI tiles differ from expected values"

def test_tile_control_catches_wrong_value(tmp_path: pathlib.Path):
    """dashboard.py: ensure that altering a metric changes the corresponding tile and is detected."""
    import dashboard
    # Copy real out folder
    src_out = pathlib.Path(_ROOT) / "out"
    dst_out = tmp_path / "out"
    shutil.copytree(src_out, dst_out)
    # Load and tamper metrics
    metrics_path = dst_out / "metrics.json"
    metrics = _load_metrics(metrics_path)
    # Replace cover_of_issuance_pct with gas_cover_of_issuance_pct (~1%)
    metrics["holders"]["cover_of_issuance_pct"] = metrics["holders"]["gas_cover_of_issuance_pct"]
    # Also replace intents_share_30d with apps.fees_yoy_pct (example mis‑match)
    metrics["apps"]["intents_share_30d"] = metrics["apps"]["fees_yoy_pct"]
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    # Build page from the tampered copy
    cwd = tmp_path
    cwd_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        dashboard.build()
    finally:
        os.chdir(cwd_cwd)
    html = (cwd / "out" / "index.html").read_text(encoding="utf-8")
    built_tiles = _extract_tiles(html)
    # Load the correct reference tiles
    real_tiles = _expected_tiles(_load_metrics(pathlib.Path(_ROOT) / "out" / "metrics.json"))
    # The mismatched tiles should be different
    assert built_tiles != real_tiles, "dashboard.py: modified metrics did not affect tiles as expected"
    # Specifically, the two target tiles must differ
    idx_cover = next(i for i, t in enumerate(real_tiles) if t[0] == "Buybacks cover of new issuance")
    idx_intents = next(i for i, t in enumerate(real_tiles) if t[0] == "NEAR Intents share of app fees")
    assert built_tiles[idx_cover][1] != real_tiles[idx_cover][1], "dashboard.py: cover_of_issuance_pct tile unchanged"
    assert built_tiles[idx_intents][1] != real_tiles[idx_intents][1], "dashboard.py: intents_share_30d tile unchanged"

def test_page_structure_and_content():
    """dashboard.py: verify overall HTML structure and required strings."""
    import dashboard
    # Build directly in the lane root (the test runs from the repo root)
    cwd_cwd = os.getcwd()
    try:
        dashboard.build()
    finally:
        os.chdir(cwd_cwd)
    html_path = pathlib.Path(_ROOT) / "out" / "index.html"
    assert html_path.is_file(), "dashboard.py: index.html missing after build"
    html = html_path.read_text(encoding="utf-8")
    # Figure count
    figures = len(re.findall(r"<figure>", html))
    assert figures == 13, f"dashboard.py: expected 13 <figure> elements, found {figures}"
    # KPI count
    kpis = len(re.findall(r'class="kpi"', html))
    assert kpis == 12, f"dashboard.py: expected 12 KPI tiles, found {kpis}"
    # Required substrings
    required = [
        "NEAR Intents share of app fees",
        "Market cap ÷ Intents revenue",
        "Fees users paid to apps on NEAR, per month, USD",
        "WEAKNESSES.md",
        "sha256sum -c --ignore-missing SHA256SUMS",
    ]
    for phrase in required:
        assert phrase in html, f"dashboard.py: missing required phrase '{phrase}'"
    # Footer panel size text
    from thesis_doc import load as td_load
    _, panel, _, _, _ = td_load()
    expected_footer = f"Built on 3Dogs wisdom of crowds, three reviewers for speed, five when one stands alone. This entry uses a {len(panel['judges'])}-judge panel."
    assert expected_footer in html, "dashboard.py: footer does not contain correct panel size"
    # Disallowed content
    disallowed = ["under 1% of issuance", "controlling", "<script"]
    for bad in disallowed:
        assert bad not in html, f"dashboard.py: disallowed content '{bad}' found"

def test_money_formatting():
    """dashboard.py: money() must format dollar amounts according to the spec."""
    import dashboard
    assert dashboard.money(59295359.42) == "$59.3 million", "dashboard.py: money formatting mismatch for 59M"
    assert dashboard.money(4694985121.06) == "$4.69 billion", "dashboard.py: money formatting mismatch for 4.69B"
    assert dashboard.money(1170.4) == "$1,170", "dashboard.py: money formatting mismatch for small amount"

# --------------------------------------------------------------------------- #
# Runner – executes every ``test_`` function, creates a temporary directory
# when a ``tmp_path`` argument is present, and finally prints exactly PASS.
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Iterate over globals to find test functions
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            sig = inspect.signature(func)
            if "tmp_path" in sig.parameters:
                with tempfile.TemporaryDirectory() as td:
                    tmp = pathlib.Path(td)
                    func(tmp_path=tmp)
            else:
                func()
    # All assertions passed
    print("PASS")
