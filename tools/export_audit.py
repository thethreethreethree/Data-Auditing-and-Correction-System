"""
export_audit.py — Run the Track A auditor over a scraped file and write a
human-reviewable audit CSV: one row per place, with the verdict, WHY, the real
type, a confidence, and a proposed action (advisory — nothing is applied).

This export is the artifact you spot-check; your corrections to it become the
Industry-path eval set we don't yet have (DACS A2 — measurement first).

Run:  python tools/export_audit.py
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from audit_engine import load, classify, amenity_of

SRC = r"C:\Users\johns\Downloads\siargao_surigao_all_cities_essentials.csv"
OUT = "data/siargao_essentials_audited.csv"

def confidence(verdict, reason):
    if verdict == "REVIEW": return "low"
    return "high" if reason.startswith("type '") else "medium"   # Industry-based vs name-based

def proposed_action(verdict, amenity, real_type):
    if verdict == "CORRECT":
        return f"keep in '{amenity}'"
    if verdict == "REVIEW":
        return "human review — no type signal"
    if real_type:
        return f"drop from '{amenity}'  (true type: {real_type} — reclassify there if wanted)"
    return f"drop from '{amenity}'"

def main():
    rows = load(SRC)
    out_cols = ["Title","City","Filed As","Verdict","Confidence","Real Type","Reason",
                "Proposed Action","Raw Industry","Rating","Reviews","Address","Google Maps Link"]
    from collections import Counter
    tally = Counter(); conf_tally = Counter()
    os.makedirs("data", exist_ok=True)
    out_path = OUT
    try:
        f = open(out_path, "w", encoding="utf-8-sig", newline="")
    except PermissionError:                      # target open in Excel — write a side copy instead
        out_path = OUT.replace(".csv", ".new.csv")
        f = open(out_path, "w", encoding="utf-8-sig", newline="")
        print(f"NOTE: {OUT} is open/locked — wrote {out_path} instead.")
    with f:
        w = csv.writer(f); w.writerow(out_cols)
        for r in rows:
            amenity = amenity_of(r)
            verdict, why, real = classify(r)
            conf = confidence(verdict, why)
            tally[verdict] += 1; conf_tally[(verdict, conf)] += 1
            w.writerow([r["Title"], r["City"], amenity, verdict, conf, real, why,
                        proposed_action(verdict, amenity, real),
                        r["Industry"], r["Rating"], r["Reviews"], r["Address"], r["Google Maps Link"]])
    n = len(rows)
    print(f"wrote {out_path}  ({n} rows)")
    print(f"  CORRECT={tally['CORRECT']}  INCORRECT={tally['INCORRECT']}  REVIEW={tally['REVIEW']}")
    print(f"  high-confidence (Industry-based): {sum(v for (vd,c),v in conf_tally.items() if c=='high')}")
    print(f"  medium (name-based)             : {sum(v for (vd,c),v in conf_tally.items() if c=='medium')}")
    print(f"  low (needs review)              : {sum(v for (vd,c),v in conf_tally.items() if c=='low')}")
    print("\n  sample INCORRECT flags:")
    with open(out_path, encoding="utf-8-sig") as f:
        rd = list(csv.DictReader(f))
    shown = 0
    for row in rd:
        if row["Verdict"] == "INCORRECT" and shown < 8:
            print(f"    {row['Title'][:30]:32} filed='{row['Filed As']}'  -> {row['Proposed Action'][:60]}")
            shown += 1

if __name__ == "__main__":
    main()
