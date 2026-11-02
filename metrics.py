"""Compute every number in the thesis from data/charts_raw.json (NearBlocks /v1/charts).
Each metric records the exact computation so anyone can re-run it."""
import json, os, statistics as st, datetime as dt

Y = 10**24  # yoctoNEAR per NEAR

def load(path="data/charts_raw.json"):
    rows = json.load(open(path))["charts"]
    out = []
    for r in rows:
        d = r["date"][:10]
        out.append({
            "date": d,
            "price": float(r["near_price"] or 0),
            "mcap": float(r["market_cap"] or 0),
            "supply": float(r["total_supply"] or 0) / Y,
            "txns": float(r["txns"] or 0),
            "active": float(r["active_accounts"] or 0),
            "new_acc": float(r["new_accounts"] or 0),
            "fee_usd": float(r["txn_fee_usd"] or 0),
            "vol_usd": float(r["txn_volume_usd"] or 0),
            "active_contracts": float(r["active_contracts"] or 0),
            "new_contracts": float(r["new_contracts"] or 0),
        })
    return out

def complete(rows):
    """Drop the last row (today, partial)."""
    return rows[:-1]

def window(rows, end, days):
    e = dt.date.fromisoformat(end)
    s = e - dt.timedelta(days=days - 1)
    return [r for r in rows if s <= dt.date.fromisoformat(r["date"]) <= e]

def mean(rows, k):
    v = [r[k] for r in rows]
    return st.mean(v) if v else float("nan")

def pct(a, b):
    return (a / b - 1) * 100 if b else float("nan")

def corr(x, y):
    mx, my = st.mean(x), st.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** 0.5
    return num / den if den else float("nan")

def monthly(rows, k, agg="mean"):
    by = {}
    for r in rows:
        by.setdefault(r["date"][:7], []).append(r[k])
    return {m: (st.mean(v) if agg == "mean" else sum(v)) for m, v in sorted(by.items())}

def compute(path="data/charts_raw.json"):
    rows = complete(load(path))
    last = rows[-1]["date"]
    e = dt.date.fromisoformat(last)
    yago = (e - dt.timedelta(days=365)).isoformat()
    m = {"as_of": last, "source": "https://api.nearblocks.io/v1/charts", "n_days": len(rows)}
    W = 30
    cur, prev = window(rows, last, W), window(rows, yago, W)
    for k, name in [("active", "daily active accounts"), ("txns", "daily transactions"),
                    ("fee_usd", "daily fees (USD)"), ("new_acc", "daily new accounts"),
                    ("vol_usd", "daily transfer volume (USD)"), ("active_contracts", "daily active contracts"),
                    ("price", "NEAR price (USD)")]:
        m[k] = {"label": name, "avg_30d": mean(cur, k), "avg_30d_year_ago": mean(prev, k),
                "yoy_pct": pct(mean(cur, k), mean(prev, k)),
                "calc": f"mean of {k} over the 30 days ending {last} vs the 30 days ending {yago}"}
    # 90-day windows (less noise than 30 days)
    c90, p90 = window(rows, last, 90), window(rows, yago, 90)
    m["w90"] = {k: {"avg_90d": mean(c90, k), "avg_90d_year_ago": mean(p90, k), "yoy_pct": pct(mean(c90, k), mean(p90, k))}
                for k in ("active", "txns", "fee_usd", "vol_usd", "new_acc", "price")}
    m["w90"]["calc"] = f"90-day means ending {last} vs ending {yago}"
    # transfer volume in NEAR terms (removes the effect of the price rise)
    vn = lambda rs: st.mean([r["vol_usd"] / r["price"] for r in rs if r["price"] > 0])
    m["vol_near"] = {"avg_30d": vn(cur), "avg_30d_year_ago": vn(prev), "yoy_pct": pct(vn(cur), vn(prev)),
                     "calc": "30-day mean of daily txn_volume_usd / near_price, i.e. transfer volume counted in NEAR"}
    # peak activity
    pk = max(rows, key=lambda r: r["active"])
    m["active_peak"] = {"date": pk["date"], "value": pk["active"],
                        "current_vs_peak_pct": pct(m["active"]["avg_30d"], pk["active"]),
                        "calc": "max single-day active_accounts in the full history vs current 30-day mean"}
    # supply inflation
    s_now, s_then = rows[-1]["supply"], next(r["supply"] for r in rows if r["date"] >= yago)
    m["supply"] = {"total_now": s_now, "total_year_ago": s_then, "growth_pct": pct(s_now, s_then),
                   "calc": f"total_supply on {last} vs {yago} (NEAR = yocto/1e24)"}
    # annualised fees vs market cap
    fees_365 = sum(r["fee_usd"] for r in window(rows, last, 365))
    m["fees"] = {"fees_usd_365d": fees_365, "mcap_now": rows[-1]["mcap"],
                 "mcap_to_fees": rows[-1]["mcap"] / fees_365 if fees_365 else None,
                 "issuance_usd_365d": (s_now - s_then) * rows[-1]["price"],
                 "calc": "sum txn_fee_usd over last 365 days; issuance = supply growth x current price"}
    # fees per active account
    m["fee_per_active"] = {"now": m["fee_usd"]["avg_30d"] / m["active"]["avg_30d"],
                           "year_ago": m["fee_usd"]["avg_30d_year_ago"] / m["active"]["avg_30d_year_ago"],
                           "calc": "30-day mean fee_usd / 30-day mean active accounts"}
    # does activity lead price? correlation of 30d change in active vs next-90d price change, monthly points
    mon_a, mon_p = monthly(rows, "active"), monthly(rows, "price")
    ks = [k for k in mon_a if k >= "2022-01"]
    xs, ys = [], []
    for i in range(1, len(ks) - 3):
        xs.append(pct(mon_a[ks[i]], mon_a[ks[i - 1]]))
        ys.append(pct(mon_p[ks[i + 3]], mon_p[ks[i]]))
    m["lead"] = {"corr_active_change_vs_next_3m_price": corr(xs, ys), "n_months": len(xs),
                 "calc": "Pearson r between monthly % change in mean active accounts and the % change in mean price over the following 3 months, Jan 2022 on"}
    xs2 = [mon_a[k] for k in ks]; ys2 = [mon_p[k] for k in ks]
    m["level_corr"] = {"corr_active_vs_price_monthly": corr(xs2, ys2), "n_months": len(ks),
                       "calc": "Pearson r of monthly mean active accounts vs monthly mean price, Jan 2022 on"}
    # NEAR Intents 1Click swaps (weekly Sunday samples, if fetched)
    ip = os.path.join(os.path.dirname(path), "intents_days.json")
    if os.path.exists(ip):
        days = json.load(open(ip))
        if len(days) >= 8:
            first, last4 = days[:4], days[-4:]
            mu = lambda xs, k: st.mean(d[k] for d in xs)
            m["intents"] = {"n_sampled_days": len(days), "first_day": days[0]["date"], "last_day": days[-1]["date"],
                            "swaps_first4": mu(first, "swaps"), "swaps_last4": mu(last4, "swaps"),
                            "usd_first4": mu(first, "usd"), "usd_last4": mu(last4, "usd"),
                            "swaps_change_pct": pct(mu(last4, "swaps"), mu(first, "swaps")),
                            "usd_change_pct": pct(mu(last4, "usd"), mu(first, "usd")),
                            "usd_per_swap_last4": mu(last4, "usd") / mu(last4, "swaps"),
                            "annualised_usd_last4": mu(last4, "usd") * 365,
                            "calc": "successful 1Click swaps on one full UTC Sunday per week (Explorer API); mean of the first 4 sampled Sundays vs the last 4"}
            m["intents_weekly"] = {d["date"]: {"swaps": d["swaps"], "usd": d["usd"]} for d in days}
    m["monthly"] = {k: {"active": mon_a[k], "price": mon_p[k],
                        "txns": monthly(rows, "txns")[k], "fee_usd": monthly(rows, "fee_usd", "sum")[k],
                        "new_acc": monthly(rows, "new_acc")[k]} for k in mon_a}
    return m

if __name__ == "__main__":
    import sys
    m = compute(sys.argv[1] if len(sys.argv) > 1 else "data/charts_raw.json")
    json.dump(m, open("out/metrics.json", "w"), indent=1)
    s = {k: v for k, v in m.items() if k != "monthly"}
    print(json.dumps(s, indent=1, default=str))
