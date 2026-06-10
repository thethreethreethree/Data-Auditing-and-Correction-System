"""
hospitality_rubric.py — v1 rubric for the hospitality taxonomy, built BACKWARDS from
the human-labeled sample (data/hospitality_sample_to_label.csv) and scored against it.

Honest scope: accommodation (hotels/hostels/guesthouses/B&B/resorts) is ~90% name-only
(Google gives no Industry), and the labeler themselves marked ~16% "Review" — so this is
inherently fuzzier than the amenity rubric. We measure it rather than claim it.

NOTE: built and tested on the same 123 rows = optimistic (no held-out split yet).
"""
import csv, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_engine import clean_industry

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELED = os.path.join(ROOT, "data", "hospitality_sample_to_label.csv")

# free-form label -> canonical category (for reading the human's verdicts)
CANON = [
    ("bed and breakfast", "bed and breakfast"), ("bed & breakfast", "bed and breakfast"), ("b&b", "bed and breakfast"),
    ("resort", "resorts"), ("hostel", "hostels"),
    ("guest house", "guesthouses"), ("guesthouse", "guesthouses"), ("pension", "guesthouses"),
    ("homestay", "guesthouses"), ("villa", "guesthouses"), ("hotel", "hotels"),
    ("gastropub", "bars"), ("pub", "bars"), ("cocktail", "bars"), ("tapas", "bars"), ("bar", "bars"),
    ("night club", "nightclubs"), ("nightclub", "nightclubs"),
    ("coffee", "cafes"), ("cafe", "cafes"), ("café", "cafes"),
    ("diving", "dive shops"), ("dive", "dive shops"), ("scuba", "dive shops"), ("freediv", "dive shops"),
    ("travel agency", "tours"), ("tour operator", "tours"), ("tour agency", "tours"), ("tour", "tours"),
    ("tourist attraction", "things to do"), ("park", "things to do"), ("beach", "things to do"),
    ("island", "things to do"), ("surf", "things to do"), ("water activity", "things to do"), ("port", "things to do"),
    ("restaurant", "restaurants"), ("resto", "restaurants"), ("diner", "restaurants"),
    ("grill", "restaurants"), ("bbq", "restaurants"), ("eatery", "restaurants"),
    ("spa", "(non-hospitality)"), ("massage", "(non-hospitality)"), ("gym", "(non-hospitality)"),
    ("tourism information", "(non-hospitality)"),
]
def canon(s):
    s = s.strip().lower()
    if s in ("review", "error/flag", "flag", "error", ""):
        return "REVIEW"
    for k, v in CANON:
        if k in s:
            return v
    return "?" + s

# --- the v1 predictor: guess the true type from Industry (if any) + the NAME ---
# checked in order; accommodation type-words beat activity words (a "surf hostel" is a hostel).
PRED = [
    ("resort", "resorts"), ("hostel", "hostels"),
    ("bed and breakfast", "bed and breakfast"), ("bed & breakfast", "bed and breakfast"), ("bed and bunk", "bed and breakfast"),
    ("guest house", "guesthouses"), ("guesthouse", "guesthouses"), ("pension", "guesthouses"),
    ("homestay", "guesthouses"), ("villa", "guesthouses"), ("coliving", "guesthouses"), ("hotel", "hotels"),
    ("diving", "dive shops"), ("dive center", "dive shops"), ("scuba", "dive shops"), ("freediv", "dive shops"),
    ("gastropub", "bars"), ("cocktail", "bars"), ("restobar", "bars"), ("sports bar", "bars"), (" pub", "bars"),
    ("night club", "nightclubs"), ("nightclub", "nightclubs"),
    ("coffee", "cafes"), ("cafe", "cafes"), ("café", "cafes"), ("espresso", "cafes"),
    ("restaurant", "restaurants"), ("diner", "restaurants"), ("grill", "restaurants"),
    ("bbq", "restaurants"), ("barbecue", "restaurants"), ("eatery", "restaurants"), ("seafood", "restaurants"),
    ("travel agency", "tours"), ("tour operator", "tours"), ("tour agency", "tours"), ("island hopping", "tours"),
    ("national park", "things to do"), ("beach", "things to do"), ("surf", "things to do"),
    ("falls", "things to do"), ("cave", "things to do"), ("lagoon", "things to do"), ("sandbar", "things to do"),
    ("bar", "bars"),   # generic, late so "restobar"/"bed and.." don't mis-hit
    ("spa", "(non-hospitality)"), ("massage", "(non-hospitality)"), ("gym", "(non-hospitality)"),
]
def predict_type(title, ind):
    hay = (ind + " " + title).lower()
    for k, v in PRED:
        if k in hay:
            return v
    return None   # no signal -> review

def main():
    rows = list(csv.DictReader(open(LABELED, encoding="utf-8-sig", newline="")))
    vcol = [c for c in rows[0] if c.strip().lower() == "verdict"][0]
    qcol = [c for c in rows[0] if "source query" in c.lower()][0]
    rtcol = [c for c in rows[0] if "real type" in c.lower()][0]

    agree = target_hit = 0
    you_correct = you_mismatch = you_review = 0
    eng_review = 0
    disagreements = []
    for r in rows:
        filed = r[qcol].split(" in ")[0].strip()
        you = canon(r[vcol])                       # ground truth class
        ind = "" if "blank" in r[rtcol].lower() else r[rtcol]
        pred = predict_type(r["Title"], ind)       # engine guess of true type
        eng = "CORRECT" if pred == filed else ("REVIEW" if pred is None else "INCORRECT")

        you_class = "CORRECT" if you == filed else ("REVIEW" if you == "REVIEW" else "INCORRECT")
        you_correct += you_class == "CORRECT"; you_mismatch += you_class == "INCORRECT"; you_review += you_class == "REVIEW"
        eng_review += eng == "REVIEW"

        if eng == you_class:
            agree += 1
            if you_class == "INCORRECT" and pred == you:   # also got the re-file target right
                target_hit += 1
        else:
            disagreements.append((filed, r["Title"][:30], f"you={you}", f"engine={eng}/{pred}"))

    n = len(rows)
    print(f"v1 hospitality rubric vs your {n} labels")
    print(f"  your labels:  correct={you_correct}  mismatch={you_mismatch}  review={you_review}")
    print(f"  3-class agreement: {agree}/{n} = {100*agree//n}%   (engine abstained on {eng_review})")
    print(f"  of your {you_mismatch} mismatches, engine caught+re-filed to the right category: {target_hit}")
    print(f"\n  disagreements ({len(disagreements)}):")
    for d in disagreements[:30]:
        print("   ", " | ".join(d))

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    main()
