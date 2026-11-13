import sys, os, json, pathlib, re

# Add lane root and optional src directory to import path
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

# ---------------------------------------------------------------------------
# Test suite for README.md
# ---------------------------------------------------------------------------

def _read_root_file(rel_path: str) -> str:
    """Read a file relative to the repository root and return its text."""
    path = pathlib.Path(_R, rel_path)
    return path.read_text(encoding="utf-8")

def _load_panel():
    """Load out/panel.json and return parsed dict."""
    return json.loads(_read_root_file("out/panel.json"))

def _extract_between_markers(text: str, begin: str, end: str) -> str:
    """Return the substring between the first occurrence of *begin* and *end*."""
    parts = text.split(begin, 1)
    assert len(parts) == 2, f"README.md: missing BEGIN marker {begin!r}"
    after = parts[1]
    parts = after.split(end, 1)
    assert len(parts) == 2, f"README.md: missing END marker {end!r}"
    return parts[0].strip("\n")

def test_readme_model_table():
    """Verify the model table block in README.md."""
    readme = _read_root_file("README.md")
    # Exactly one BEGIN and END marker
    assert readme.count("<!-- MODELS:BEGIN -->") == 1, "README.md: should have exactly one MODELS:BEGIN"
    assert readme.count("<!-- MODELS:END -->") == 1, "README.md: should have exactly one MODELS:END"
    # Load panel and compute expected table
    panel = _load_panel()
    import thesis_doc
    expected_table = thesis_doc.models_table(panel)
    # Extract actual block
    block = _extract_between_markers(readme, "<!-- MODELS:BEGIN -->", "<!-- MODELS:END -->")
    # The block must exactly equal the generated table
    assert block == expected_table, "README.md: model table does not match generated table"
    # readme_synced must be a no‑op when applied to the current text
    synced = thesis_doc.readme_synced(readme, panel)
    assert synced == readme, "README.md: readme_synced altered already‑synced README"
    # Ensure every model name appears before the first '('
    names = [j.split(" (")[0] for j in panel["judges"]]
    for name in names:
        assert name in readme, f"README.md: model name {name!r} missing from README"

    # Sample dictionary test (explicit example from spec)
    sample_panel = {"judges": ["alpha-1 (Maker One, open-weight)", "beta-2 (Maker Two)"]}
    sample_expected = "| Judge model | Maker |\n|---|---|\n| alpha-1 | Maker One |\n| beta-2 | Maker Two |"
    assert thesis_doc.models_table(sample_panel) == sample_expected, "README.md: sample models_table output mismatch"

def test_readme_structure():
    """Check heading order, Install block, Disclosures and forbidden strings."""
    readme = _read_root_file("README.md")
    # Expected headings in order (including the leading H1)
    expected_headings = [
        "# NEAR, Cross-Examined",
        "## The thesis in one line",
        "## Install",
        "## Do X, see Y",
        "## Use it on your own claim",
        "## What it does",
        "## Data sources",
        "## Weak points",
        "## Model retirement, 9 Nov 2026",
        "## Files",
        "## Disclosures",
        "## License",
    ]
    # Extract all lines that start with '#'
    actual_headings = [line.rstrip() for line in readme.splitlines() if line.lstrip().startswith('#')]
    # Verify subsequence order
    idx = 0
    for exp in expected_headings:
        while idx < len(actual_headings) and actual_headings[idx] != exp:
            idx += 1
        assert idx < len(actual_headings), f"README.md: heading {exp!r} not found in order"
        idx += 1

    # Verify Install section contains exactly one fenced block with four lines
    install_match = re.search(r"## Install\s+```sh\s+(.*?)```", readme, re.DOTALL)
    assert install_match, "README.md: Install section missing fenced block"
    block_lines = [ln for ln in install_match.group(1).splitlines() if ln.strip()]
    expected_block = [
        "python3 -m venv .venv",
        ". .venv/bin/activate",
        "pip install pytest",
        "make verify",
    ]
    assert block_lines == expected_block, "README.md: Install fenced block does not contain the four expected lines"

    # Verify Disclosures section contains required bullets (order not critical)
    disclosures_section = re.search(r"## Disclosures\s+(.*?)(?:\n## |\Z)", readme, re.DOTALL)
    assert disclosures_section, "README.md: Disclosures section missing"
    disclosures_text = disclosures_section.group(1)
    required_phrases = [
        "AI tools:",
        "Claude (Anthropic)",
        "DeepSeek (a Flash model)",
        "gpt-oss-120b",
        "Alan Finney",
        "The judge panel is four AI models",
        "Libraries:",
        "Hosted page:",
        "2026-11-02",
    ]
    for phrase in required_phrases:
        assert phrase in disclosures_text, f"README.md: Disclosures missing required phrase {phrase!r}"

    # Forbidden strings must not appear in the public README
    forbidden = ["openrouter", "XXL", "6 of 6"]
    for forb in forbidden:
        assert forb not in readme, f"README.md: contains forbidden string {forb!r}"

def test_readme_five_minute_path():
    """Validate the “Judge's 5‑minute path” box and its numbered list."""
    readme = _read_root_file("README.md")
    # The box must appear directly after the title line
    title_index = readme.find("# NEAR, Cross-Examined")
    assert title_index != -1, "README.md: title line missing"
    after_title = readme[title_index + len("# NEAR, Cross-Examined"):]

    # Look for the bolded box marker
    box_marker = "**Judge's 5-minute path**"
    assert box_marker in after_title, "README.md: missing 5‑minute path box marker"

    # Extract the numbered list (lines beginning with digits and a period)
    list_pattern = r"1\. `pip install pytest && make verify`.*?2\. Open `docs/index.html`.*?3\. Read the section \"The track's question\" in `THESIS\.md`.*?4\. `python3 bq_fetch\.py` prints the three SQL queries"
    assert re.search(list_pattern, readme, re.DOTALL), "README.md: 5‑minute path numbered list does not match expected content"

    # Ensure the list items are in the exact order and wording
    expected_items = [
        "1. `pip install pytest && make verify` (in a virtual environment, see Install): prints the VERIFY OK and DOCS OK lines.",
        "2. Open `docs/index.html` (or the hosted page, see Disclosures): the thesis, three numbers, 13 charts, each with its method.",
        "3. Read the section \"The track's question\" in `THESIS.md`.",
        "4. `python3 bq_fetch.py` prints the three SQL queries for the NEAR BigQuery public dataset; their results, run once on 13 Nov 2026, are in `data/bq_*.csv`.",
    ]
    for item in expected_items:
        assert item in readme, f"README.md: missing or incorrect 5‑minute path item: {item!r}"

    # The README must not mention a demo video file
    assert "demo.mp4" not in readme, "README.md: unexpected reference to demo.mp4"

# ---------------------------------------------------------------------------
# Runner – executes all test functions and prints PASS on success.
# ---------------------------------------------------------------------------

def _run_all():
    """Execute every test_* function defined in this module."""
    tests = [obj for name, obj in globals().items()
             if callable(obj) and name.startswith("test_")]
    for fn in tests:
        fn()

if __name__ == "__main__":
    _run_all()
    print("PASS")
