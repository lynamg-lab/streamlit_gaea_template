#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter dataset to only include *Total emissions* and *Stocks*
=============================================================

Usage (PowerShell):
-------------------
py .\2_Scriptes\filter_total_and_stocks.py --input ".\2_Scriptes\livestock_PREPARED_long.csv" --output ".\2_Scriptes\livestock_PREPARED_total_stocks.csv"

What it expects:
----------------
A "prepared long" CSV with at least these columns:
  - Metric  (e.g., 'Total_CO2e', 'CH4_CO2e', 'N2O_CO2e', 'Stocks', 'LSU')
Other columns (Area, Item, Year, Value, item_kind, etc.) are preserved.

What it does:
-------------
- Keeps only rows where Metric is either 'Total_CO2e' or 'Stocks' (case-insensitive).
- Optionally drops zero/NaN rows with --drop-zero.
- Writes the filtered CSV to --output.

If your file does not have a 'Metric' column, this tool will stop with
an informative error (we don't try to compute totals from raw files here).
"""

from __future__ import annotations
import argparse, sys
from pathlib import Path
import pandas as pd

WANTED = {"total_co2e", "stocks"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to prepared long CSV")
    ap.add_argument("--output", default="", help="Path to write the filtered CSV")
    ap.add_argument("--drop-zero", action="store_true", help="Drop rows where Value is 0 or NaN")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        sys.exit(f"Input not found: {inp}")

    outp = Path(args.output) if args.output else (inp.parent / (inp.stem + "_total_stocks.csv"))

    df = pd.read_csv(inp)

    if "Metric" not in df.columns:
        sys.exit("This file has no 'Metric' column. Please run your preprocessor first to create a prepared long file.")

    # Standardize metric names to match robustly
    def norm(x):
        return str(x).strip().lower().replace(" ", "_")

    keep_mask = df["Metric"].apply(norm).isin(WANTED)
    out = df[keep_mask].copy()

    if args.drop_zero and "Value" in out.columns:
        out = out[pd.to_numeric(out["Value"], errors="coerce").fillna(0) != 0]

    # Order columns: keep common ones first if present
    preferred = [c for c in ["Area","Item","Year","Metric","Value","item_kind","is_all","is_aggregated","is_atomic",
                             "region_EU","region_EUEEAUK","region_europe"] if c in out.columns]
    other = [c for c in out.columns if c not in preferred]
    out = out[preferred + other]

    out.to_csv(outp, index=False)
    print(f"Wrote {len(out):,} rows to: {outp}")

if __name__ == "__main__":
    main()
