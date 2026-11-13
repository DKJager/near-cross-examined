"""Compute every metric from data/charts_raw.json (and other raw files when present)."""

import json
import math
import datetime as dt
import statistics as st
import csv
import os
from typing import Optional

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
    if len(x) == 0 or len(y) == 0:
        return float("nan")
    mx, my = st.mean(x), st.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = (sum((a - mx)**2 for a in x) * sum((b - my)**2 for b in y))**0.5
    return num / den if den else float("nan")

def monthly(rows, k, agg="mean"):
    by = {}
    for r in rows:
        by.setdefault(r["date"][:7], []).append(r[k])
    return {m: (st.mean(v) if agg == "mean" else sum(v)) for m, v in sorted(by.items())}

def _day(ts):
    ts = int(ts)
    if ts > 10**11:
        ts //= 1000
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()

def series(path, key="totalDataChart"):
    """{date: value} from a DefiLlama chart ([[unix time, value], ...])."""
    d = json.load(open(path))
    ch = d[key] if isinstance(d, dict) else d
    return {_day(ts): float(v) for ts, v in ch if v is not None}

def swin(s, end, days):
    e = dt.date.fromisoformat(end)
    return [s[(e - dt.timedelta(days=i)).isoformat()] for i in range(days) if (e - dt.timedelta(days=i)).isoformat() in s]

def smean(s, end, days=30):
    v = swin(s, end, days)
    return st.mean(v) if v else float("nan")

def ssum(s, end, days=365):
    return sum(swin(s, end, days))

def weekly(s: dict, end: str, weeks: int) -> list:
    """Return *weeks* consecutive 7-day block means (oldest first) ending at *end* from daily dict *s*.

    *s* maps date string -> value.  A block with no days present becomes None.
    """
    e = dt.date.fromisoformat(end)
    if weeks == 0:
        return []
    result = []
    for k in reversed(range(weeks)):
        start_day = e - dt.timedelta(days=7*k + 6)
        end_day = e - dt.timedelta(days=7*k)
        week_values = []
        current = start_day
        while current <= end_day:
            day_key = current.isoformat()
            if day_key in s:
                week_values.append(s[day_key])
            current += dt.timedelta(days=1)
        if not week_values:
            result.append(None)
        else:
            result.append(st.mean(week_values))
    return result

def pct_changes(vals: list) -> list:
    """Return [None if a or b is None or a == 0 else b/a - 1 for each consecutive pair (a, b)]."""
    changes = []
    for i in range(1, len(vals)):
        a, b = vals[i-1], vals[i]
        if a is None or b is None or a == 0:
            changes.append(None)
        else:
            changes.append(b / a - 1)
    return changes

def lagged_corr(x: list, y: list, lag: int) -> float:
    """Pearson correlation between x[i] and y[i+lag] over indices where both are not None.
    Returns NaN when fewer than 20 pairs."""
    pairs = []
    for i in range(len(x) - lag):
        if x[i] is not None and y[i+lag] is not None:
            pairs.append((x[i], y[i+lag]))
    if len(pairs) < 20:
        return float("nan")
    xs, ys = zip(*pairs) if pairs else ([], [])
    if len(xs) < 2 or len(ys) < 2:
        return float("nan")
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx)**2 for a in xs) * sum((b - my)**2 for b in ys))**0.5
    return num / den if den else float("nan")

def lagged_n(x: list, y: list, lag: int) -> int:
    """Count of valid pairs between x[i] and y[i+lag] over indices where both are not None."""
    n = 0
    for i in range(len(x) - lag):
        if x[i] is not None and y[i+lag] is not None:
            n += 1
    return n


def fisher_stats(r: float, n: int):
    """Calculate Fisher z transform confidence interval and p-value.
    Returns (ci_low, ci_high, p_value) or None if n <= 3 or r is NaN."""
    if math.isnan(r) or n <= 3:
        return None
    
    # Fisher z transform
    z = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    
    # 95% confidence interval
    z_low = z - 1.96 * se
    z_high = z + 1.96 * se
    ci_low = math.tanh(z_low)
    ci_high = math.tanh(z_high)
    
    # Two-sided p-value
    abs_z = abs(z)
    p_value = math.erfc(abs_z * math.sqrt(n - 3) / math.sqrt(2))
    
    return (ci_low, ci_high, p_value)


def swin_keys(end, days):
    e = dt.date.fromisoformat(end)
    return [(e - dt.timedelta(days=i)).isoformat() for i in range(days)]

def windows_section(m, rows, folder, last):
    """Other windows, so the headline 30-day year-on-year figures are not shown alone."""
    w = {}
    e = dt.date.fromisoformat(last)
    for k, name in [("active", "active_accounts"), ("txns", "transactions")]:
        now = mean(window(rows, last, 30), k)
        for d in (30, 90, 180, 365, 730):
            end = (e - dt.timedelta(days=d)).isoformat()
            w[f"{name}_30d_mean_vs_{d}d_ago_pct"] = pct(now, mean(window(rows, end, 30), k))
    fp = os.path.join(folder, "llama_fees_near.json")
    if os.path.exists(fp):
        tot = series(fp)
        for d in (30, 90, 365):
            end = (e - dt.timedelta(days=d)).isoformat()
            w[f"app_fees_last_{d}d_vs_prior_{d}d_pct"] = pct(sum(swin(tot, last, d)), sum(swin(tot, end, d)))
    m["windows"] = w
    # before / after the transaction step (date comes from the BigQuery cross-check when present)
    bq = m.get("crosscheck", {}) if isinstance(m.get("crosscheck"), dict) else {}
    step = bq.get("bq_txns_largest_drop_date")
    if step:
        sd = dt.date.fromisoformat(step)
        before = window(rows, (sd - dt.timedelta(days=1)).isoformat(), 14)
        after = window(rows, (sd + dt.timedelta(days=13)).isoformat(), 14)
        for k, name in [("new_acc", "new_accounts"), ("active_contracts", "active_contracts"),
                        ("txns", "transactions"), ("active", "active_accounts")]:
            w[f"step_{name}_14d_before"] = mean(before, k)
            w[f"step_{name}_14d_after"] = mean(after, k)
            w[f"step_{name}_change_pct"] = pct(mean(after, k), mean(before, k))

def second_source(m, rows, folder, last, yago):
    """Numbers from a second and third provider (DefiLlama, CoinGecko), if their files are in the data folder.
    Every window ends on the same day as the chain data (`last`), so the sources are compared like for like."""
    f = lambda name: os.path.join(folder, name)
    have = lambda name: os.path.exists(f(name))
    issuance = m["fees"]["issuance_usd_365d"]
    mcap = m["fees"]["mcap_now"]
    if have("llama_fees_near.json"):
        d = json.load(open(f("llama_fees_near.json")))
        tot = {_day(ts): float(v) for ts, v in d["totalDataChart"]}
        by = {_day(ts): v for ts, v in d.get("totalDataChartBreakdown", [])}
        def share(end, name="NEAR Intents"):
            e = dt.date.fromisoformat(end); num = den = 0.0
            for i in range(30):
                k = (e - dt.timedelta(days=i)).isoformat()
                if k in by:
                    num += float(by[k].get(name, 0) or 0); den += sum(float(x or 0) for x in by[k].values())
            return num / den if den else float("nan")
        def earners(end):
            e = dt.date.fromisoformat(end); t = {}
            for i in range(30):
                for n, v in by.get((e - dt.timedelta(days=i)).isoformat(), {}).items():
                    t[n] = t.get(n, 0) + float(v or 0)
            return sum(1 for v in t.values() if v >= 30 * 100)
        f365 = ssum(tot, last)
        m["apps"] = {"fees_avg_30d": smean(tot, last), "fees_avg_30d_year_ago": smean(tot, yago),
                     "fees_yoy_pct": pct(smean(tot, last), smean(tot, yago)), "fees_usd_365d": f365,
                     "intents_share_30d": share(last), "intents_share_30d_year_ago": share(yago),
                     "protocols_over_100_usd_a_day": earners(last),
                     "x_gas_fees": f365 / m["fees"]["fees_usd_365d"] if m["fees"]["fees_usd_365d"] else float("nan"),
                     "source": "https://api.llama.fi/overview/fees/near",
                     "calc": f"DefiLlama daily fees paid by users of apps on NEAR (the chain's own gas is not in this total); 30-day means ending {last} vs ending {yago}; 365-day sum; intents_share = NEAR Intents fees / all app fees over the same 30 days; protocols_over_100_usd_a_day = apps averaging at least $100 a day in fees over those 30 days; x_gas_fees = app fees / chain gas fees, both over 365 days"}
    if have("llama_intents_fees.json") and have("llama_intents_revenue.json"):
        fe, rv = series(f("llama_intents_fees.json")), series(f("llama_intents_revenue.json"))
        r30 = sum(swin(rv, last, 30)); f30 = sum(swin(fe, last, 30))
        m["intents_daily"] = {"first_day": min(fe), "fees_avg_30d": smean(fe, last), "fees_avg_30d_year_ago": smean(fe, yago),
                              "fees_yoy_pct": pct(smean(fe, last), smean(fe, yago)), "fees_usd_365d": ssum(fe, last),
                              "revenue_avg_30d": smean(rv, last), "revenue_avg_30d_year_ago": smean(rv, yago),
                              "revenue_yoy_pct": pct(smean(rv, last), smean(rv, yago)),
                              "revenue_usd_365d": ssum(rv, last), "revenue_annualised": r30 / 30 * 365,
                              "kept_share_30d": r30 / f30 if f30 else float("nan"),
                              "source": "https://api.llama.fi/summary/fees/near-intents",
                              "calc": f"DefiLlama, every day (not a sample): gross fees on NEAR Intents swaps, and the part NEAR keeps (revenue); 30-day means ending {last} vs ending {yago}; annualised = last 30 days x 365/30; kept_share = revenue / gross fees over 30 days"}
    if have("llama_holders_revenue_near.json"):
        h = series(f("llama_holders_revenue_near.json"))
        h = {k: v for k, v in h.items() if k <= last}
        ann = sum(swin(h, last, 30)) / 30 * 365
        m["holders"] = {"first_day": min(h), "days": len(h), "usd_since_first_day": sum(h.values()), "avg_30d": smean(h, last),
                        "annualised": ann, "cover_of_issuance_pct": ann / issuance * 100 if issuance else float("nan"),
                        "gas_cover_of_issuance_pct": m["fees"]["fees_usd_365d"] / issuance * 100 if issuance else float("nan"),
                        "mcap_to_annualised": mcap / ann if ann else float("nan"),
                        "x_to_cover_issuance": issuance / ann if ann else float("nan"),
                        "source": "https://api.llama.fi/overview/fees/near?dataType=dailyHoldersRevenue",
                        "calc": f"DefiLlama revenue returned to NEAR holders on NEAR (NEAR Intents revenue used to buy back NEAR since {min(h)}; the series starts that day); annualised = last 30 days x 365/30; cover = annualised / (supply growth over 365 days x current price); gas_cover = 365-day gas fees / the same issuance"}
    if "apps" in m:
        m["valuation"] = {"mcap_now": mcap, "mcap_to_gas_fees": m["fees"]["mcap_to_fees"],
                          "mcap_to_app_fees": mcap / m["apps"]["fees_usd_365d"] if m["apps"]["fees_usd_365d"] else float("nan"),
                          "calc": f"market cap on the last day / 365-day gas fees, and / 365-day app fees"}
        if "intents_daily" in m:
            m["valuation"]["mcap_to_intents_revenue_annualised"] = mcap / m["intents_daily"]["revenue_annualised"]
            m["valuation"]["calc"] += ", and / annualised NEAR Intents revenue"
    for name, key, fn, label in [("tvl", "llama_tvl_near.json", lambda p: {_day(x["date"]): float(x["tvl"]) for x in json.load(open(p))}, "total value locked on NEAR (USD)"),
                                 ("dex", "llama_dex_near.json", series, "daily exchange volume on NEAR (USD)"),
                                 ("stables", "llama_stablecoins_near.json", lambda p: {_day(x["date"]): float(x["totalCirculatingUSD"]["peggedUSD"]) for x in json.load(open(p))}, "stablecoin supply on NEAR (USD)")]:
        if have(key):
            s_ = fn(f(key))
            m[name] = {"label": label, "avg_30d": smean(s_, last), "avg_30d_year_ago": smean(s_, yago), "yoy_pct": pct(smean(s_, last), smean(s_, yago)),
                       "calc": f"DefiLlama; 30-day mean ending {last} vs ending {yago}"}
    mon2 = {}
    def add_monthly(name, s_, agg):
        by = {}
        for k, v in s_.items():
            if k <= last:
                by.setdefault(k[:7], []).append(v)
        for mth, v in by.items():
            mon2.setdefault(mth, {})[name] = sum(v) if agg == "sum" else st.mean(v)
    if have("llama_fees_near.json"):
        add_monthly("app_fees", series(f("llama_fees_near.json")), "sum")
    if have("llama_gas_fees_near.json"):
        add_monthly("gas_fees", series(f("llama_gas_fees_near.json")), "sum")
    if have("llama_intents_revenue.json"):
        add_monthly("intents_revenue", series(f("llama_intents_revenue.json")), "sum")
        add_monthly("intents_fees", series(f("llama_intents_fees.json")), "sum")
    if have("llama_stablecoins_near.json"):
        add_monthly("stables", {_day(x["date"]): float(x["totalCirculatingUSD"]["peggedUSD"]) for x in json.load(open(f("llama_stablecoins_near.json")))}, "mean")
    if have("llama_tvl_near.json"):
        add_monthly("tvl", {_day(x["date"]): float(x["tvl"]) for x in json.load(open(f("llama_tvl_near.json")))}, "mean")
    if mon2:
        m["monthly2"] = {k: mon2[k] for k in sorted(mon2)}
    cc = {}
    if have("llama_gas_fees_near.json"):
        g = series(f("llama_gas_fees_near.json"))
        nb = {r["date"]: r["fee_usd"] for r in rows}
        days = [k for k in swin_keys(last, 365) if k in g and k in nb]
        a, b = sum(nb[k] for k in days), sum(g[k] for k in days)
        cc.update({"gas_fees_365d_nearblocks": a, "gas_fees_365d_defillama": b, "gas_fees_diff_pct": pct(b, a),
                   "gas_fees_abs_diff_pct": abs(pct(b, a)), "gas_fee_days_compared": len(days)})
    if have("coingecko_near.json"):
        c = {_day(ts): float(v) for ts, v in json.load(open(f("coingecko_near.json")))["prices"]}
        nbp = {r["date"]: r["price"] for r in rows}
        days = [k for k in swin_keys(last, 30) if k in c and k in nbp]
        if days:
            a, b = st.mean(nbp[k] for k in days), st.mean(c[k] for k in days)
            cc.update({"price_30d_nearblocks": a, "price_30d_coingecko": b, "price_diff_pct": pct(b, a), "price_days_compared": len(days)})
    if cc:
        cc["calc"] = "the same days from two providers: gas fees summed over 365 days (NearBlocks txn_fee_usd vs DefiLlama, whose data comes from Allium), and the 30-day mean price (NearBlocks vs CoinGecko); diff = second source / NearBlocks - 1"
        m["crosscheck"] = cc
    return m

def compute(data_path: Optional[str] = None, as_of: Optional[str] = None) -> dict:
    """Every number. *as_of* (YYYY-MM-DD) ends all series on that day, so a later re-fetch can be rebuilt for the same dates."""
    path = data_path if data_path is not None else "data/charts_raw.json"
    rows = complete(load(path))
    if as_of:
        rows = [r for r in rows if r["date"] <= as_of]
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
    c90, p90 = window(rows, last, 90), window(rows, yago, 90)
    m["w90"] = {k: {"avg_90d": mean(c90, k), "avg_90d_year_ago": mean(p90, k), "yoy_pct": pct(mean(c90, k), mean(p90, k))}
                for k in ("active", "txns", "fee_usd", "vol_usd", "new_acc", "price")}
    m["w90"]["calc"] = f"90-day means ending {last} vs ending {yago}"
    vn = lambda rs: st.mean([r["vol_usd"] / r["price"] for r in rs if r["price"] > 0])
    m["vol_near"] = {"avg_30d": vn(cur), "avg_30d_year_ago": vn(prev), "yoy_pct": pct(vn(cur), vn(prev)),
                     "calc": "30-day mean of daily txn_volume_usd / near_price, i.e. transfer volume counted in NEAR"}
    usd_x = mean(cur, "vol_usd") / mean(prev, "vol_usd")
    price_x = mean(cur, "price") / mean(prev, "price")
    near_x = vn(cur) / vn(prev)
    txn_x = mean(cur, "txns") / mean(prev, "txns")
    npt = lambda rs: st.mean([r["vol_usd"] / r["price"] / r["txns"] for r in rs if r["price"] > 0 and r["txns"] > 0])
    m["paradox"] = {"usd_volume_x": usd_x, "price_x": price_x, "near_volume_x": near_x, "txns_x": txn_x,
                    "near_per_txn_now": npt(cur), "near_per_txn_year_ago": npt(prev), "near_per_txn_x": npt(cur) / npt(prev),
                    "share_of_usd_growth_from_price": math.log(price_x) / math.log(usd_x) if usd_x > 0 and usd_x != 1 and price_x > 0 else float("nan"),
                    "share_of_usd_growth_from_near_moved": math.log(near_x) / math.log(usd_x) if usd_x > 0 and usd_x != 1 and near_x > 0 else float("nan"),
                    "calc": "ratios of 30-day means, now vs a year earlier; near_per_txn = daily (txn_volume_usd / near_price) / txns; shares are log(ratio) / log(usd ratio), and the two do not sum to exactly 1 because a mean of ratios is not a ratio of means"}
    mt = monthly(rows, "txns"); mk = [k for k in sorted(mt) if k < last[:7]]
    drops = [(pct(mt[mk[i]], mt[mk[i - 1]]), mk[i]) for i in range(1, len(mk)) if mk[i] >= "2025-01"]
    if drops:
        d, when = min(drops)
        before = mk[mk.index(when) - 1]
        ma = monthly(rows, "active")
        m["txn_step"] = {"month": when, "change_pct": d, "txns_month_before": mt[before], "txns_month": mt[when],
                         "active_change_pct_same_month": pct(ma[when], ma[before]),
                         "share_of_12m_txn_fall": (mt[before] - mt[when]) / (mean(prev, "txns") - mean(cur, "txns")) if mean(prev, "txns") != mean(cur, "txns") else float("nan"),
                         "calc": "largest month-over-month % fall in monthly mean daily transactions since Jan 2025 (complete months only); active change is for the same pair of months; share = that one-month fall / the whole year-over-year fall in the 30-day mean"}
    pk = max(rows, key=lambda r: r["active"])
    m["active_peak"] = {"date": pk["date"], "value": pk["active"],
                        "current_vs_peak_pct": pct(m["active"]["avg_30d"], pk["active"]),
                        "calc": "max single-day active_accounts in the full history vs current 30-day mean"}
    s_now, s_then = rows[-1]["supply"], next(r["supply"] for r in rows if r["date"] >= yago)
    m["supply"] = {"total_now": s_now, "total_year_ago": s_then, "growth_pct": pct(s_now, s_then),
                   "calc": f"total_supply on {last} vs {yago} (NEAR = yocto/1e24)"}
    fees_365 = sum(r["fee_usd"] for r in window(rows, last, 365))
    m["fees"] = {"fees_usd_365d": fees_365, "mcap_now": rows[-1]["mcap"],
                 "mcap_to_fees": rows[-1]["mcap"] / fees_365 if fees_365 else None,
                 "issuance_usd_365d": (s_now - s_then) * rows[-1]["price"],
                 "calc": "sum txn_fee_usd over last 365 days; issuance = supply growth x current price"}
    m["fee_per_active"] = {"now": m["fee_usd"]["avg_30d"] / m["active"]["avg_30d"],
                           "year_ago": m["fee_usd"]["avg_30d_year_ago"] / m["active"]["avg_30d_year_ago"],
                           "calc": "30-day mean fee_usd / 30-day mean active accounts"}
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
    second_source(m, rows, os.path.dirname(path), last, yago)

    # leadlag section
    have_intents_fees = os.path.exists(os.path.join(os.path.dirname(path), "llama_intents_fees.json"))
    have_coingecko = os.path.exists(os.path.join(os.path.dirname(path), "coingecko_near.json"))
    if have_intents_fees and have_coingecko:
        intents_series = series(os.path.join(os.path.dirname(path), "llama_intents_fees.json"))
        price_series = {_day(ts): float(v) for ts, v in json.load(open(os.path.join(os.path.dirname(path), "coingecko_near.json")))["prices"]}
        active_series = {r["date"]: r["active"] for r in rows}

        # Determine the earliest date common to all three series for the weeks calculation.
        intents_dates = sorted(k for k in intents_series.keys() if k <= last)
        if intents_dates:
            series_start = intents_dates[0]
            # weeks = number of 7-day blocks ending at `last` that the Intents series covers
            days_diff = (dt.date.fromisoformat(last) - dt.date.fromisoformat(series_start)).days
            weeks = (days_diff // 7) + 1
            if weeks > 0:
                weekly_intents = weekly(intents_series, last, weeks)
                weekly_price = weekly(price_series, last, weeks)
                weekly_active = weekly(active_series, last, weeks)

                ch_intents = pct_changes(weekly_intents)
                ch_price = pct_changes(weekly_price)
                ch_active = pct_changes(weekly_active)

                # Compute correlations at 0,4,8,12 weeks lag
                corrs_intents = []
                corrs_price = []
                for lag in (0, 4, 8, 12):
                    corrs_intents.append(lagged_corr(ch_intents, ch_active, lag))
                    corrs_price.append(lagged_corr(ch_price, ch_active, lag))

                # Determine better leading indicator according to the rule:
                # I = largest absolute value among Intents correlations at lags 4,8,12 (ignore NaN)
                # P = same for price
                # "neither" when both I and P are below 0.2; "intents" when I >= P; else "price"
                def max_abs(vals):
                    valid = [abs(v) for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]
                    return max(valid) if valid else 0.0
                I_vals = corrs_intents[1:4]  # lags 4, 8, and 12 (indices 1, 2, and 3)
                P_vals = corrs_price[1:4]
                I = max_abs(I_vals)
                P = max_abs(P_vals)
                if I >= 0.2 or P >= 0.2:
                    better = "intents" if I >= P else "price"
                else:
                    better = "neither"

                # Build leadlag dict, omitting keys where correlation is NaN (per spec: stored as null-safe, if NaN key is omitted)
                leadlag = {
                    "n_weeks": weeks,
                    "first_week": series_start,
                    "last_week": last,
                    "better_leading_indicator": better,
                    "calc": "Pearson correlation between weekly % change of the indicator (NEAR Intents fees from DefiLlama, NEAR price from CoinGecko) and weekly % change of daily active accounts, with the indicator leading by 0, 4, 8 or 12 weeks. Weekly blocks are consecutive 7-day periods ending at the overall end date; each week's value is the mean of the days present in the series. better_leading_indicator is chosen among lags 4, 8, 12 weeks: 'neither' if both max absolute correlations are <0.2, otherwise the one with the larger absolute correlation."
                }
                # Add correlation keys only when not NaN
                lag_names = ["lag0w", "lag4w", "lag8w", "lag12w"]
                for i, lag_name in enumerate(lag_names):
                    intent_corr = corrs_intents[i]
                    price_corr = corrs_price[i]
                    
                    # Calculate additional statistics for intents
                    n_intents = lagged_n(ch_intents, ch_active, i * 4)
                    intent_stats = fisher_stats(intent_corr, n_intents)
                    
                    # Calculate additional statistics for price
                    n_price = lagged_n(ch_price, ch_active, i * 4)
                    price_stats = fisher_stats(price_corr, n_price)
                    
                    if isinstance(intent_corr, (int, float)) and not math.isnan(intent_corr):
                        if intent_stats is not None:
                            ci_low, ci_high, p_value = intent_stats
                            leadlag[f"intents_fees_to_active_n_{lag_name}"] = n_intents
                            leadlag[f"intents_fees_to_active_ci_low_{lag_name}"] = ci_low
                            leadlag[f"intents_fees_to_active_ci_high_{lag_name}"] = ci_high
                            leadlag[f"intents_fees_to_active_p_{lag_name}"] = p_value
                    
                    if isinstance(price_corr, (int, float)) and not math.isnan(price_corr):
                        if price_stats is not None:
                            ci_low, ci_high, p_value = price_stats
                            leadlag[f"price_to_active_n_{lag_name}"] = n_price
                            leadlag[f"price_to_active_ci_low_{lag_name}"] = ci_low
                            leadlag[f"price_to_active_ci_high_{lag_name}"] = ci_high
                            leadlag[f"price_to_active_p_{lag_name}"] = p_value
                        leadlag[f"intents_fees_to_active_corr_{lag_name}"] = intent_corr
                    if isinstance(price_corr, (int, float)) and not math.isnan(price_corr):
                        leadlag[f"price_to_active_corr_{lag_name}"] = price_corr
                m["leadlag"] = leadlag

    # bq cross-check keys
    dq_files = [
        os.path.join(os.path.dirname(path), "bq_active_accounts_daily.csv"),
        os.path.join(os.path.dirname(path), "bq_transactions_daily.csv"),
        os.path.join(os.path.dirname(path), "bq_contract_usage_daily.csv")
    ]
    if all(os.path.exists(f) for f in dq_files):
        def read_bq_file(filename):
            d = {}
            with open(filename, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_val = row["block_date"]
                    value = float(row["value"]) if row["value"].replace(".", "", 1).isdigit() else None
                    if value is not None:
                        d[date_val] = value
            return d

        def median(vals):
            if not vals:
                return 0.0
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            mid = n // 2
            if n % 2:
                return sorted_vals[mid]
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0

        aq_active = read_bq_file(dq_files[0])
        aq_txns = read_bq_file(dq_files[1])

        nb_active_map = {r["date"]: r["active"] for r in rows}
        nb_txn_map = {r["date"]: r["txns"] for r in rows}

        shared_active_dates = set(aq_active.keys()) & set(nb_active_map.keys())
        shared_txn_dates = set(aq_txns.keys()) & set(nb_txn_map.keys())

        if "crosscheck" not in m:
            m["crosscheck"] = {}

        if shared_active_dates:
            diffs_active_list = [
                100 * abs(aq_active[d] - nb_active_map[d]) / max(nb_active_map[d], 1e-9)
                for d in shared_active_dates if nb_active_map[d] != 0
            ]
            m["crosscheck"]["bq_active_vs_nearblocks_pct"] = median(diffs_active_list)
        if shared_txn_dates:
            diffs_txn_list = [
                100 * abs(aq_txns[d] - nb_txn_map[d]) / max(nb_txn_map[d], 1e-9)
                for d in shared_txn_dates if nb_txn_map[d] != 0
            ]
            m["crosscheck"]["bq_txns_vs_nearblocks_pct"] = median(diffs_txn_list)
            
            # Compute largest daily transaction drop
            dates_sorted = sorted(aq_txns.keys())
            drops = []
            for i in range(1, len(dates_sorted)):
                prev_date = dates_sorted[i-1]
                curr_date = dates_sorted[i]
                prev_val = aq_txns[prev_date]
                curr_val = aq_txns[curr_date]
                if prev_val > 0:
                    drop_pct = 100 * (prev_val - curr_val) / prev_val
                    if drop_pct > 0:
                        drops.append((drop_pct, curr_date))
            
            if drops:
                largest_drop_pct, largest_drop_date = max(drops, key=lambda x: x[0])
                m["crosscheck"]["bq_txns_largest_daily_drop_pct"] = largest_drop_pct
                m["crosscheck"]["bq_txns_largest_drop_date"] = largest_drop_date
            
            m["crosscheck"]["bq_txns_bigquery_days"] = len(aq_txns)

    windows_section(m, rows, os.path.dirname(path), last)

    # Monthly aggregation
    mon_a, mon_p = monthly(rows, "active"), monthly(rows, "price")
    mon_t = monthly(rows, "txns")
    mon_f = monthly(rows, "fee_usd", "sum")
    mon_n = monthly(rows, "new_acc")
    m["monthly"] = {}
    for k in mon_a:
        m["monthly"][k] = {
            "active": mon_a[k],
            "price": mon_p[k],
            "txns": mon_t[k],
            "fee_usd": mon_f[k],
            "new_acc": mon_n[k]
        }
    
    return m

if __name__ == "__main__":
    import sys
    m = compute(sys.argv[1] if len(sys.argv) > 1 else "data/charts_raw.json")
    json.dump(m, open("out/metrics.json", "w"), indent=1)
    s = {k: v for k, v in m.items() if k != "monthly"}
    print(json.dumps(s, indent=1, default=str))
