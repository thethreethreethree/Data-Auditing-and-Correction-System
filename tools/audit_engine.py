"""
audit_engine.py — Category-relevance auditor (Track A, v1).

Decides, per scraped row, whether the place genuinely matches the amenity it was
filed under (Source Query). Deterministic and reviewable: the rubric lives in the
RULES table below, not in a model that's "right most of the time" (DACS A11).

v1 scope = amenity taxonomy (the essentials file). Accommodation (blank-Industry
hospitality) is Track B, not handled here.

Signal: cleaned `Industry` (the place's real Google type) vs the amenity, plus a few
NAME overrides for categories where Industry alone can't separate (transportation,
tourist information) and an operating-status kill rule.

Read-only. Run:  python tools/audit_engine.py
"""
import csv, re, sys, unicodedata

# Windows console is cp1252; some Industry cells carry PUA icon glyphs / ₱ / CJK.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

COLS = ["Title","Rating","Reviews","Phone","WhatsApp","Instagram","Facebook",
        "Industry","Address","Website","Image","Amenities","Pitch",
        "Latitude","Longitude","Google Maps Link","Source Query","City"]

# ---------- robust IO ----------
def load(path):
    """Load a scraped CSV regardless of utf-8 vs cp1252; return list of dict rows."""
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue
    header = rows[0]
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        r = (r + [""] * len(COLS))[:len(COLS)]
        out.append(dict(zip(COLS, r)))
    return out

def amenity_of(row):
    return row["Source Query"].split(" in ")[0].strip().lower()

PLUS = re.compile(r"[A-Z0-9]{4,}\+[A-Z0-9]{2,}")
def clean_industry(s):
    """Strip the scrape contamination down to the real category token."""
    if not s or not s.strip():
        return ""
    s = "".join(ch for ch in s if not (0xE000 <= ord(ch) <= 0xF8FF))   # drop PUA icons
    s = re.sub(r"^[₱P][0-9,\-–—]+", "", s)                          # leading price range
    s = PLUS.sub("", s)
    s = re.split(r"\s{2,}", s)[0]                                       # before double-space blob
    s = re.split(r"(Open|Closed|Closes|Opens|Permanently)", s)[0]
    return s.strip().lower()

DEAD = re.compile(r"permanently closed|not operational|do not visit|closed permanently", re.I)

# ---------- the rubric, as data ----------
# accept/reject are substring tests against the cleaned Industry.
RULES = {
    "atm":               dict(accept=["atm","bank"], reject=["pawn","money transfer","salon","spa"]),
    "bank":              dict(accept=["bank","financial institution"], reject=["pawn","foundation","hub"]),
    "currency exchange": dict(accept=["money transfer","currency","foreign exchange","financial institution","remittance"],
                              reject=["spa","massage","rental"]),
    "pharmacy":          dict(accept=["pharmacy","drugstore","drug store"], reject=[]),
    "medical clinic":    dict(accept=["medical clinic","medical center","clinic","hospital","dental","dentist","optical",
                                      "optometr","health consultant","health unit","health center","rural health",
                                      "urgent care","diagnostic","physician","doctor"],
                              reject=["pharmacy","drugstore","veterinar","spa","aesthetic","gym","fitness","tattoo",
                                      "yoga","dive","lodge","hostel","laundry","hotel"]),
    "massage spa":       dict(accept=["massage","spa","beauty salon","nail salon","wellness","health club",
                                      "therapist","retreat","physical therapy"], reject=[]),
    "gym":               dict(accept=["gym","fitness","yoga","pilates","climbing","boxing","muay thai","personal trainer",
                                      "recreation","swimming instructor","martial art"],
                              reject=["restaurant","housing","playground","hotel","store"]),
    "convenience store": dict(accept=["convenience store","grocery","supermarket","general store","mini mart","minimart",
                                      "sari","market","food products","store"],
                              reject=["coffee","cafe","café","bakery","deli","ice cream","frozen yogurt","dessert",
                                      "cake","juice","souvenir","gift","cigar","meat","butcher","wholesal"]),
    "laundry":           dict(accept=["laundry","laundromat","dry clean","wash"], reject=["car wash","lodging"]),
    "scooter rental":    dict(accept=["motorcycle rental","scooter rental","motorbike rental","car rental","moto rental",
                                      "motor rental","rental car","bike rental"],
                              reject=["tour","vape","travel","hostel","hotel","information"]),
    "luggage storage":   dict(accept=["luggage"], reject=[]),
    "gas station":       dict(accept=["gas station","gas","fuel","petrol","gasoline"], reject=["express"]),
    "public wifi":       dict(accept=["cafe","café","coffee"], reject=["hostel","hotel","resort","lodging","inn"]),
    "sim card":          dict(accept=["phone","cellphone","cell phone","mobile","telecom","electronics","accessor"],
                              reject=[]),
    "embassy":           dict(accept=["embassy","consulate","immigration"], reject=[]),  # immigration office = traveler's embassy-equivalent
    "coworking space":   dict(accept=["coworking","co-working","shared office"], reject=["hostel","hotel"]),
    "post office":       dict(accept=["post office","postal","courier"], reject=[]),
    "public restroom":   dict(accept=["restroom","toilet","comfort room","public toilet"], reject=[]),
    "tourist information": dict(accept=["tourist information","visitor center","information center"], reject=[]),
    "transportation":    dict(accept=["ferry","port","bus","van","terminal","jeepney","tricycle","transport"], reject=[]),
}
# SPECIAL: categories where Google's Industry is unreliable (it tags travel agencies as
# "tourist information center", private boats as "transportation service"), so the place
# NAME decides. Elsewhere Industry leads and NAME only breaks ties / fills blanks.
SPECIAL = {"transportation", "tourist information"}
NAME_REJECT = {
    "transportation":      ["private","boat","island tour","rental","expedition","charter"],
    "tourist information": ["travel","tour","agency","hopping","expedition","ecotour","adventure",
                            # natural features / landmarks are attractions, not info centers
                            "river","cave","falls","waterfall","island","islet","beach","rock","lagoon",
                            "sandbar","sand bar","spring","lake","mountain","sanctuary","cove","reef"],
}

# ---------- hospitality taxonomy (deterministic) ----------
# The browser tool can't call an LLM, so this is the autonomous fallback (~mid-80s% on
# decidable rows; the agent pass is higher). Accommodation subtype isn't in the data, so
# all of hotels/hostels/guesthouses/B&B/resorts collapse to one "lodging" bucket.
HOSP_LODGING_CATS = {"hotels", "hostels", "guesthouses", "bed and breakfast", "resorts"}
HOSP_CATS = HOSP_LODGING_CATS | {"restaurants", "cafes", "bars", "nightclubs", "nightlife", "tours", "things to do", "dive shops"}
HOSP_SAT = {"restaurant": {"restaurants"}, "cafe": {"cafes"}, "bar": {"bars", "nightlife"},
            "nightclub": {"nightclubs", "nightlife"}, "tour": {"tours"}, "attraction": {"things to do"},
            "dive shop": {"dive shops"}, "lodging": set(HOSP_LODGING_CATS)}
HOSP_TARGET = {"restaurant": "restaurants", "cafe": "cafes", "bar": "bars", "nightclub": "nightclubs",
               "tour": "tours", "attraction": "things to do", "dive shop": "dive shops", "lodging": "lodging"}
HOSP_PRED = [  # (substring, true_type) — first match wins; order = most specific first
    ("massage","non-hospitality"),("spa","non-hospitality"),("wellness","non-hospitality"),("ice bath","non-hospitality"),
    ("gym","non-hospitality"),("fitness","non-hospitality"),("jiu","non-hospitality"),("tennis","non-hospitality"),
    ("tattoo","non-hospitality"),("piercing","non-hospitality"),("coworking","non-hospitality"),("co-working","non-hospitality"),
    ("car rental","non-hospitality"),("motorbike rental","non-hospitality"),("pharmacy","non-hospitality"),("salon","non-hospitality"),
    ("tourism office","non-hospitality"),("tourism information","non-hospitality"),("tourist information","non-hospitality"),
    ("public market","non-hospitality"),("graphics","non-hospitality"),("multimedia","non-hospitality"),("drone","non-hospitality"),
    ("surf shop","non-hospitality"),("surfshop","non-hospitality"),("boardriders","non-hospitality"),
    ("resort","lodging"),("hostel","lodging"),("bed and breakfast","lodging"),("bed & breakfast","lodging"),("b&b","lodging"),
    ("guest house","lodging"),("guesthouse","lodging"),("pension","lodging"),("homestay","lodging"),("home stay","lodging"),
    ("villa","lodging"),("bungalow","lodging"),("apartelle","lodging"),("apartment","lodging"),("coliving","lodging"),
    ("dorm","lodging"),("capsule","lodging"),("reddoorz","lodging"),("inn","lodging"),("lodge","lodging"),("lodging","lodging"),
    ("suite","lodging"),("rooms","lodging"),("transient","lodging"),("hotel","lodging"),("casa","lodging"),("retreat","lodging"),("camp","lodging"),
    ("diving","dive shop"),("dive center","dive shop"),("scuba","dive shop"),("freediv","dive shop"),
    ("beach","attraction"),("island","attraction"),("lagoon","attraction"),("sandbar","attraction"),("falls","attraction"),
    ("cave","attraction"),("rock formation","attraction"),("viewpoint","attraction"),("park","attraction"),("port","attraction"),
    ("firefly","attraction"),("cove","attraction"),("reef","attraction"),("sanctuary","attraction"),("surf school","attraction"),
    ("surf spot","attraction"),("surfing area","attraction"),("surf academy","attraction"),("kite","attraction"),("hideaway","attraction"),
    ("gastropub","bar"),("restobar","bar"),("beach club","bar"),("cocktail","bar"),("brewery","bar"),
    ("night club","nightclub"),("nightclub","nightclub"),("disco","nightclub"),
    ("coffee","cafe"),("cafe","cafe"),("café","cafe"),("espresso","cafe"),("matcha","cafe"),("bakery","cafe"),("bakeshop","cafe"),
    ("restaurant","restaurant"),("resto","restaurant"),("bistro","restaurant"),("grill","restaurant"),("bbq","restaurant"),
    ("barbecue","restaurant"),("eatery","restaurant"),("diner","restaurant"),("seafood","restaurant"),("kitchen","restaurant"),
    ("panciteria","restaurant"),("pizza","restaurant"),("shawarma","restaurant"),("kebab","restaurant"),("food","restaurant"),
    ("travel and tour","tour"),("tour operator","tour"),("tour agency","tour"),("travel agency","tour"),
    ("boat tour","tour"),("island hopping","tour"),("expedition","tour"),("tours","tour"),
    ("bar","bar"),  # generic, last
]

def predict_hosp_type(title, ind):
    hay = (ind + " " + title).lower()
    for kw, t in HOSP_PRED:
        if kw in hay:
            return t
    return None

def classify_hospitality(row):
    amenity = amenity_of(row)
    tt = predict_hosp_type(row["Title"], clean_industry(row["Industry"]))
    if tt is None:
        if amenity in HOSP_LODGING_CATS:
            return "CORRECT", "assumed lodging (filed under accommodation)", "lodging"
        return "REVIEW", "type unclear from name", ""
    if tt == "non-hospitality":
        return "INCORRECT", "not a hospitality place", "non-hospitality"
    if amenity in HOSP_SAT.get(tt, set()):
        return "CORRECT", f"reads as {tt}", tt
    return "INCORRECT", f"reads as {tt}, not {amenity}", tt


def classify(row):
    amenity = amenity_of(row)
    ind = clean_industry(row["Industry"])
    title = row["Title"].lower()
    rule = RULES.get(amenity)

    if DEAD.search(row["Industry"] + " " + row["Title"]):
        return "INCORRECT", "business not operating", ind
    if amenity in HOSP_CATS:
        return classify_hospitality(row)
    if rule is None:
        return "REVIEW", f"no rule for amenity '{amenity}'", ind
    acc, rej = rule["accept"], rule["reject"]

    # Primary-function rule: a genuine match term in the NAME wins over everything
    # (Matcharap *Minimart* & Cafe, Tualla *van service*, …/*Motor Rental*/…).
    if amenity in SPECIAL:
        if any(x in title for x in acc):
            return "CORRECT", f"name reads as {amenity}", ind
        if any(x in title for x in NAME_REJECT.get(amenity, [])):
            return "INCORRECT", f"name implies not a real {amenity}", ind
        # name silent -> fall through to Industry below

    if ind:
        if any(x in ind for x in acc):
            return "CORRECT", f"type '{ind}' matches {amenity}", ind
        if any(x in ind for x in rej):
            return "INCORRECT", f"type '{ind}' is excluded from {amenity}", ind
        if any(x in title for x in acc):                       # name rescues an unrelated Industry
            return "CORRECT", f"type '{ind}', but name reads as {amenity}", ind
        return "INCORRECT", f"type '{ind}' is not a {amenity}", ind

    # No Industry captured: judge from the name (primary function wins)
    if any(x in title for x in acc):
        return "CORRECT", f"name reads as {amenity}", ind
    if any(x in title for x in rej):
        return "INCORRECT", f"name implies not a {amenity}", ind
    return "REVIEW", "Industry blank — cannot judge", ind


def reclassify_targets(real_type):
    """Which amenity categories WOULD accept this real type? (the matrix, run in reverse).
    Lets a mismatch be re-filed into its correct bucket instead of just deleted."""
    if not real_type:
        return []
    out = []
    for am, rule in RULES.items():
        if any(a in real_type for a in rule["accept"]) and not any(r in real_type for r in rule["reject"]):
            out.append(am)
    return out


def auto_decision(row):
    """Full-automation policy (no human gate). Everything uncertain or changed is flagged
    so it can be reviewed later, but nothing blocks. Returns a dict."""
    verdict, reason, real = classify(row)
    cur = amenity_of(row)
    if verdict == "CORRECT":
        return {"action": "keep", "target": cur, "verdict": verdict, "reason": reason, "note": "", "flagged": False}
    if verdict == "REVIEW":
        return {"action": "keep", "target": cur, "verdict": verdict, "reason": reason,
                "note": "uncertain — kept by default", "flagged": True}
    if cur in HOSP_CATS:                                  # hospitality re-file/remove
        target = HOSP_TARGET.get(real)                    # real = true_type; None => non-hospitality
        if target and target != cur:
            return {"action": "reclassify", "target": target, "verdict": verdict, "reason": reason,
                    "note": f"re-filed {cur} -> {target}", "flagged": True}
        return {"action": "remove", "target": None, "verdict": verdict, "reason": reason,
                "note": f"not a {cur} — removed", "flagged": True}
    targets = [t for t in reclassify_targets(real) if t != cur]
    if len(targets) == 1:
        return {"action": "reclassify", "target": targets[0], "verdict": verdict, "reason": reason,
                "note": f"re-filed {cur} -> {targets[0]}", "flagged": True}
    if not targets:
        return {"action": "remove", "target": None, "verdict": verdict, "reason": reason,
                "note": "fits no amenity — removed", "flagged": True}
    return {"action": "reclassify", "target": targets[0], "verdict": verdict, "reason": reason,
            "note": f"ambiguous {targets}; chose {targets[0]}", "flagged": True}


def main():
    import os
    from collections import Counter, defaultdict

    # --- ground truth sanity (the bug fix): count the saved answer key correctly ---
    ak = "data/palawan_answer_key.csv"
    if os.path.exists(ak):
        with open(ak, encoding="utf-8", newline="") as f:
            akr = list(csv.DictReader(f))
        # CONVENTION: blank OR literal "correct" = correct (green); a typed reason = incorrect (red)
        gt = Counter("correct" if r["Verdict"].strip().lower() in ("", "correct") else "incorrect" for r in akr)
        print(f"ANSWER KEY {ak}: {len(akr)} rows | correct={gt['correct']} incorrect={gt['incorrect']} "
              f"({100*gt['correct']//len(akr)}% correct)  [blank verdict = correct]")
    print("=" * 70)

    # --- run Track A on the Siargao essentials (real target, has Industry) ---
    path = r"C:\Users\johns\Downloads\siargao_surigao_all_cities_essentials.csv"
    rows = load(path)
    by = defaultdict(Counter)
    samples = defaultdict(list)
    for row in rows:
        v, why, ind = classify(row)
        by[amenity_of(row)][v] += 1
        if v in ("INCORRECT", "REVIEW") and len(samples[amenity_of(row)]) < 3:
            samples[amenity_of(row)].append(f"{row['Title'][:34]:36} [{ind or 'blank'}] -> {why}")

    tot = Counter()
    print(f"SIARGAO ESSENTIALS — {len(rows)} rows, Track A verdicts by amenity")
    print("-" * 70)
    for cat in sorted(by):
        c = by[cat]
        tot.update(c)
        print(f"{cat:20} correct={c['CORRECT']:3} incorrect={c['INCORRECT']:3} review={c['REVIEW']:3}")
        for s in samples[cat]:
            print(f"      · {s}")
    print("-" * 70)
    print(f"TOTAL  correct={tot['CORRECT']}  incorrect={tot['INCORRECT']}  review={tot['REVIEW']}"
          f"   ({100*tot['CORRECT']//max(sum(tot.values()),1)}% pass)")

if __name__ == "__main__":
    main()
