"""Rebuild every number from the committed data, with no API key and no network, and check it.

    python3 verify.py            (or: make verify)

1. Recomputes out/metrics.json from data/charts_raw.json with metrics.compute() (nothing is written).
2. Compares every number with the committed out/metrics.json.
3. Checks that every metric the four judges cited in out/panel.json exists and has the cited value.
4. Checks every committed data file against data/SHA256SUMS.
Exit code 0 when everything matches, 1 otherwise.
"""
import argparse
import hashlib
import json
import math
import os
from typing import Optional

def flatten(obj, prefix: str = "") -> dict:
    """Return {dotted.path: number} for every int/float leaf (not bool) in nested dicts."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                out.update(flatten(v, path))
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                out[path] = v
    return out

def same(a, b, rel_tol: float = 1e-9) -> bool:
    """Equal within rel_tol; two NaNs count as equal."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=1e-12)

def compare(committed: dict, rebuilt: dict, rel_tol: float = 1e-9) -> list:
    """Lines describing every difference between two nested metric dicts, sorted by path."""
    c = flatten(committed)
    r = flatten(rebuilt)
    out = []
    for path in sorted(set(c) | set(r)):
        if path not in r:
            out.append(f"MISSING_IN_REBUILT {path}")
        elif path not in c:
            out.append(f"MISSING_IN_COMMITTED {path}")
        elif not same(c[path], r[path], rel_tol):
            out.append(f"DIFF {path} committed={c[path]} rebuilt={r[path]}")
    return out

def check_citations(panel: dict, metrics: dict, rel_tol: float = 1e-9) -> list:
    """BAD_CITATION lines for every cited path that is absent from *metrics* or has a different value."""
    flat = flatten(metrics)
    out = []
    for claim in panel.get("claims", []):
        for ev in claim.get("evidence", []):
            path, value = ev.get("path"), ev.get("value")
            if path not in flat or not isinstance(value, (int, float)) or isinstance(value, bool) \
                    or not same(flat[path], value, rel_tol):
                out.append(f"BAD_CITATION {claim.get('id')} {path}")
    return out

def count_citations(panel: dict) -> int:
    """Total number of evidence citations across all claims in *panel*."""
    return sum(len(c.get("evidence", [])) for c in panel.get("claims", []))

def uncommitted_names(folder: str = "data") -> set:
    """Names listed in ``folder/RAW_NOT_COMMITTED.txt``: source files that are hashed in SHA256SUMS but not shipped."""
    p = os.path.join(folder, "RAW_NOT_COMMITTED.txt")
    if not os.path.isfile(p):
        return set()
    with open(p, "r", encoding="utf-8") as f:
        return {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}

def check_sums(folder: str = "data") -> list:
    """Verify every committed data file against ``folder/SHA256SUMS``.

    Returns a list of problem strings (empty when everything matches).
    Possible problem strings:
        "SUMS_MISSING <path>"
        "HASH_FILE_MISSING <name>"
        "HASH_MISMATCH <name>"
        "UNLISTED_DATA_FILE <name>"
    """
    sums_path = os.path.join(folder, "SHA256SUMS")
    if not os.path.isfile(sums_path):
        return [f"SUMS_MISSING {sums_path}"]
    problems = []
    listed = {}
    order = []
    with open(sums_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("  ", 1)
            if len(parts) == 2:
                hash_hex, name = parts
                listed[name] = hash_hex
                order.append(name)

    absent_ok = uncommitted_names(folder)
    for name in order:
        file_path = os.path.join(folder, name)
        if not os.path.isfile(file_path):
            if name not in absent_ok:
                problems.append(f"HASH_FILE_MISSING {name}")
            continue
        with open(file_path, "rb") as f:
            data = f.read()
        computed = hashlib.sha256(data).hexdigest()
        if computed != listed[name]:
            problems.append(f"HASH_MISMATCH {name}")

    all_files = [
        f
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and not f.startswith(".")
        and f != "SHA256SUMS"
    ]
    for f in sorted(all_files):
        if f not in listed:
            problems.append(f"UNLISTED_DATA_FILE {f}")

    return problems

def count_sums(folder: str = "data") -> int:
    """Number of non-empty lines in ``folder/SHA256SUMS`` (0 when the file is absent)."""
    sums_path = os.path.join(folder, "SHA256SUMS")
    if not os.path.isfile(sums_path):
        return 0
    count = 0
    with open(sums_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count

def check_derived(metrics_path: str = "out/metrics.json", panel_path: str = "out/panel.json",
                  sums_path: str = "data/DERIVED_SHA256SUMS") -> list:
    """The derived numbers (out/metrics.json, out/panel.json) against the hashes recorded when they were built."""
    if not os.path.isfile(sums_path):
        return [f"SUMS_MISSING {sums_path}"]
    want = {}
    with open(sums_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                h, name = line.rstrip("\n").split("  ", 1)
                want[name] = h
    problems = []
    for name, path in (("out/metrics.json", metrics_path), ("out/panel.json", panel_path)):
        if name not in want:
            problems.append(f"DERIVED_NOT_RECORDED {name}")
        elif hashlib.sha256(open(path, "rb").read()).hexdigest() != want[name]:
            problems.append(f"DERIVED_HASH_MISMATCH {name}")
    return problems

def record_derived(metrics_path: str = "out/metrics.json", panel_path: str = "out/panel.json",
                   sums_path: str = "data/DERIVED_SHA256SUMS") -> None:
    """Write the hashes of the derived numbers. Run by `make numbers` after metrics.py."""
    with open(sums_path, "w", encoding="utf-8", newline="\n") as f:
        for name, path in (("out/metrics.json", metrics_path), ("out/panel.json", panel_path)):
            f.write(hashlib.sha256(open(path, "rb").read()).hexdigest() + "  " + name + "\n")

def bq_only(folder: str = "data") -> dict:
    """The numbers that come from the BigQuery result files alone (these files are committed)."""
    import csv
    p = os.path.join(folder, "bq_transactions_daily.csv")
    if not os.path.isfile(p):
        return {}
    v = {}
    with open(p, newline="") as f:
        for row in csv.DictReader(f):
            v[row["block_date"]] = float(row["value"])
    days = sorted(v)
    drops = [(100 * (v[a] - v[b]) / v[a], b) for a, b in zip(days, days[1:]) if v[a] > 0 and v[a] > v[b]]
    out = {"bq_txns_bigquery_days": len(v)}
    if drops:
        pct, date = max(drops)
        out["bq_txns_largest_daily_drop_pct"] = pct
        out["bq_txns_largest_drop_date"] = date
    return out

def main_offline(args) -> int:
    """No raw files: check what can be checked from files that are committed."""
    with open(args.metrics, "r", encoding="utf-8") as f:
        committed = json.load(f)
    with open(args.panel, "r", encoding="utf-8") as f:
        panel = json.load(f)
    problems = check_derived(args.metrics, args.panel, os.path.join(args.sums_dir, "DERIVED_SHA256SUMS"))
    problems += check_citations(panel, committed) + check_sums(args.sums_dir)
    cc = committed.get("crosscheck", {})
    rebuilt = bq_only(args.sums_dir)
    for k, v in rebuilt.items():
        if k not in cc or (isinstance(v, float) and not same(cc[k], v)) or (isinstance(v, str) and cc[k] != v):
            problems.append(f"DIFF crosscheck.{k} committed={cc.get(k)} rebuilt={v}")
    if problems:
        for p in problems:
            print(p)
        print(f"VERIFY FAILED: {len(problems)} problems")
        return 1
    missing = sorted(uncommitted_names(args.sums_dir) - {n for n in os.listdir(args.sums_dir)})
    print(f"VERIFY OK (offline): {len(flatten(committed))} numbers in out/metrics.json match the hash recorded when they were built, "
          f"{len(rebuilt)} BigQuery numbers rebuilt from data/bq_*.csv, {count_citations(panel)} panel citations checked, "
          f"{count_sums(args.sums_dir)} files in {args.sums_dir}/SHA256SUMS ({len(missing)} source files are hashed but not shipped; their terms bar republishing).")
    print("To rebuild all the numbers from the sources: python3 verify_online.py")
    return 0

def main(argv: Optional[list] = None, compute=None) -> int:
    """CLI: rebuild metrics, compare, check citations and SHA-256 hashes; return 0 when all pass."""
    ap = argparse.ArgumentParser(
        description="Rebuild every number from the committed data, with no API key and no network, and check it."
    )
    ap.add_argument("--data", default="data/charts_raw.json")
    ap.add_argument("--metrics", default="out/metrics.json")
    ap.add_argument("--panel", default="out/panel.json")
    ap.add_argument("--sums-dir", default="data")
    ap.add_argument("--mode", choices=["auto", "offline", "full"], default="auto",
                    help="auto: full when data/charts_raw.json is present, else offline. (verify_online.py re-fetches every source.)")
    ap.add_argument("--record", action="store_true", help="record the hashes of out/metrics.json and out/panel.json")
    args = ap.parse_args(argv)

    if args.record:
        record_derived(args.metrics, args.panel, os.path.join(args.sums_dir, "DERIVED_SHA256SUMS"))
        print("recorded", os.path.join(args.sums_dir, "DERIVED_SHA256SUMS"))
        return 0
    mode = args.mode
    if mode == "auto":
        mode = "full" if (compute is not None or os.path.isfile(args.data)) else "offline"
    if mode == "offline":
        return main_offline(args)

    if compute is None:
        import metrics as metrics_module
        compute = metrics_module.compute

    rebuilt = compute(args.data)

    with open(args.metrics, "r", encoding="utf-8") as f:
        committed = json.load(f)

    with open(args.panel, "r", encoding="utf-8") as f:
        panel = json.load(f)

    problems = compare(committed, rebuilt) + check_citations(panel, committed) + check_sums(args.sums_dir)
    if not problems:
        n_numbers = len(flatten(committed))
        n_citations = count_citations(panel)
        n_files = count_sums(args.sums_dir)
        print(
            f"VERIFY OK: {n_numbers} numbers rebuilt from the full local data, {n_citations} panel citations checked, {n_files} data files match {args.sums_dir}/SHA256SUMS"
        )
        return 0

    for p in problems:
        print(p)
    print(f"VERIFY FAILED: {len(problems)} problems")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
