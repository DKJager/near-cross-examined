"""Download the raw data. Public endpoints, no key.

    python3 fetch.py

Every response is saved byte for byte in data/ (or --out), for the same dates as the committed numbers (--as-of), and data/MANIFEST.json records where each file came from,
when, its size and its SHA-256. `verify.py` checks those hashes, so a changed data file cannot pass unnoticed.
Then `python3 export_csv.py` writes the same daily series as CSV.
"""
import argparse
import calendar
import datetime as dt
import hashlib
import json
import os
import time
import urllib.request

LLAMA = "https://api.llama.fi"
SOURCES = [
    # (file, url, what it is)
    ("charts_raw.json", "https://api.nearblocks.io/v1/charts",
     "NearBlocks: daily chain data (accounts, transactions, gas fees, transfer volume, supply, price)"),
    ("stats_raw.json", "https://api.nearblocks.io/v1/stats", "NearBlocks: current network stats"),
    ("llama_fees_near.json", LLAMA + "/overview/fees/near?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=false&dataType=dailyFees",
     "DefiLlama: daily fees paid by users of every app on NEAR, and the chain's own gas fees, by protocol"),
    ("llama_revenue_near.json", LLAMA + "/overview/fees/near?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyRevenue",
     "DefiLlama: daily revenue kept by protocols on NEAR"),
    ("llama_holders_revenue_near.json", LLAMA + "/overview/fees/near?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyHoldersRevenue",
     "DefiLlama: daily revenue returned to token holders on NEAR (NEAR Intents buybacks since 23 Feb 2026, and burned gas)"),
    ("llama_gas_fees_near.json", LLAMA + "/summary/fees/near?dataType=dailyFees",
     "DefiLlama (data from Allium): daily gas fees on the NEAR chain; a second source for NearBlocks txn_fee_usd"),
    ("llama_intents_fees.json", LLAMA + "/summary/fees/near-intents?dataType=dailyFees",
     "DefiLlama: daily gross fees on NEAR Intents swaps, every day since May 2025"),
    ("llama_intents_revenue.json", LLAMA + "/summary/fees/near-intents?dataType=dailyRevenue",
     "DefiLlama: daily NEAR Intents revenue captured by NEAR"),
    ("llama_tvl_near.json", LLAMA + "/v2/historicalChainTvl/Near", "DefiLlama: daily total value locked on NEAR"),
    ("llama_dex_near.json", LLAMA + "/overview/dexs/near?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true",
     "DefiLlama: daily exchange volume on NEAR"),
    ("llama_stablecoins_near.json", "https://stablecoins.llama.fi/stablecoincharts/Near", "DefiLlama: daily stablecoin supply on NEAR"),
    ("coingecko_near.json", "https://api.coingecko.com/api/v3/coins/near/market_chart/range?vs_currency=usd&from={cg_from}&to={cg_to}",
     "CoinGecko: daily NEAR price and market cap, from 12 Nov 2025 to the as-of day; a second source for the NearBlocks price"),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download the raw series for the same dates as the committed numbers.")
    ap.add_argument("--out", default="data", help="folder to write into (default data/)")
    ap.add_argument("--as-of", default=None, help="last day (YYYY-MM-DD); default is as_of in out/metrics.json")
    args = ap.parse_args(argv)
    out = args.out
    as_of = args.as_of
    if as_of is None:
        try:
            as_of = json.load(open("out/metrics.json"))["as_of"]
        except OSError:
            as_of = dt.date.today().isoformat()
    # CoinGecko's public API serves only the last 365 days, so a later re-fetch cannot go back to 12 Nov 2025: it starts at the oldest day allowed
    cg_from = calendar.timegm(max(dt.date(2025, 11, 12), dt.date.today() - dt.timedelta(days=364)).timetuple())
    cg_to = calendar.timegm((dt.date.fromisoformat(as_of) + dt.timedelta(days=1)).timetuple())
    os.makedirs(out, exist_ok=True)
    manifest = {}
    for name, url, what in SOURCES:
        url = url.format(cg_from=cg_from, cg_to=cg_to) if "{cg_from}" in url else url
        req = urllib.request.Request(url, headers={"User-Agent": "near-cross-examined/1.0", "Accept": "application/json"})
        for attempt in range(5):
            try:
                b = urllib.request.urlopen(req, timeout=120).read()
                json.loads(b)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 4:
                    raise SystemExit(f"FAILED {name}: {exc}")
                time.sleep(20 * (attempt + 1))
        with open(os.path.join(out, name), "wb") as f:
            f.write(b)
        manifest[name] = {"url": url, "what": what, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                          "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        print(name, len(b), "bytes")
        time.sleep(1.5)
    # intents_days.json is written by intents.py (it needs a key and about a minute per sampled day); hash it here if present
    p = os.path.join(out, "intents_days.json")
    if os.path.exists(p):
        b = open(p, "rb").read()
        manifest["intents_days.json"] = {"url": "https://explorer.near-intents.org/api/v0/transactions", "bytes": len(b),
                                         "what": "NEAR Intents Explorer: successful 1Click swaps on one full UTC Sunday per week (intents.py)",
                                         "sha256": hashlib.sha256(b).hexdigest(), "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p)))}
    with open(os.path.join(out, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print("MANIFEST.json", len(manifest), "files")


if __name__ == "__main__":
    main()
