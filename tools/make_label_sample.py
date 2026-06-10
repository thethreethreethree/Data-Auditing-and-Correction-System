"""
make_label_sample.py — Build a small, balanced sample for a human to label, so we can
build AND validate a rubric for a taxonomy we don't have one for yet (e.g. hospitality).

Stratified: up to N rows per Source Query category (evenly spaced through each), so every
category is represented without making you label all 864 rows. Verdict is left BLANK on
purpose — your labels must be independent of any engine guess (DACS A3: don't grade your
own homework). Convention matches the Palawan key: blank = correct, a typed reason = wrong.

    python tools/make_label_sample.py [source.csv] [N]
"""
import csv, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_engine import load, amenity_of, clean_industry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\johns\Downloads\siargao_surigao_all_cities (1).csv"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
OUT = os.path.join(ROOT, "data", "hospitality_sample_to_label.csv")


def evenly(items, n):
    if len(items) <= n:
        return items
    step = len(items) / n
    picked, seen = [], set()
    for i in range(n):
        j = int(i * step)
        if j not in seen:
            seen.add(j); picked.append(items[j])
    return picked


def main():
    rows = load(SRC)
    by = defaultdict(list)
    for r in rows:
        by[amenity_of(r)].append(r)

    sample = []
    for cat in sorted(by):
        sample += evenly(by[cat], N)

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Title", "Source Query", "City", "Verdict",
                    "Real Type (reference)", "Google Maps Link (verify)"])
        for r in sample:
            rt = clean_industry(r["Industry"]) or "(blank — judge by name/map)"
            w.writerow([r["Title"], r["Source Query"], r["City"], "", rt, r["Google Maps Link"]])

    print(f"wrote {os.path.relpath(OUT, ROOT)}  —  {len(sample)} rows across {len(by)} categories")
    for cat in sorted(by):
        print(f"   {cat:20} {min(len(by[cat]), N):3} of {len(by[cat])}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
