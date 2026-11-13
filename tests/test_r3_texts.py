import sys, os
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

import thesis_doc


def test_volume_paradox_text():
    m, p, f, t, man = thesis_doc.load()
    text = thesis_doc.thesis(m, p, f, t)

    # Paragraph 1
    para1 = (
        f"What we can and cannot say: this data cannot name the cause. The numbers are consistent with "
        f"fewer small, everyday transactions and a larger average transfer: NEAR moved per transaction rose "
        f"{m['paradox']['near_per_txn_x']:.1f}x (`paradox.near_per_txn_x`). No transaction-size distribution is "
        f"measured here, so we do not know which kinds of transactions stopped, or whether larger transfers "
        f"took their place."
    )
    # Paragraph 2
    para2 = (
        "So the paradox is not a contradiction. The data shows fewer transactions and more NEAR moved per "
        "transaction. That is consistent with a chain that lost many small transactions and kept larger "
        "ones, but it does not prove it."
    )

    assert para1 in text, "THESIS.md: missing first volume paradox paragraph"
    assert para2 in text, "THESIS.md: missing second volume paradox paragraph"

    # Forbidden strings
    forbidden = [
        "the pattern is clear",
        "are gone",
        "kept its large ones",
        "exchanges, bridge operators",
    ]
    for s in forbidden:
        assert s not in text, f"THESIS.md: contains forbidden string '{s}'"


def test_counterfactual_text():
    m, p, f, t, man = thesis_doc.load()
    text = thesis_doc.tripwires(m, p, f, t, man)

    # Counterfactual 1 paragraph
    cf1 = (
        f"**1. If NEAR moved per transaction had not changed, NEAR-denominated transfer volume would have fallen about as far as transactions did.** "
        f"NEAR moved per transaction is {m['paradox']['near_per_txn_x']:.1f} times what it was a year ago (`paradox.near_per_txn_x`), "
        f"so NEAR volume is {m['paradox']['near_volume_x']:.2f} times last year's (`paradox.near_volume_x`) although transactions are {m['paradox']['txns_x']:.2f} "
        f"times last year's (`paradox.txns_x`). At last year's NEAR per transaction, volume would be about {m['paradox']['txns_x']:.2f} times last year's, "
        f"a fall of {(1 - m['paradox']['txns_x']) * 100:.0f}%."
        f" The pieces are in the table in THESIS.md, section \"The volume paradox, explained\"."
    )

    assert cf1 in text, "TRIPWIRES.md: missing or malformed counterfactual 1 paragraph"

    # Ensure no prohibited strings appear
    prohibited = ["6.3x", "paradox table above", "three quarters"]
    for s in prohibited:
        assert s not in text, f"TRIPWIRES.md: contains prohibited string '{s}'"


def test_f3_statement_and_w9_source():
    m, p, f, t, man = thesis_doc.load()
    # Check F3 forecast
    f3 = None
    for item in f.get("forecasts", []):
        if item.get("id") == "F3":
            f3 = item
            break
    assert f3 is not None, "TRIPWIRES.md: F3 forecast not found"
    stmt = f3.get("statement", "")
    assert "about 73%" in stmt, "TRIPWIRES.md: F3 statement missing 'about 73%'"
    assert "three quarters" not in stmt, "TRIPWIRES.md: F3 statement incorrectly contains 'three quarters'"
    assert f3.get("threshold") == 45000, "TRIPWIRES.md: F3 threshold is not 45000"
    assert f3.get("path") == "intents_daily.revenue_avg_30d", "TRIPWIRES.md: F3 path is incorrect"

    # Check W9 source line in weaknesses
    weaknesses_text = thesis_doc.weaknesses(m, p, f, t, man)
    # Find the W9 section (heading "## W9") and its "Source: " line
    sec = weaknesses_text.split("## W9", 1)[1].split("\n## ", 1)[0] if "## W9" in weaknesses_text else ""
    lines = [ln for ln in sec.splitlines() if ln.startswith("Source: ")]
    w9_line = lines[0] if lines else None
    assert w9_line is not None, "WEAKNESSES.md: W9 source line not found"
    expected_url = thesis_doc.src(man, "charts_raw.json")
    assert w9_line == f"Source: {expected_url}", "WEAKNESSES.md: W9 source line incorrect"
    # Ensure it does not contain forbidden substrings
    for bad in ["give", "scored by"]:
        assert bad not in w9_line.lower(), f"WEAKNESSES.md: W9 source line contains forbidden word '{bad}'"


if __name__ == "__main__":
    test_volume_paradox_text()
    test_counterfactual_text()
    test_f3_statement_and_w9_source()
    print("PASS")
