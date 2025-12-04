#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess livestock-style dataset — v4g
=======================================

Fixes for duplicated LSU rows:
- **Only split generic 'Cattle'** into dairy/non-dairy for (Area, Year) where
  there are **no existing atomic cattle rows** ("Cattle, dairy" or "Cattle, non-dairy").
  This prevents creating a second "Cattle, dairy"/"Cattle, non-dairy" line.
- **Group LSU** at the end by (Area, Item, Year) to collapse any upstream duplicates
  (e.g., accidental multi-rows from the input).

Also includes earlier improvements:
- Canonical cattle labels (non-dairy check before dairy)
- Region boolean flags; generic item_kind flags
"""

from __future__ import annotations
import argparse, re, sys
from pathlib import Path
import pandas as pd

ALL_ANIMALS_LIST = ["All animals","All animal","All livestock","Total animals","Animals, all"]
AGGREGATE_LIST   = ["Camels and Llamas","Cattle","Mules and Asses","Poultry Birds","Sheep and Goats","Swine"]
ATOMIC_LIST      = ["Asses","Buffalo","Camels","Swine, breeding","Swine, market","Turkeys",
                    "Cattle, dairy","Cattle, non-dairy","Chickens, broilers","Chickens, layers",
                    "Ducks","Goats","Horses","Sheep"]

EXCLUDE_ITEMS = {s.lower() for s in ["Chickens","Mules and hinnies","(blank)",""]}

EU = {"Austria","Belgium","Bulgaria","Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia",
      "Finland","France","Germany","Greece","Hungary","Ireland","Italy","Latvia","Lithuania","Luxembourg",
      "Malta","Netherlands","Poland","Portugal","Romania","Slovakia","Slovenia","Spain","Sweden"}
EEA_PLUS_UK = EU.union({"Iceland","Liechtenstein","Norway","United Kingdom","UK"})
EUROPE_WIDE = {"Albania","Andorra","Armenia","Austria","Azerbaijan","Belarus","Belgium","Bosnia and Herzegovina","Bulgaria",
               "Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia","Finland","France","Georgia","Germany","Greece",
               "Hungary","Iceland","Ireland","Italy","Kazakhstan","Kosovo","Latvia","Liechtenstein","Lithuania","Luxembourg",
               "Malta","Moldova","Monaco","Montenegro","Netherlands","North Macedonia","Norway","Poland","Portugal","Romania",
               "Russia","San Marino","Serbia","Slovakia","Slovenia","Spain","Sweden","Switzerland","Turkey","Ukraine",
               "United Kingdom","UK","Vatican City"}

def detect_year_cols(cols):
    return [c for c in cols if isinstance(c, str) and c.startswith("Y") and c[1:].isdigit()]

def normalize_element(e: str) -> str | None:
    if e is None: return None
    s = str(e).strip().lower()
    if re.search(r"(^stocks?$|\bstock\b)", s, re.I): return "Stocks"
    if re.search(r"\b(ch4|methane)\b", s, re.I):     return "CH4"
    if re.search(r"\b(n2o|nitrous)\b", s, re.I):     return "N2O"
    return None

def gwp_pair(name: str):
    return {"AR4":(25.0,298.0),"AR5":(28.0,265.0),"AR6_NOCCF":(27.2,273.0),"AR6_CCF":(29.8,273.0)}.get(name.strip().upper(), (27.2,273.0))

# --- canonicalizer (non-dairy before dairy) ---
_non_dairy_pat = re.compile(r"\bnon-?dairy\b", flags=re.I)
_dairy_pat = re.compile(r"\bdairy\b", flags=re.I)
_other_pat = re.compile(r"\bother\b", flags=re.I)
def canonical_item(item: str) -> str:
    s = str(item).strip()
    low = s.lower().replace("non dairy", "non-dairy")
    low = re.sub(r"\s+", " ", low)
    if ("cattle" in low) or ("bovine" in low):
        if _non_dairy_pat.search(low) or _other_pat.search(low):
            return "Cattle, non-dairy"
        if _dairy_pat.search(low):
            return "Cattle, dairy"
        return "Cattle"
    return s

def item_kind(label: str) -> str:
    low = canonical_item(label).lower()
    if low in {x.lower() for x in ALL_ANIMALS_LIST}: return "All"
    if low in {x.lower() for x in AGGREGATE_LIST}:   return "aggregated"
    if low in {x.lower() for x in ATOMIC_LIST}:      return "atomic"
    return "atomic"

def default_lsu_weight(item: str) -> float:
    il = canonical_item(item).lower()
    if "dairy" in il and "cattle" in il: return 1.0
    if "cattle" in il: return 0.8
    if "buffalo" in il: return 1.0
    if "sheep" in il or "goat" in il: return 0.1
    if "pig" in il or "swine" in il: return 0.3
    if "poultry" in il or "chicken" in il or "turkey" in il or "duck" in il: return 0.01
    if "horse" in il or "equid" in il: return 0.8
    return 1.0

def is_livestock_total_element(label: str) -> bool:
    if label is None: return False
    s = str(label)
    return bool(re.search(r"livestock", s, re.I) and re.search(r"total", s, re.I))

def region_flags(area: str):
    a = str(area).strip()
    return (a in EUROPE_WIDE, a in EU, a in EEA_PLUS_UK)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to raw CSV (e.g., ...\\1_Donnees\\Emissions_*.csv)")
    ap.add_argument("--output", default="", help="Output CSV path. Default: <input_folder>\\livestock_PREPARED_long.csv")
    ap.add_argument("--gwp", default="AR6_NOCCF", help="AR4|AR5|AR6_NOCCF|AR6_CCF")
    ap.add_argument("--split-cattle", default="true", help="true|false — split generic 'Cattle' for LSU only when no atomic cattle present")
    ap.add_argument("--dairy-share", type=float, default=35.0, help="% dairy within Cattle when splitting")
    ap.add_argument("--only-livestock-total", default="true", help="true|false — for CH4/N2O keep only 'Livestock total'")
    args = ap.parse_args()

    split_cattle = str(args.split_cattle).strip().lower() in {"1","true","yes","y"}
    only_lt = str(args.only_livestock_total).strip().lower() in {"1","true","yes","y"}
    dairy_frac = max(0.0, min(1.0, (args.dairy_share or 0.0)/100.0))
    GWP_CH4, GWP_N2O = gwp_pair(args.gwp)

    inp = Path(args.input)
    if not inp.exists():
        sys.exit(f"Input not found: {inp}")
    outp = Path(args.output) if args.output else (inp.parent / "livestock_PREPARED_long.csv")
    outp.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(inp)

    required = {"Area","Item","Element"}
    missing = required.difference(df.columns)
    if missing:
        sys.exit(f"ERROR: CSV missing columns: {', '.join(sorted(missing))}")

    for c in ["Area","Item","Element"]:
        df[c] = df[c].astype(str).str.strip()

    # Drop excluded/blank; canonicalize
    df = df[~df["Item"].str.strip().str.lower().isin(EXCLUDE_ITEMS)].copy()
    df["Item"] = df["Item"].apply(canonical_item)

    year_cols = detect_year_cols(df.columns)
    if not year_cols:
        sys.exit("ERROR: No year columns found (expected 'Y2010', 'Y2018', etc.)")

    df["ElementNorm"] = df["Element"].apply(normalize_element)
    df = df[df["ElementNorm"].notna()].copy()
    if only_lt:
        mask_gases = df["ElementNorm"].isin(["CH4","N2O"])
        lt_mask = df["Element"].apply(is_livestock_total_element)
        df = df[(~mask_gases) | (mask_gases & lt_mask)].copy()

    # Flags
    df["item_kind"] = df["Item"].apply(item_kind)
    df["is_all"] = df["item_kind"].eq("All")
    df["is_aggregated"] = df["item_kind"].eq("aggregated")
    df["is_atomic"] = df["item_kind"].eq("atomic")

    # Region flags
    reg = df["Area"].apply(region_flags).tolist()
    df["region_europe"]  = [t[0] for t in reg]
    df["region_EU"]      = [t[1] for t in reg]
    df["region_EUEEAUK"] = [t[2] for t in reg]

    # Long format
    id_keep = ["Area","Item","Element","ElementNorm","item_kind","is_all","is_aggregated","is_atomic",
               "region_EU","region_EUEEAUK","region_europe"]
    long = df.melt(id_vars=id_keep, value_vars=year_cols, var_name="Year", value_name="Value")
    long["Year"] = long["Year"].str[1:].astype(int)

    prepared = []

    # Stocks (as-is)
    stocks = long[long["ElementNorm"]=="Stocks"][["Area","Item","Year","Value","item_kind","is_all","is_aggregated","is_atomic"]].copy()
    if not stocks.empty:
        s = stocks.copy(); s["Metric"]="Stocks"; prepared.append(s)

    # CH4 -> CO2e
    ch4 = long[long["ElementNorm"]=="CH4"][["Area","Item","Year","Value","item_kind","is_all","is_aggregated","is_atomic"]].copy()
    if not ch4.empty:
        ch4["Value"] = ch4["Value"] * GWP_CH4
        ch4e = ch4.groupby(["Area","Item","Year","item_kind","is_all","is_aggregated","is_atomic"], as_index=False)["Value"].sum()
        ch4e["Metric"]="CH4_CO2e"; prepared.append(ch4e)

    # N2O -> CO2e
    n2o = long[long["ElementNorm"]=="N2O"][["Area","Item","Year","Value","item_kind","is_all","is_aggregated","is_atomic"]].copy()
    if not n2o.empty:
        n2o["Value"] = n2o["Value"] * GWP_N2O
        n2oe = n2o.groupby(["Area","Item","Year","item_kind","is_all","is_aggregated","is_atomic"], as_index=False)["Value"].sum()
        n2oe["Metric"]="N2O_CO2e"; prepared.append(n2oe)

    # Total CO2e
    if not ch4.empty or not n2o.empty:
        ch4_sum = ch4.groupby(["Area","Item","Year","item_kind","is_all","is_aggregated","is_atomic"], as_index=False)["Value"].sum().rename(columns={"Value":"CH4_CO2e"})
        n2o_sum = n2o.groupby(["Area","Item","Year","item_kind","is_all","is_aggregated","is_atomic"], as_index=False)["Value"].sum().rename(columns={"Value":"N2O_CO2e"})
        tot = pd.merge(ch4_sum, n2o_sum, on=["Area","Item","Year","item_kind","is_all","is_aggregated","is_atomic"], how="outer").fillna(0.0)
        tot["Value"] = tot["CH4_CO2e"] + tot["N2O_CO2e"]
        tot = tot.drop(columns=["CH4_CO2e","N2O_CO2e"])
        tot["Metric"]="Total_CO2e"; prepared.append(tot)

    # LSU: compute from Stocks, with guarded cattle split + grouping
    if not stocks.empty:
        sb = stocks.rename(columns={"Value": "Stocks"}).copy()
        sb["Item"] = sb["Item"].apply(canonical_item)

        if split_cattle:
            # keys where atomic cattle already exists
            atomic_mask = sb["Item"].isin(["Cattle, dairy","Cattle, non-dairy"])
            keys_atomic = set(sb.loc[atomic_mask, ["Area","Year"]].itertuples(index=False, name=None))

            # generic cattle rows
            mask_generic = sb["Item"].str.fullmatch(r"(?i)cattle")
            cattle = sb[mask_generic].copy()
            non_cattle = sb[~mask_generic].copy()

            if not cattle.empty:
                # split only for keys NOT in keys_atomic
                split_mask = cattle.apply(lambda r: (r["Area"], r["Year"]) not in keys_atomic, axis=1)
                to_split = cattle[split_mask].copy()
                keep_generic = cattle[~split_mask].copy()

                if not to_split.empty:
                    dairy = to_split.copy()
                    dairy["Stocks"] *= dairy_frac
                    dairy["Item"] = "Cattle, dairy"
                    dairy["item_kind"] = "atomic"; dairy["is_all"] = False; dairy["is_aggregated"] = False; dairy["is_atomic"] = True

                    other = to_split.copy()
                    other["Stocks"] *= (1.0 - dairy_frac)
                    other["Item"] = "Cattle, non-dairy"
                    other["item_kind"] = "atomic"; other["is_all"] = False; other["is_aggregated"] = False; other["is_atomic"] = True

                    sb = pd.concat([non_cattle, keep_generic, dairy, other], ignore_index=True)
                else:
                    sb = pd.concat([non_cattle, keep_generic], ignore_index=True)

        # Compute LSU and GROUP to remove any duplicates
        sb["LSU_weight"] = sb["Item"].apply(default_lsu_weight)
        sb["Value"] = sb["Stocks"] * sb["LSU_weight"]
        lsu = sb[["Area","Item","Year","Value","item_kind","is_all","is_aggregated","is_atomic"]].copy()
        lsu = lsu.groupby(["Area","Item","Year","item_kind","is_all","is_aggregated","is_atomic"], as_index=False)["Value"].sum()
        lsu["Metric"]="LSU"; prepared.append(lsu)

    if not prepared:
        sys.exit("Nothing to write.")

    out = pd.concat(prepared, ignore_index=True).sort_values(["Area","Item","Year","Metric"]).reset_index(drop=True)

    # Final canonicalization + drop blanks
    out["Item"] = out["Item"].apply(canonical_item)
    out = out[~out["Item"].str.strip().str.lower().isin(EXCLUDE_ITEMS)].copy()

    regs = out["Area"].apply(region_flags).tolist()
    out["region_europe"]  = [t[0] for t in regs]
    out["region_EU"]      = [t[1] for t in regs]
    out["region_EUEEAUK"] = [t[2] for t in regs]

    cols = ["Area","Item","Year","Metric","Value",
            "item_kind","is_all","is_aggregated","is_atomic",
            "region_EU","region_EUEEAUK","region_europe"]
    out[cols].to_csv(outp, index=False)
    print(f"Wrote prepared dataset (v4g) to: {outp}")
    # quick list for QA
    print("Sample LSU cattle items:", sorted(set([x for x in out[out['Metric']=='LSU']['Item'].unique() if 'Cattle' in str(x)])))
if __name__ == "__main__":
    main()
