"""
hospitality_apply.py — merge Claude's 8 classification batches, validate against the
123 human labels, and write the corrected hospitality dataset.

verdict logic (accommodation collapsed to "lodging"):
  true_type satisfies the filed category -> CORRECT (keep)
  true_type is a different hospitality category -> INCORRECT (re-file there)
  non-hospitality -> remove ; review -> keep + flag
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_engine import load, amenity_of
from hospitality_rubric import canon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r"C:\Users\johns\Downloads\siargao_surigao_all_cities (1).csv"
ACCOM = {"hotels", "hostels", "guesthouses", "bed and breakfast", "resorts"}
collapse = lambda c: "lodging" if c in ACCOM else c

# true_type -> the filed categories it satisfies, and its re-file target
SAT = {"restaurant": {"restaurants"}, "cafe": {"cafes"}, "bar": {"bars", "nightlife"},
       "nightclub": {"nightclubs", "nightlife"}, "tour": {"tours"}, "attraction": {"things to do"},
       "dive shop": {"dive shops"}, "lodging": set(ACCOM), "non-hospitality": set(), "review": set()}
TARGET = {"restaurant": "restaurants", "cafe": "cafes", "bar": "bars", "nightclub": "nightclubs",
          "tour": "tours", "attraction": "things to do", "dive shop": "dive shops", "lodging": "lodging"}

def norm(tt):
    t = tt.strip().lower()
    return {"dive shops": "dive shop", "non hospitality": "non-hospitality",
            "attractions": "attraction", "bars": "bar", "cafes": "cafe", "tours": "tour",
            "restaurants": "restaurant", "nightclubs": "nightclub"}.get(t, t)

def load_classifications():
    cls = {}
    for k in range(8):
        p = os.path.join(ROOT, "data", f"hosp_out_{k}.csv")
        for r in csv.DictReader(open(p, encoding="utf-8-sig", newline="")):
            cls[int(r["idx"])] = norm(r["true_type"])
    return cls

def verdict(filed, tt):
    if tt == "review": return "REVIEW", None
    if filed in SAT.get(tt, set()): return "CORRECT", None
    return "INCORRECT", TARGET.get(tt)        # target None => non-hospitality => remove

def main():
    rows = load(SRC)
    cls = load_classifications()
    missing = [i for i in range(len(rows)) if i not in cls]
    if missing:
        print("WARNING missing classifications for idx:", missing[:20], "..." if len(missing) > 20 else "")

    # --- validate against the 123 labels ---
    lab = list(csv.DictReader(open(os.path.join(ROOT, "data", "hospitality_sample_to_label.csv"),
                                   encoding="utf-8-sig", newline="")))
    vcol = [c for c in lab[0] if c.strip().lower() == "verdict"][0]
    qcol = [c for c in lab[0] if "source query" in c.lower()][0]
    key2idx = {(rows[i]["Title"].strip(), amenity_of(rows[i])): i for i in range(len(rows))}
    agree = dec_a = dec_n = matched = 0
    for r in lab:
        filed = r[qcol].split(" in ")[0].strip()
        i = key2idx.get((r["Title"].strip(), filed))
        if i is None: continue
        matched += 1
        tt = cls.get(i, "review")
        ec = verdict(filed, tt)[0]
        yc = canon(r[vcol]); you = "REVIEW" if yc == "REVIEW" else ("CORRECT" if collapse(yc) == collapse(filed) else "INCORRECT")
        if ec == you: agree += 1
        if you != "REVIEW":
            dec_n += 1; dec_a += (ec == you)
    print(f"VALIDATION vs your labels (matched {matched}/123):")
    print(f"  overall agreement : {agree}/{matched} = {100*agree//max(matched,1)}%")
    print(f"  on rows you could decide: {dec_a}/{dec_n} = {100*dec_a//max(dec_n,1)}%")

    # --- write corrected + flagged ---
    from collections import Counter
    COLS = list(rows[0].keys())
    def op(path):
        try: return open(path, "w", encoding="utf-8-sig", newline=""), path
        except PermissionError:
            alt = path.replace(".csv", ".new.csv"); return open(alt, "w", encoding="utf-8-sig", newline=""), alt
    fc, cor = op(os.path.join(ROOT, "data", "hospitality_corrected.csv"))
    ff, flg = op(os.path.join(ROOT, "data", "hospitality_flagged.csv"))
    tally = Counter()
    with fc, ff:
        wc = csv.writer(fc); wc.writerow(COLS)
        wf = csv.writer(ff); wf.writerow(["Title", "City", "Filed", "True Type", "Verdict", "Action", "Re-filed To"])
        for i, r in enumerate(rows):
            filed = amenity_of(r); tt = cls.get(i, "review")
            v, target = verdict(filed, tt)
            if v == "CORRECT":
                action = "keep"; tally["keep"] += 1
            elif v == "REVIEW":
                action = "keep (flagged)"; tally["review"] += 1
            elif target is None:
                action = "remove"; tally["remove"] += 1
            else:
                action = "re-file"; tally["refile"] += 1
                parts = r["Source Query"].split(" in ", 1)
                r["Source Query"] = target + (" in " + parts[1] if len(parts) > 1 else "")
            if v != "CORRECT":
                wf.writerow([r["Title"], r["City"], filed, tt, v, action, target or ""])
            if action != "remove":
                wc.writerow([r[c] for c in COLS])
    n = len(rows)
    print(f"\n{n} rows -> kept {tally['keep']} · re-filed {tally['refile']} · removed {tally['remove']} · flagged-kept {tally['review']}")
    print(f"  corrected: {os.path.relpath(cor, ROOT)}  ({tally['keep']+tally['refile']+tally['review']} rows)")
    print(f"  flagged  : {os.path.relpath(flg, ROOT)}  ({tally['refile']+tally['remove']+tally['review']} rows)")

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    main()
