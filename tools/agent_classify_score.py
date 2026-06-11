"""
agent_classify_score.py — Score CLAUDE's own per-row judgments against the human labels.

Point: the classifier doesn't need an external API — the agent reading the data IS the
LLM. These 123 calls were made by Claude from the place name + world knowledge (accommodation
collapsed to "lodging", since subtype isn't in the data). We score them the same way as
everything else: measured, not asserted.
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hospitality_rubric import canon, LABELED

ACCOM = {"hotels", "hostels", "guesthouses", "bed and breakfast", "resorts"}
collapse = lambda c: "lodging" if c in ACCOM else c

# Claude's call per row index (true type; "lodging" = any accommodation; "review" = can't tell)
MY = [
 "things to do","nightclub","bar","bar","bar","bar","review","bar","bar","bar",          # 0-9 bars
 "lodging","lodging","lodging","lodging","lodging","lodging","lodging","lodging","lodging","lodging",  # 10-19 b&b
 "cafe","restaurant","cafe","lodging","restaurant","cafe","cafe","cafe","cafe","cafe",    # 20-29 cafes
 "dive","dive","dive","spa","review","dive","dive","review","dive","things to do",        # 30-39 dive
 "lodging","lodging","things to do","lodging","lodging","lodging","lodging","lodging","lodging","lodging", # 40-49 guesthouses
 "lodging","lodging","lodging","review","lodging","review","review","lodging","lodging","lodging",        # 50-59 hostels
 "lodging","lodging","lodging","review","lodging","lodging","lodging","lodging","lodging","lodging",      # 60-69 hotels
 "review","things to do","cafe",                                                          # 70-72 nightclubs
 "other","things to do","things to do","review","bar","things to do","things to do","review","review","gym", # 73-82 nightlife
 "lodging","lodging","lodging","lodging","lodging","lodging","review","lodging","lodging","lodging",       # 83-92 resorts
 "restaurant","review","restaurant","restaurant","restaurant","restaurant","cafe","restaurant","restaurant","restaurant", # 93-102 restaurants
 "things to do","things to do","things to do","things to do","things to do","things to do","things to do","things to do","things to do","things to do", # 103-112 things to do
 "tour","tour","tour","tour","tourism information","lodging","things to do","review","review","tour",      # 113-122 tours
]
MYCANON = {"things to do":"things to do","nightclub":"nightclubs","bar":"bars","cafe":"cafes",
           "restaurant":"restaurants","dive":"dive shops","tour":"tours","lodging":"lodging"}

def my_class(filed, my):
    if my == "review": return "REVIEW"
    m = MYCANON.get(my, "(non-hospitality)")     # spa/gym/other/tourism-info -> mismatch
    mc = "lodging" if m == "lodging" else collapse(m)
    return "CORRECT" if mc == collapse(filed) else "INCORRECT"

def you_class(filed, verdict):
    yc = canon(verdict)
    if yc == "REVIEW": return "REVIEW"
    return "CORRECT" if collapse(yc) == collapse(filed) else "INCORRECT"

def main():
    rows = list(csv.DictReader(open(LABELED, encoding="utf-8-sig", newline="")))
    v = [c for c in rows[0] if c.strip().lower() == "verdict"][0]
    q = [c for c in rows[0] if "source query" in c.lower()][0]
    assert len(MY) == len(rows), f"{len(MY)} vs {len(rows)}"
    agree = dec_agree = dec_n = 0
    disagree = []
    for i, r in enumerate(rows):
        filed = r[q].split(" in ")[0].strip()
        yc = you_class(filed, r[v]); mc = my_class(filed, MY[i])
        if mc == yc: agree += 1
        else: disagree.append((filed, r["Title"][:34], f"you={yc}", f"claude={mc}({MY[i]})"))
        if yc != "REVIEW":
            dec_n += 1; dec_agree += (mc == yc)
    n = len(rows)
    print(f"CLAUDE-as-classifier vs your {n} labels (accommodation collapsed to lodging)")
    print(f"  overall 3-class agreement : {agree}/{n} = {100*agree//n}%")
    print(f"  on rows YOU could decide  : {dec_agree}/{dec_n} = {100*dec_agree//dec_n}%   <- the real number")
    print(f"\n  the {len(disagree)} disagreements (mostly rows you flagged Review):")
    for d in disagree: print("   ", " | ".join(d))

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    main()
