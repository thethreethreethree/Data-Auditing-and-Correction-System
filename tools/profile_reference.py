"""
profile_reference.py  — Retrospective profiler for the reference audit file.

Purpose: turn qualitative "this looks wrong" claims into COUNTED evidence,
so the error taxonomy that drives the DACS is earned from the record (DACS
Constitution §1.2 retrospective identification), not asserted from impression.

Read-only. Prints a profile; changes nothing. Run:  python tools/profile_reference.py
"""
import csv, re, sys, unicodedata
from collections import Counter

PATH = r"C:\Users\johns\Downloads\Sample File to Audit and correct.csv"

COLS = ["Title","Rating","Reviews","Phone","WhatsApp","Instagram","Facebook",
        "Industry","Address","Website","Image","Amenities","Pitch",
        "Latitude","Longitude","Google Maps Link","Source Query","City"]

PLUS_CODE = re.compile(r"[A-Z0-9]{4,}\+[A-Z0-9]{2,}")          # Google Plus Code, e.g. X3P7+H57
STATUS    = re.compile(r"\b(Open|Closed|Closes|Opens|Permanently closed|Open now|Closes soon|Opens soon)\b", re.I)
PESO      = re.compile(r"[₱]")                              # ₱
PHONE_ONLY= re.compile(r"^[\(\)\d\s\-\+]{6,}$")                 # cell is basically just a phone/number
HOURS     = re.compile(r"\d{1,2}(:\d{2})?\s*(AM|PM)", re.I)

def is_pua(ch):
    cp = ord(ch)
    return (0xE000 <= cp <= 0xF8FF) or (0xF0000 <= cp <= 0xFFFFD) or (0x100000 <= cp <= 0x10FFFD)

def main():
    with open(PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]

    total = len(data)
    nonempty = [r for r in data if any(c.strip() for c in r)]
    empty = total - len(nonempty)

    neg_reviews = comma_reviews = 0
    rev_examples = []
    ind_pluscode = ind_status = ind_peso = ind_pua = 0
    addr_phone_only = addr_short_frag = addr_ok = addr_blank = 0
    phone_no_leadzero = phone_has_space = 0
    pua_rows = 0
    nonascii_rows = 0
    wa_with_zero = 0
    website_is_social = 0
    pitch_nonblank = 0

    for r in nonempty:
        d = dict(zip(COLS, r + [""]*(len(COLS)-len(r))))

        rev = d["Reviews"].strip()
        if rev:
            if rev.lstrip("-").replace(",","").isdigit():
                if rev.startswith("-"): neg_reviews += 1
                if "," in rev: comma_reviews += 1
                if len(rev_examples) < 6: rev_examples.append(rev)

        ind = d["Industry"]
        if ind:
            if PLUS_CODE.search(ind): ind_pluscode += 1
            if STATUS.search(ind):    ind_status   += 1
            if PESO.search(ind):      ind_peso     += 1
            if any(is_pua(c) for c in ind): ind_pua += 1

        addr = d["Address"].strip()
        if not addr: addr_blank += 1
        elif PHONE_ONLY.match(addr) and sum(c.isdigit() for c in addr) >= 7: addr_phone_only += 1
        elif len(addr) <= 6 or re.match(r"^\d+\s+\d+$", addr): addr_short_frag += 1
        else: addr_ok += 1

        ph = d["Phone"].strip()
        if ph:
            digits = re.sub(r"\D","",ph)
            if not ph.startswith("0") and not ph.startswith("(") and digits and digits[0] == "9":
                phone_no_leadzero += 1
            if " " in ph: phone_has_space += 1

        wa = d["WhatsApp"]
        if "wa.me/0" in wa: wa_with_zero += 1

        web, fb, ig = d["Website"], d["Facebook"], d["Instagram"]
        if web and (web == fb or web == ig): website_is_social += 1

        if d["Pitch"].strip(): pitch_nonblank += 1

        joined = "".join(r)
        if any(is_pua(c) for c in joined): pua_rows += 1
        if any(ord(c) > 0x2000 and not is_pua(c) for c in joined): nonascii_rows += 1

    p = print
    p("="*64)
    p(f"FILE: {PATH}")
    p("="*64)
    p(f"Total data rows:            {total}")
    p(f"  Non-empty rows:           {len(nonempty)}")
    p(f"  Fully-empty rows:         {empty}   <- trailing padding to trim")
    p("-"*64)
    p(f"REVIEWS (n={len(nonempty)})")
    p(f"  Negative values:          {neg_reviews}   ({100*neg_reviews//max(len(nonempty),1)}%)")
    p(f"  With thousands-comma:     {comma_reviews}   (quoted, e.g. -1,133)")
    p(f"  examples:                 {rev_examples}")
    p("-"*64)
    p(f"INDUSTRY contamination")
    p(f"  contains Plus Code:       {ind_pluscode}")
    p(f"  contains open/close text: {ind_status}")
    p(f"  contains peso price range:{ind_peso}")
    p(f"  contains UI icon glyph:   {ind_pua}")
    p("-"*64)
    p(f"ADDRESS field")
    p(f"  looks OK (street-ish):    {addr_ok}")
    p(f"  is actually a phone#:     {addr_phone_only}")
    p(f"  short/numeric fragment:   {addr_short_frag}")
    p(f"  blank:                    {addr_blank}")
    p("-"*64)
    p(f"PHONE / WHATSAPP")
    p(f"  Phone missing leading 0:  {phone_no_leadzero}")
    p(f"  wa.me link with bad '0':  {wa_with_zero}")
    p("-"*64)
    p(f"OTHER")
    p(f"  Website == a social URL:  {website_is_social}")
    p(f"  Pitch non-blank:          {pitch_nonblank}   (mostly split review snippets)")
    p(f"  rows w/ UI icon glyph:    {pua_rows}")
    p(f"  rows w/ stray unicode:    {nonascii_rows}")
    p("="*64)

if __name__ == "__main__":
    main()
