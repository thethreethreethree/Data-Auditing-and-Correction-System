"""
hospitality_rescore.py — Does collapsing accommodation subtypes into one "lodging"
bucket fix the accuracy? Re-scores the 123 labels two ways so we can SEE the move.

The 64% loss was dominated by hotel/hostel/guesthouse/B&B/resort confusion — a
distinction the data can't support. Auditing accommodation as "lodging vs not" removes
that unsolvable sub-problem.
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hospitality_rubric import canon, predict_type, LABELED

ACCOM = {"hotels", "hostels", "guesthouses", "bed and breakfast", "resorts"}
LODGING = ["hotel", "hostel", "resort", "villa", "pension", "homestay", "guest house", "guesthouse",
           "bed and breakfast", "b&b", "bed & breakfast", "inn", "lodge", "lodging", "apartment",
           "bungalow", "suite", "dorm", "bunk", "coliving", "co-living", "cabana", "cabin", "casa",
           "house", "homes", " stay", "reddoorz", "nipa hut", "tourist inn"]
NONLODGING = ["restaurant", "resto", "cafe", "café", "coffee", " bar", "pub", "beach", "surf", "falls",
              "cave", "lagoon", "sandbar", "park", "dive", "diving", "scuba", "freediv", "gym", "fitness",
              "spa", "massage", "tour", "market", "grocery", " store", "port", "night club"]

def collapse(c):
    return "lodging" if c in ACCOM else c

def eng_class_subtype(filed, title, ind):
    pred = predict_type(title, ind)
    return ("CORRECT" if pred == filed else ("REVIEW" if pred is None else "INCORRECT"))

def eng_class_collapsed(filed, title, ind):
    hay = (ind + " " + title).lower()
    if filed in ACCOM:
        if any(w in hay for w in LODGING):    return "CORRECT"      # it's lodging, filed as lodging
        if any(w in hay for w in NONLODGING): return "INCORRECT"    # clearly not lodging
        return "CORRECT"                                            # default: trust the accommodation query
    pred = predict_type(title, ind)
    return ("CORRECT" if pred == filed else ("REVIEW" if pred is None else "INCORRECT"))

def you_class(filed, verdict, collapsed):
    yc = canon(verdict)
    if yc == "REVIEW": return "REVIEW"
    if collapsed:
        return "CORRECT" if collapse(yc) == collapse(filed) else "INCORRECT"
    return "CORRECT" if yc == filed else "INCORRECT"

def score(rows, collapsed):
    vcol = [c for c in rows[0] if c.strip().lower() == "verdict"][0]
    qcol = [c for c in rows[0] if "source query" in c.lower()][0]
    rtcol = [c for c in rows[0] if "real type" in c.lower()][0]
    agree = rev = dec_agree = dec_n = 0
    for r in rows:
        filed = r[qcol].split(" in ")[0].strip()
        ind = "" if "blank" in r[rtcol].lower() else r[rtcol]
        yc = you_class(filed, r[vcol], collapsed)
        ec = (eng_class_collapsed if collapsed else eng_class_subtype)(filed, r["Title"], ind)
        if ec == "REVIEW": rev += 1
        if ec == yc: agree += 1
        if yc != "REVIEW":                       # rows where YOU made a definite call
            dec_n += 1
            if ec == yc: dec_agree += 1
    n = len(rows)
    return agree, n, rev, dec_agree, dec_n

def main():
    rows = list(csv.DictReader(open(LABELED, encoding="utf-8-sig", newline="")))
    a1, n, r1, d1, dn1 = score(rows, collapsed=False)
    a2, _, r2, d2, dn2 = score(rows, collapsed=True)
    print(f"BEFORE  police exact subtype       : {a1}/{n} = {100*a1//n}%")
    print(f"AFTER   accommodation = lodging     : {a2}/{n} = {100*a2//n}%")
    print(f"AFTER   + only the rows YOU could decide (drop your 'Review's): {d2}/{dn2} = {100*d2//dn2}%")

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    main()
