"""Rebuild every number from a fresh download of every source, for the same dates as the committed numbers.

    python3 verify_online.py          (or: make verify-online)

Needs the internet (public endpoints, no key) and about two minutes. It runs fetch.py into data_online/ (your data/ is untouched),
rebuilds all the numbers with metrics.compute(as_of=...), and compares each with out/metrics.json. Sources revise recent days, so
a number may differ slightly: --tol (default 2%) is the relative difference allowed, and the raw files that changed since the
recorded fetch (SHA256SUMS) are listed. The NEAR Intents Explorer sample needs a partner key (INTENTS_JWT); without its file those
numbers are skipped and the count says so. verify.py itself never touches the network.
"""
import argparse
import hashlib
import json
import os
import sys

from verify import flatten, same, uncommitted_names


def main_online(args) -> int:
    """Re-fetch every series for the same dates into data_online/, rebuild every number, compare."""
    import shutil
    import subprocess
    import sys
    import metrics as metrics_module
    with open(args.metrics, "r", encoding="utf-8") as f:
        committed = json.load(f)
    as_of = committed["as_of"]
    out = "data_online"
    os.makedirs(out, exist_ok=True)
    rc = 0 if getattr(args, "reuse", False) and os.path.isfile(os.path.join(out, "charts_raw.json")) else \
        subprocess.call([sys.executable, "fetch.py", "--out", out, "--as-of", as_of])
    if rc:
        print("VERIFY FAILED: fetch.py failed")
        return 1
    for name in os.listdir(args.sums_dir):          # files we do commit (BigQuery results) and anything kept locally
        if name.startswith("bq_") or (name == "intents_days.json" and os.path.isfile(os.path.join(args.sums_dir, name))):
            shutil.copy(os.path.join(args.sums_dir, name), os.path.join(out, name))
    have_intents = os.path.isfile(os.path.join(out, "intents_days.json"))
    rebuilt = metrics_module.compute(os.path.join(out, "charts_raw.json"), as_of=as_of)
    c, r = flatten(committed), flatten(rebuilt)
    skipped = [p for p in c if p not in r and not have_intents and (p.startswith("intents.") or p.startswith("intents_weekly."))]
    tol = args.tol
    def _abs_ok(p):
        # price statistics use CoinGecko's last 365 days only, so a later fetch drops the oldest days and they shift a little
        return abs(c[p] - r[p]) <= (0.1 if p.startswith("leadlag.price_") else args.abs_tol)
    bad = [p for p in sorted(c) if p in r and not (same(c[p], r[p], tol) or _abs_ok(p))]
    missing = [p for p in sorted(c) if p not in r and p not in skipped]
    same_raw = []
    changed_raw = []
    want = {}
    sp = os.path.join(args.sums_dir, "SHA256SUMS")
    for line in open(sp, encoding="utf-8"):
        if line.strip():
            h, n = line.rstrip("\n").split("  ", 1)
            want[n] = h
    for n in sorted(uncommitted_names(args.sums_dir)):
        p = os.path.join(out, n)
        if os.path.isfile(p):
            (same_raw if hashlib.sha256(open(p, "rb").read()).hexdigest() == want.get(n) else changed_raw).append(n)
    print(f"raw files identical to the recorded fetch: {len(same_raw)}; changed since (sources revise data): {len(changed_raw)} {changed_raw}")
    for p in bad[:40]:
        print(f"DIFF {p} committed={c[p]} rebuilt={r[p]}")
    for p in missing[:20]:
        print(f"MISSING_IN_REBUILT {p}")
    exact = sum(1 for p in c if p in r and same(c[p], r[p]))
    if bad or missing:
        print(f"VERIFY FAILED (online): {len(bad)} numbers differ by more than {tol:.0%} and {args.abs_tol}, {len(missing)} missing, of {len(c)}")
        return 1
    print(f"VERIFY OK (online): {len(c) - len(skipped)} of {len(c)} numbers rebuilt from a fresh fetch for dates up to {as_of}; "
          f"{exact} equal to the committed value, the rest within {tol:.0%} or {args.abs_tol} (sources revise recent days; CoinGecko's public API cannot go back past 365 days, so price statistics shift slightly)"
          + (f"; {len(skipped)} Intents Explorer numbers skipped (needs INTENTS_JWT)" if skipped else ""))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics", default="out/metrics.json")
    ap.add_argument("--sums-dir", default="data")
    ap.add_argument("--tol", type=float, default=0.02, help="relative difference allowed (sources revise recent days)")
    ap.add_argument("--abs-tol", type=float, default=0.02, help="or an absolute difference this small (correlations near zero)")
    ap.add_argument("--reuse", action="store_true", help="rebuild from an earlier download in data_online/ instead of fetching again")
    args = ap.parse_args(argv)
    return main_online(args)


if __name__ == "__main__":
    raise SystemExit(main())
