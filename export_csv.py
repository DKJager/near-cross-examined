"""Export NearBlocks daily data and NEAR Intents Sunday samples as CSV, then write data/SHA256SUMS.

Reads:
    data/charts_raw.json
    data/intents_days.json
Writes:
    data/nearblocks_daily.csv
    data/intents_sundays.csv
    data/SHA256SUMS  (hash of every regular, non-dot file in data/ except itself)
"""
import argparse
import csv
import hashlib
import json
import os
from typing import List


CHART_COLUMNS: List[str] = [
    "date",
    "near_price",
    "market_cap",
    "total_supply",
    "circulating_supply",
    "blocks",
    "gas_fee",
    "gas_used",
    "txns",
    "txn_volume",
    "txn_volume_usd",
    "txn_fee",
    "txn_fee_usd",
    "new_accounts",
    "active_accounts",
    "deleted_accounts",
    "new_contracts",
    "active_contracts",
    "unique_contracts",
    "multichain_txns",
]

INTENT_COLUMNS: List[str] = ["date", "swaps", "usd", "pages"]


def _write_csv(path: str, header: List[str], rows: List[List[str]]) -> int:
    """Write *rows* to *path* using *header*.
    Returns the number of data rows written (excluding the header)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def export_charts(src: str = "data/charts_raw.json", dst: str = "data/nearblocks_daily.csv") -> int:
    """Write the NearBlocks daily-chart rows to a CSV file.

    Returns the number of data rows written (excluding the header).
    Missing or None cells become empty strings.
    """
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    charts = data.get("charts", [])
    rows: List[List[str]] = []
    for entry in charts:
        row = [
            "" if col not in entry or entry[col] is None else str(entry[col])
            for col in CHART_COLUMNS
        ]
        rows.append(row)
    return _write_csv(dst, CHART_COLUMNS, rows)


def export_intents(src: str = "data/intents_days.json", dst: str = "data/intents_sundays.csv") -> int:
    """Write the NEAR Intents Sunday-sample rows to a CSV file.

    Returns the number of data rows written (excluding the header).
    The ``top_origin`` field is deliberately dropped.
    """
    with open(src, "r", encoding="utf-8") as f:
        intents = json.load(f)
    rows: List[List[str]] = []
    for entry in intents:
        row = [
            str(entry.get("date", "")),
            str(entry.get("swaps", "")),
            repr(float(entry.get("usd", 0.0))) if entry.get("usd") is not None else "",
            str(entry.get("pages", "")),
        ]
        rows.append(row)
    return _write_csv(dst, INTENT_COLUMNS, rows)


def sums_lines(folder: str = "data") -> List[str]:
    """Return one sha256sum-format line per regular, non-dot, non-SHA256SUMS file."""
    lines: List[str] = []
    for name in sorted(os.listdir(folder)):
        if name.startswith(".") or name == "SHA256SUMS":
            continue
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {name}")
    return lines


def write_sums(folder: str = "data") -> int:
    """Write ``folder/SHA256SUMS`` with the sorted checksum lines.

    Returns the number of files listed (one per line).
    """
    lines = sums_lines(folder)
    sums_path = os.path.join(folder, "SHA256SUMS")
    with open(sums_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")
    return len(lines)


def main(argv: List[str] | None = None) -> int:
    """Entry point.

    Option ``--data <folder>`` (default "data") controls where the JSON inputs and
    CSV outputs live.  Writes nearblocks_daily.csv, intents_sundays.csv and finally
    SHA256SUMS into that folder.  Returns 0.
    """
    parser = argparse.ArgumentParser(description="Export CSV files and SHA256SUMS")
    parser.add_argument("--data", default="data", help="Folder containing input JSON and where CSVs are written")
    args = parser.parse_args(argv)

    data_dir = args.data
    charts_src = os.path.join(data_dir, "charts_raw.json")
    charts_dst = os.path.join(data_dir, "nearblocks_daily.csv")
    intents_src = os.path.join(data_dir, "intents_days.json")
    intents_dst = os.path.join(data_dir, "intents_sundays.csv")

    r1 = export_charts(charts_src, charts_dst)
    r2 = export_intents(intents_src, intents_dst)
    n_files = write_sums(data_dir)

    print(
        f"EXPORT OK: {r1} NearBlocks days, {r2} NEAR Intents Sundays, {n_files} files in {data_dir}/SHA256SUMS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
