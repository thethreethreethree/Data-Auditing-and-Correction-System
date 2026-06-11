"""Merge the agent suspect classifications into the deterministic pass and re-export
the finished wondavu corrected/flagged/report to the Desktop folder."""
import csv, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dacs
from audit_engine import load, COLS

ORIG = r"C:\Users\johns\Favorites\PEN DRAWING STYLE\wondavu-utility-suspects-2026-06-11.csv"
OUT = r"C:\Users\johns\OneDrive\Desktop\Corrected Data"
NAME = "wondavu-utility-suspects-2026-06-11"
AMEN = set(dacs.INDUSTRY_TO_AMENITY.values())
# write re-filed categories back in the file's own label convention (Title Case, file's wording)
LABEL = {"pharmacy": "Pharmacy", "convenience store": "Convenience Store", "bank": "Bank",
         "gas station": "Petrol Station", "medical clinic": "Medical Clinic", "massage spa": "Massage / Spa",
         "scooter rental": "Motorbike / Scooter Rental", "gym": "Gym / Fitness", "atm": "ATM",
         "currency exchange": "Currency Exchange", "laundry": "Laundry", "transportation": "Transportation",
         "sim card": "SIM Card", "coworking space": "Coworking Space"}
lab = lambda t: LABEL.get(t, t)

def _open(path):
    try: return open(path, "w", encoding="utf-8-sig", newline=""), path
    except PermissionError:
        alt = path.replace(".csv", ".new.csv"); return open(alt, "w", encoding="utf-8-sig", newline=""), alt

def main():
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    cls = {}
    for k in range(11):
        p = os.path.join("data", f"sus_out_{k}.csv")
        if os.path.exists(p):
            for r in csv.DictReader(open(p, encoding="utf-8-sig", newline="")):
                try: cls[int(r["idx"])] = r["true_category"].strip().lower()
                except Exception: pass

    rows = load(ORIG)
    corrected, flagged = [], []
    tally = Counter(); src = Counter()
    for i, r in enumerate(rows):
        claim = r["Industry"]; mapped = dacs.INDUSTRY_TO_AMENITY.get(claim.strip().lower())
        d = dacs.decide_industry(r)
        if d["action"] == "keep":
            corrected.append(r); tally["keep"] += 1
        elif d["action"] == "reclassify":
            r["Industry"] = lab(d["target"]); corrected.append(r)
            flagged.append((r["Title"], claim, "re-file", lab(d["target"]), "name match")); tally["reclassify"] += 1; src["deterministic"] += 1
        else:  # suspect -> agent verdict
            tt = cls.get(i, "uncertain"); src["agent"] += 1
            if tt == "non-amenity":
                flagged.append((r["Title"], claim, "remove", "", "agent: not a utility")); tally["remove"] += 1
            elif tt not in AMEN:   # uncertain / unknown -> keep as tagged
                corrected.append(r); flagged.append((r["Title"], claim, "keep (uncertain)", "", "agent: uncertain")); tally["uncertain"] += 1
            elif tt == mapped:
                corrected.append(r); tally["keep"] += 1
            else:
                r["Industry"] = lab(tt); corrected.append(r)
                flagged.append((r["Title"], claim, "re-file", lab(tt), "agent: reads as " + tt)); tally["reclassify"] += 1

    os.makedirs(OUT, exist_ok=True)
    cf, cp = _open(os.path.join(OUT, f"{NAME}_corrected.csv"))
    with cf:
        w = csv.writer(cf); w.writerow(COLS)
        for r in corrected: w.writerow([r[c] for c in COLS])
    ff, fp = _open(os.path.join(OUT, f"{NAME}_flagged.csv"))
    with ff:
        w = csv.writer(ff); w.writerow(["Title", "Claimed", "Action", "Re-filed To", "Reason"])
        for rec in flagged: w.writerow(rec)

    # category mix after correction
    mix = Counter(r["Industry"].strip() for r in corrected)
    rep = [f"DACS finalize — {NAME}", f"rows in: {len(rows)}",
           f"kept {tally['keep']} · re-filed {tally['reclassify']} · removed {tally['remove']} · uncertain-kept {tally['uncertain']}",
           f"  (re-files: {src['deterministic']} deterministic + {tally['reclassify']-src['deterministic']} from agent suspects)",
           f"corrected -> {os.path.basename(cp)} ({len(corrected)} rows)",
           f"flagged   -> {os.path.basename(fp)} ({len(flagged)} rows)", "", "corrected category mix:"]
    for k, v in mix.most_common(): rep.append(f"   {k:18} {v}")
    txt = "\n".join(rep)
    open(os.path.join(OUT, f"{NAME}_report.txt"), "w", encoding="utf-8").write(txt + "\n")
    print(txt); print(f"\nwritten to: {OUT}")

if __name__ == "__main__":
    main()
