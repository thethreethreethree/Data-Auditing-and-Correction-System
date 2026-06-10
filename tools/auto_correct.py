"""
auto_correct.py — Hands-off batch corrector.

Point it at one or more scraped CSVs (or a folder) and it auto-applies the audit:
high-confidence rows are kept/corrected silently, mismatches are re-filed to their
true category or removed, and uncertain rows are kept by default. Nothing blocks —
but every uncertain or changed row is written to a *_flagged.csv so you CAN review
it later (the user's call: accept the measured ~0.5-2% residual, just keep the note).

    python tools/auto_correct.py <file-or-folder> [more ...]
    python tools/auto_correct.py            # demo on the Siargao files in Downloads

Outputs per input file (into data/):
    <name>_corrected.csv   cleaned dataset (keeps + re-filed; removed rows dropped)
    <name>_flagged.csv     every uncertain/changed row + reason + action  (review me)
"""
import csv, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_engine import load, amenity_of, auto_decision, COLS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "data")


def _open(path, **kw):
    try:
        return open(path, "w", **kw), path
    except PermissionError:
        alt = path.replace(".csv", ".new.csv")
        return open(alt, "w", **kw), alt


def set_category(row, newcat):
    parts = row["Source Query"].split(" in ", 1)
    row["Source Query"] = newcat + (" in " + parts[1] if len(parts) > 1 else "")


def process(path):
    rows = load(path)
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(OUTDIR, exist_ok=True)
    fc, cor_path = _open(os.path.join(OUTDIR, base + "_corrected.csv"), encoding="utf-8-sig", newline="")
    ff, flag_path = _open(os.path.join(OUTDIR, base + "_flagged.csv"), encoding="utf-8-sig", newline="")

    tally = Counter()
    with fc, ff:
        wc = csv.writer(fc); wc.writerow(COLS)
        wf = csv.writer(ff); wf.writerow(["Title", "City", "Filed As", "Verdict", "Action",
                                          "Re-filed To", "Reason", "Note"])
        for r in rows:
            cur = amenity_of(r)
            d = auto_decision(r)
            tally[d["action"]] += 1
            if d["flagged"]:
                tally["flagged"] += 1
                wf.writerow([r["Title"], r["City"], cur, d["verdict"], d["action"],
                             d["target"] or "", d["reason"], d["note"]])
            if d["action"] == "remove":
                continue
            if d["action"] == "reclassify":
                set_category(r, d["target"])
            wc.writerow([r[c] for c in COLS])

    n = len(rows)
    kept = tally["keep"]; refiled = tally["reclassify"]; removed = tally["remove"]
    print(f"\n{os.path.basename(path)}  ({n} rows)")
    print(f"  kept {kept}  ·  re-filed {refiled}  ·  removed {removed}")
    print(f"  -> corrected: {os.path.relpath(cor_path, ROOT)}  ({kept + refiled} rows)")
    print(f"  -> flagged for optional review: {os.path.relpath(flag_path, ROOT)}  ({tally['flagged']} rows, "
          f"{round(100*tally['flagged']/max(n,1))}% of file)")
    return tally


def expand(args):
    out = []
    for a in args:
        if os.path.isdir(a):
            out += [os.path.join(a, f) for f in sorted(os.listdir(a)) if f.lower().endswith(".csv")]
        elif os.path.isfile(a):
            out.append(a)
        else:
            print(f"  (skip, not found) {a}")
    return out


def main():
    args = sys.argv[1:]
    if not args:
        dl = os.path.join(os.path.expanduser("~"), "Downloads")
        args = [os.path.join(dl, f) for f in
                ["siargao_surigao_all_cities_essentials.csv", "siargao_surigao_all_cities (1).csv"]]
        print("no path given — running demo on the Siargao files in Downloads")
    files = expand(args)
    if not files:
        print("nothing to process."); return
    total = Counter()
    for f in files:
        total.update(process(f))
    print(f"\n=== {len(files)} file(s): kept {total['keep']} · re-filed {total['reclassify']} · "
          f"removed {total['remove']} · flagged {total['flagged']} ===")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
