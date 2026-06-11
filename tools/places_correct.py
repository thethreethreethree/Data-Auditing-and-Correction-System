"""
places_correct.py — apply the verdict to the wondavu PLACES (hospitality) file and export
one clean corrected file in the standard 18-column format.

Verdict per row (Industry is reliably populated in this file):
  accommodation -> subtype from the NAME (user's rule: villa->guesthouses,
                   apartment/homestay->bed and breakfast, inn/pension/guesthouse->guesthouses,
                   hostel->hostels, resort->resorts, hotel/suite->hotels), else from Industry
  Restaurant    -> keep food subtype if already cafes/bars/restaurants/nightlife, else by name
  Tour          -> keep tours/things to do/dive shops if set, else by name (dive/attraction/tour)
Source Query is rewritten "<category> in <location>" (location preserved); blanks get the bare
category. No rows are dropped.
"""
import csv, os, re, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_engine import load, amenity_of, accom_subtype, ACCOM_FILED, HOSP_LODGING_CATS, COLS

SRC = r"C:\Users\johns\Favorites\PEN DRAWING STYLE\wondavu-classification-places-2026-06-11.csv"
OUT = r"C:\Users\johns\OneDrive\Desktop\Corrected Data"
NAME = "PLACES_REVIEWD+CORRECTED"

ACCOM_IND = {"guesthouse": "guesthouses", "hotel": "hotels", "bed & breakfast": "bed and breakfast",
             "bed and breakfast": "bed and breakfast", "resort": "resorts", "hostel": "hostels",
             "apartment": "bed and breakfast"}
CAFE_KW = ["coffee", "cafe", "café", "bakery", "bakeshop", "patisserie", "gelato", "ice cream",
           "dessert", "milk tea", "milktea", "brunch", "pastr", "cake", "creamery", "tea bar"]
BAR_KW = ["bar", "pub", "brewery", "brew", "cocktail", "lounge", "nightclub", "night club",
          "wine", "videoke", "ktv", "speakeasy"]
DIVE_KW = ["divers", "diving", "dive ", "scuba", "freediv"]
ATTR_KW = ["beach", "sandbar", "cove", "lagoon", "falls", "cave", "island camp", "sanctuary",
           "ancestral", "museum", "reef", "underground river", "subterranean", "macaque",
           "whale shark", "pink island", "viewpoint", "hill"]


def has(t, kws):
    return any(k in t for k in kws)


VILLA_RE = re.compile(r"\b(villa|casita)")                # user rule: villa -> guesthouses
BNB_RE = re.compile(r"\b(apartment|apartelle|aparthotel|homestay|home stay)")  # -> bed and breakfast


def verdict(row):
    name = row["Title"].lower()
    ind = row["Industry"].strip().lower()
    sq = amenity_of(row)                                   # current category from Source Query

    if ind == "restaurant":                               # FOOD (Industry beats a mis-filed category)
        if sq in {"restaurants", "cafes", "bars", "nightclubs", "nightlife"}:
            return sq
        if has(name, CAFE_KW): return "cafes"
        if has(name, BAR_KW): return "bars"
        return "restaurants"
    if ind == "tour":                                     # EXPERIENCES
        if sq in {"tours", "things to do", "dive shops"}:
            return sq
        if has(name, DIVE_KW): return "dive shops"
        if has(name, ATTR_KW): return "things to do"
        return "tours"
    if ind in ACCOM_IND or sq in ACCOM_FILED:             # ACCOMMODATION
        if "resort" in name: return "resorts"             # explicit type word in name wins
        if "hotel" in name: return "hotels"
        if "hostel" in name or "dormitory" in name: return "hostels"
        if VILLA_RE.search(name): return "guesthouses"            # your rule
        if BNB_RE.search(name): return "bed and breakfast"        # your rule
        if sq == "apartments" or ind == "apartment": return "bed and breakfast"  # apartments default
        if sq in HOSP_LODGING_CATS: return sq                     # keep the scrape category (inns, lodges…)
        if ind in ACCOM_IND: return ACCOM_IND[ind]               # map from Industry
        return "guesthouses"
    if VILLA_RE.search(name): return "guesthouses"        # blank / other Industry
    if BNB_RE.search(name): return "bed and breakfast"
    return sq or "things to do"


def new_sq(row, cat):
    orig = row["Source Query"]
    if " in " in orig:
        return cat + " in " + orig.split(" in ", 1)[1]
    return cat


def main():
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    rows = load(SRC)
    os.makedirs(OUT, exist_ok=True)
    changed = 0
    mix = Counter()
    transitions = Counter()
    for r in rows:
        old = amenity_of(r)
        cat = verdict(r)
        if cat != old:
            changed += 1
            transitions[(old or "(blank)", cat)] += 1
        r["Source Query"] = new_sq(r, cat)
        mix[cat] += 1

    path = os.path.join(OUT, f"{NAME}.csv")
    try:
        f = open(path, "w", encoding="utf-8-sig", newline="")
    except PermissionError:
        path = path.replace(".csv", ".new.csv")
        f = open(path, "w", encoding="utf-8-sig", newline="")
    with f:
        w = csv.writer(f); w.writerow(COLS)
        for r in rows:
            w.writerow([r[c] for c in COLS])

    print(f"PLACES corrected — {len(rows)} rows, {changed} re-filed")
    print("\ncorrected category mix:")
    for k, v in mix.most_common():
        print(f"   {k:18} {v}")
    print("\ntop category changes (old -> new):")
    for (o, n), v in transitions.most_common(15):
        print(f"   {v:4}  {o:16} -> {n}")
    print(f"\nwritten to: {path}")


if __name__ == "__main__":
    main()
