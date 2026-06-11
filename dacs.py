"""
dacs.py — DACS local tool (structure-aware auditor / corrector you run from the terminal).

This is the "internal software" version of the system — no browser, no API. It auto-detects
the file shape, runs the deterministic engine for the clear cases, and writes the rows it
CAN'T decide to a *_suspects.csv worklist for the agent (Claude) to classify and fold back in.

Usage:
  python dacs.py <input.csv> [--out FOLDER] [--name NAME]
  python dacs.py apply <input.csv> <classified_suspects.csv> [--out FOLDER] [--name NAME]

Outputs (into --out, default = Desktop\\Corrected Data):
  <name>_corrected.csv   cleaned dataset (keeps + re-files; removed rows dropped)
  <name>_flagged.csv     everything changed or unsure (review/worklist) + reason
  <name>_suspects.csv    rows the deterministic pass couldn't decide -> Claude classifies these
  <name>_report.txt      summary
"""
import argparse, csv, os, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
from audit_engine import load, amenity_of, auto_decision, COLS

DEFAULT_OUT = r"C:\Users\johns\OneDrive\Desktop\Corrected Data"

# ---- "Industry is the category" mode: the Industry label IS the claim to verify ----
INDUSTRY_TO_AMENITY = {
    "pharmacy": "pharmacy", "convenience store": "convenience store", "bank": "bank",
    "petrol station": "gas station", "gas station": "gas station", "medical clinic": "medical clinic",
    "massage / spa": "massage spa", "massage spa": "massage spa", "spa": "massage spa",
    "motorbike / scooter rental": "scooter rental", "scooter rental": "scooter rental",
    "gym / fitness": "gym", "gym": "gym", "atm": "atm", "currency exchange": "currency exchange",
    "laundry": "laundry", "transportation": "transportation", "sim card": "sim card",
    "coworking space": "coworking space",
}
# keywords (incl. Filipino + brands) that CONFIRM a name belongs to a category
CONFIRM = {
    "pharmacy": ["pharmacy","drugstore","drug store","drug","botika","botica","pharma","rx","generika",
                 "mercury drug","watsons","rose pharmacy","southstar","south star","st joseph","apothecary","gamot"],
    "convenience store": ["store","mart","grocery","sari-sari","sari sari","tindahan","minimart","mini mart",
                          "7-eleven","7 eleven","alfamart","ministop","supermarket","market","convenience",
                          "shoppe","general merchandise","trading","merchandise"],
    "bank": ["bank","bdo","bpi","metrobank","landbank","land bank","pnb","rcbc","security bank","unionbank",
             "chinabank","china bank","eastwest","east west","ucpb","psbank","maybank","rural bank","savings bank",
             "cooperative bank","network bank"],
    "gas station": ["petron","shell","caltex","phoenix","seaoil","gas","petrol","fuel","gasoline","flying v",
                    "unioil","total","jetti","filling station"],
    "medical clinic": ["clinic","medical","health center","health unit","hospital","diagnostic","doctor","dental",
                       "dentist","birthing","lying-in","lying in","rhu","infirmary","polyclinic","optical",
                       "eye center","maternity","laboratory","wellness clinic"],
    "massage spa": ["spa","massage","wellness","beauty","salon","nail"],
    "scooter rental": ["rental","motorbike","scooter","bike rental","rent a","motor rental","moto rental"],
    "gym": ["gym","fitness","crossfit"],
    "atm": ["atm"],
    "currency exchange": ["money changer","money exchange","exchange","forex","remittance","foreign exchange","changer"],
    "laundry": ["laundry","laundromat","labada","wash","labalava"],
    "transportation": ["terminal","transport","bus","van","ferry","port","jeepney","tricycle"],
    "sim card": ["sim","globe","smart","dito","telecom","load station","cellphone"],
    "coworking space": ["coworking","co-working","shared office","workspace","co work"],
}


def detect_mode(rows):
    n = max(len(rows), 1)
    sq = sum(1 for r in rows if r["Source Query"].strip()) / n
    return "filed" if sq >= 0.3 else "industry"


def decide_industry(row):
    """Verify the place's name against its Industry-claimed category."""
    claim_raw = row["Industry"].strip().lower()
    cat = INDUSTRY_TO_AMENITY.get(claim_raw)
    name = row["Title"].lower()
    if cat is None:
        return {"action": "suspect", "target": None, "reason": f"unmapped category '{row['Industry']}'"}
    matches = [c for c in CONFIRM if any(kw in name for kw in CONFIRM[c])]
    if cat in matches:
        return {"action": "keep", "target": cat, "reason": f"name confirms {cat}"}
    if len(matches) == 1:
        return {"action": "reclassify", "target": matches[0], "reason": f"name reads as {matches[0]}, not {cat}"}
    return {"action": "suspect", "target": None, "reason": "name gives no clear category signal"}


def _open(path):
    try:
        return open(path, "w", encoding="utf-8-sig", newline=""), path
    except PermissionError:
        alt = path.replace(".csv", ".new.csv")
        return open(alt, "w", encoding="utf-8-sig", newline=""), alt


def run(infile, out, name):
    rows = load(infile)
    mode = detect_mode(rows)
    os.makedirs(out, exist_ok=True)
    tally = Counter()
    corrected, flagged, suspects = [], [], []

    for r in rows:
        if mode == "filed":
            d = auto_decision(r)
            action, target = d["action"], d["target"]
            claim = amenity_of(r); reason = d["reason"]
            if action == "keep" and not d["flagged"]:
                corrected.append(r)
            elif action == "remove":
                flagged.append((r["Title"], claim, "remove", "", reason))
            elif action == "reclassify":
                _set_cat(r, target); corrected.append(r); flagged.append((r["Title"], claim, "re-file", target, reason))
            else:  # keep (flagged/review)
                corrected.append(r); flagged.append((r["Title"], claim, "keep", "", reason))
            tally[action] += 1
        else:  # industry-as-category
            d = decide_industry(r); action = d["action"]; claim = r["Industry"]
            if action == "keep":
                corrected.append(r); tally["keep"] += 1
            elif action == "reclassify":
                r["Industry"] = d["target"]; corrected.append(r)
                flagged.append((r["Title"], claim, "re-file", d["target"], d["reason"])); tally["reclassify"] += 1
            else:  # suspect
                corrected.append(r)  # keep by default; flag for Claude
                flagged.append((r["Title"], claim, "suspect", "", d["reason"]))
                suspects.append(r); tally["suspect"] += 1

    # write files
    cf, cp = _open(os.path.join(out, f"{name}_corrected.csv"))
    with cf:
        w = csv.writer(cf); w.writerow(COLS)
        for r in corrected: w.writerow([r[c] for c in COLS])
    ff, fp = _open(os.path.join(out, f"{name}_flagged.csv"))
    with ff:
        w = csv.writer(ff); w.writerow(["Title", "Claimed", "Action", "Re-filed To", "Reason"])
        for rec in flagged: w.writerow(rec)
    sp = None
    if suspects:
        sf, sp = _open(os.path.join(out, f"{name}_suspects.csv"))
        with sf:
            w = csv.writer(sf); w.writerow(["Title", "Claimed Category", "City", "Address", "Verdict (fill)"])
            for r in suspects: w.writerow([r["Title"], r["Industry"], r["City"], r["Address"], ""])

    report = [f"DACS report — {os.path.basename(infile)}", f"mode: {mode}", f"rows: {len(rows)}",
              "actions: " + ", ".join(f"{k}={v}" for k, v in tally.most_common()),
              f"corrected -> {os.path.basename(cp)} ({len(corrected)} rows)",
              f"flagged   -> {os.path.basename(fp)} ({len(flagged)} rows)"]
    if sp: report.append(f"suspects  -> {os.path.basename(sp)} ({len(suspects)} rows — agent classifies these)")
    rt = "\n".join(report)
    with open(os.path.join(out, f"{name}_report.txt"), "w", encoding="utf-8") as f:
        f.write(rt + "\n")
    print(rt)
    print(f"\nwritten to: {out}")


def _set_cat(r, cat):
    parts = r["Source Query"].split(" in ", 1)
    r["Source Query"] = cat + (" in " + parts[1] if len(parts) > 1 else "")


def main():
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    p = argparse.ArgumentParser(description="DACS local auditor/corrector")
    p.add_argument("infile")
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--name", default=None)
    a = p.parse_args()
    name = a.name or os.path.splitext(os.path.basename(a.infile))[0]
    run(a.infile, a.out, name)


if __name__ == "__main__":
    main()
