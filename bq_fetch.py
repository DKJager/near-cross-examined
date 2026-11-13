"""Fetch NEAR BigQuery data: print SQL, run from fixtures, or run live.

    python3 bq_fetch.py           # print SQL text and exit 0
    python3 bq_fetch.py --from-fixture DIR --out data   # copy fixture CSVs
    python3 bq_fetch.py --run     # live query (needs google credentials)
"""
import json
import argparse
import sys
import csv
import datetime
import os
import hashlib
from typing import Optional

QUERIES = {
    "active_accounts_daily": "sql/active_accounts_daily.sql",
    "transactions_daily": "sql/transactions_daily.sql",
    "contract_usage_daily": "sql/contract_usage_daily.sql",
}

_BQ_URL = "https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=crypto_near_mainnet_us"

def read_queries(folder: str = "") -> dict:
    """Return {name: SQL text} from the sql/ files."""
    out = {}
    for name, path in QUERIES.items():
        full = os.path.join(folder, path)
        with open(full, encoding="utf-8") as f:
            out[name] = f.read()
    return out

def date_range(metrics_path: str = "out/metrics.json") -> tuple:
    """Return (start, end) as 'YYYY-MM-DD' from metrics as_of."""
    with open(metrics_path, encoding="utf-8") as f:
        m = json.load(f)
    end = m["as_of"]
    end_date = datetime.date.fromisoformat(end)
    start_date = end_date - datetime.timedelta(days=364)
    return (start_date.isoformat(), end)

def write_csv(rows: list, dst: str) -> int:
    """Write rows as CSV with header block_date,value. Return row count."""
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["block_date", "value"])
        for r in rows:
            w.writerow(r)
    return len(rows)

def register(data_dir: str, names: list) -> None:
    """Update MANIFEST.json and SHA256SUMS in data_dir for the bq_*.csv files only."""
    import export_csv
    path_manifest = os.path.join(data_dir, "MANIFEST.json")
    # Load existing manifest only if it exists
    if os.path.exists(path_manifest):
        with open(path_manifest, encoding="utf-8") as f:
            man = json.load(f)
    else:
        man = {}

    # Process only the bq_*.csv files to be added
    for name in names:
        dst = os.path.join(data_dir, f"bq_{name}.csv")
        with open(dst, "rb") as f:
            content = f.read()
        sha = hashlib.sha256(content).hexdigest()
        bts = len(content)
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        key = f"bq_{name}.csv"
        what = f"BigQuery daily {name.replace('_', ' ')} from {QUERIES[name]}"
        man[key] = {
            "bytes": bts,
            "fetched_at": now_utc,
            "sha256": sha,
            "url": _BQ_URL,
            "what": what,
        }

    with open(path_manifest, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2)

    # Merge the bq_*.csv hashes into data/SHA256SUMS; keep every existing line,
    # so the committed data files stay covered by `make verify`.
    sums_path = os.path.join(data_dir, "SHA256SUMS")
    keep = {}
    if os.path.exists(sums_path):
        with open(sums_path, encoding="utf-8") as f:
            for ln in f:
                parts = ln.split()
                if len(parts) == 2:
                    keep[parts[1]] = parts[0]
    for name in names:
        file_path = os.path.join(data_dir, f"bq_{name}.csv")
        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                keep[f"bq_{name}.csv"] = hashlib.sha256(f.read()).hexdigest()
    if "MANIFEST.json" in keep:
        with open(path_manifest, "rb") as f:
            keep["MANIFEST.json"] = hashlib.sha256(f.read()).hexdigest()
    with open(sums_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(f"{h}  {n}\n" for n, h in sorted(keep.items())))

def run_live(data_dir: str, metrics_path: str) -> None:
    """Run BigQuery queries and write results to data_dir."""
    try:
        from google.cloud import bigquery
    except ImportError:
        print(
            "bq_fetch.py: Google credentials or the google-cloud-bigquery package are missing; nothing was run"
        )
        return 2

    client = bigquery.Client()
    start, end = date_range(metrics_path)
    queries = read_queries()
    written = []
    for name, sql in queries.items():
        sql_filled = sql.replace("@start_date", f"'{start}'").replace("@end_date", f"'{end}'")
        job = client.query(sql_filled)
        rows = [(str(r.block_date), str(r.value)) for r in job]
        dst = os.path.join(data_dir, f"bq_{name}.csv")
        write_csv(rows, dst)
        written.append(name)
    register(data_dir, written)
    return 0

def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="NEAR BigQuery fetch tool")
    ap.add_argument("--from-fixture", help="Directory with fixture CSV files")
    ap.add_argument("--out", default="data", help="Output directory")
    ap.add_argument("--run", action="store_true", help="Run live BigQuery queries")
    args = ap.parse_args(argv)

    if args.run:
        return run_live(args.out, "out/metrics.json")

    if args.from_fixture:
        names = []
        for name in QUERIES:
            src = os.path.join(args.from_fixture, f"{name}.csv")
            with open(src, encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                rows = list(reader)
            write_csv(rows, os.path.join(args.out, f"bq_{name}.csv"))
            names.append(name)
        register(args.out, names)
        return 0

    queries = read_queries()
    for name, path in QUERIES.items():
        print(f"-- {path}")
        print(queries[name])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
