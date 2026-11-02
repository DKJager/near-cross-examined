import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import metrics, panel

def fake(path):
    rows = []
    import datetime as dt
    d0 = dt.date(2024, 1, 1)
    for i in range(800):
        d = d0 + dt.timedelta(days=i)
        rows.append({"date": d.isoformat() + "T00:00:00.000Z", "near_price": str(2 + i / 400), "market_cap": "1000000",
                     "total_supply": str(int((1e9 + i * 1e5) * 1e24)), "txns": str(1000 - i), "active_accounts": str(2000 - 2 * i),
                     "new_accounts": "10", "txn_fee_usd": "5", "txn_volume_usd": str(100 + i), "active_contracts": "7", "new_contracts": "1"})
    json.dump({"charts": rows}, open(path, "w"))

def test_compute(tmp_path):
    p = tmp_path / "c.json"; fake(p)
    m = metrics.compute(str(p))
    assert m["n_days"] == 799                      # partial last day dropped
    assert m["active"]["yoy_pct"] < 0               # active falls in the fake series
    assert m["vol_usd"]["yoy_pct"] > 0
    assert abs(m["fees"]["fees_usd_365d"] - 5 * 365) < 1e-6
    assert m["supply"]["growth_pct"] > 0

def test_resolve_rejects_invented_paths(tmp_path):
    p = tmp_path / "c.json"; fake(p)
    m = metrics.compute(str(p)); nums = panel.flat(m)
    assert panel.resolve("active.yoy_pct", m, nums) == m["active"]["yoy_pct"]
    assert panel.resolve("active.made_up", m, nums) is None
    month = sorted(m["monthly"])[0]
    assert panel.resolve(f"monthly.{month}.active", m, nums) == m["monthly"][month]["active"]

def test_parse():
    assert panel.parse('blah {"claims":[{"id":"C1","verdict":"SUPPORTED"}],"thesis":"x"} tail')["claims"][0]["id"] == "C1"
    assert panel.parse("no json") is None
