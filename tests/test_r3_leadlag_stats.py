"""The README lead-lag table must equal the values rebuilt in metrics.json (r, n, 95% interval, p)."""
import json, os, pathlib, re
import pytest
_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_readme_leadlag_table_matches_metrics():
    m = json.load(open(os.path.join(_R, "out", "metrics.json")))["leadlag"]
    rows = re.findall(r"^\| (Intents fees|Price) \| (\d+) \| ([+-]\d\.\d\d) \| (\d+) \| ([+-]\d\.\d\d) to ([+-]\d\.\d\d) \| (\d\.\d\d) \|$", open(os.path.join(_R, "README.md")).read(), re.M)
    assert len(rows) == 8, rows
    for who, lag, r, n, lo, hi, p in rows:
        pre = "intents_fees_to_active" if who == "Intents fees" else "price_to_active"
        k = "lag%sw" % lag
        assert f"{m[pre + '_corr_' + k]:+.2f}" == r
        assert m[pre + "_n_" + k] == int(n)
        assert f"{m[pre + '_ci_low_' + k]:+.2f}" == lo and f"{m[pre + '_ci_high_' + k]:+.2f}" == hi
        assert f"{m[pre + '_p_' + k]:.2f}" == p

def test_leadlag_stats_are_in_metrics():
    m = json.load(open(os.path.join(_R, "out", "metrics.json")))["leadlag"]
    for pre in ("intents_fees_to_active", "price_to_active"):
        for lag in ("lag0w", "lag4w", "lag8w", "lag12w"):
            lo, hi = m[f"{pre}_ci_low_{lag}"], m[f"{pre}_ci_high_{lag}"]
            assert lo < hi and lo <= m[f"{pre}_corr_{lag}"] <= hi
            assert 0 <= m[f"{pre}_p_{lag}"] <= 1 and m[f"{pre}_n_{lag}"] > 3


def test_other_windows_are_disclosed_and_tied_to_metrics():
    import json, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    m = json.load(open(root / "out" / "metrics.json"))
    w = m["windows"]
    for k in ("active_accounts_30d_mean_vs_365d_ago_pct", "app_fees_last_30d_vs_prior_30d_pct",
              "app_fees_last_365d_vs_prior_365d_pct", "step_transactions_change_pct"):
        assert k in w
    thesis = (root / "THESIS.md").read_text()
    assert format(w["app_fees_last_30d_vs_prior_30d_pct"], "+.1f") + "%" in thesis
    assert "is unknown" in thesis and "shows scale only" in thesis
    page = (root / "out" / "index.html").read_text()
    assert "Other windows, and what we do not know" in page and "its cause is unknown" in page


@pytest.mark.skipif(not (pathlib.Path(__file__).resolve().parent.parent / "data" / "nearblocks_daily.csv").exists(), reason="needs the source files (python3 fetch.py)")
def test_window_values_match_an_independent_recompute_from_the_csv():
    import csv, json, pathlib, datetime as dt
    root = pathlib.Path(__file__).resolve().parent.parent
    m = json.load(open(root / "out" / "metrics.json"))
    end = dt.date.fromisoformat(m["as_of"])
    by = {r["date"][:10]: r for r in csv.DictReader(open(root / "data" / "nearblocks_daily.csv"))}

    def mean30(col, last):
        v = [float(by[(last - dt.timedelta(days=i)).isoformat()][col]) for i in range(30)]
        return sum(v) / 30

    for col, name in (("active_accounts", "active_accounts"), ("txns", "transactions")):
        for d in (30, 90, 180, 365, 730):
            want = (mean30(col, end) / mean30(col, end - dt.timedelta(days=d)) - 1) * 100
            assert abs(m["windows"][f"{name}_30d_mean_vs_{d}d_ago_pct"] - want) < 1e-6, (col, d)
    step = dt.date.fromisoformat(m["crosscheck"]["bq_txns_largest_drop_date"])
    b = [float(by[(step - dt.timedelta(days=i)).isoformat()]["txns"]) for i in range(1, 15)]
    a = [float(by[(step + dt.timedelta(days=i)).isoformat()]["txns"]) for i in range(0, 14)]
    want = (sum(a) / 14 / (sum(b) / 14) - 1) * 100
    assert abs(m["windows"]["step_transactions_change_pct"] - want) < 1e-6
    assert m["windows"]["app_fees_last_30d_vs_prior_30d_pct"] < 0 < m["windows"]["app_fees_last_365d_vs_prior_365d_pct"]
