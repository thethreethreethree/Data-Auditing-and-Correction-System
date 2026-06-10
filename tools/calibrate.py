"""
calibrate.py — Score the auditor against the Palawan answer key (ground truth).

Honest scope: the Palawan rows have NO Industry on disk (the 18-col file was
overwritten by the answer key), so this measures the engine's NAME-based path only
— the same path that must carry blank-Industry accommodation rows in Track B.
Where the name gives no signal the engine ABSTAINS (REVIEW); abstentions are
reported separately, never silently scored as right (DACS §3.5 honesty).
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from audit_engine import classify, COLS

AK = "data/palawan_answer_key.csv"

def main():
    with open(AK, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    tp = fp = tn = fn = abstain = 0   # "positive" = engine flags INCORRECT
    wrong = []
    for r in rows:
        row = {c: "" for c in COLS}
        row["Title"] = r["Title"]; row["Source Query"] = r["Source Query"]; row["City"] = r["City"]
        verdict, why, _ = classify(row)
        v = r["Verdict"].strip().lower()
        truth_incorrect = bool(v) and v != "correct"   # blank OR "correct" = correct; a reason = incorrect

        if verdict == "REVIEW":
            abstain += 1
            continue
        pred_incorrect = (verdict == "INCORRECT")
        if pred_incorrect and truth_incorrect: tp += 1
        elif pred_incorrect and not truth_incorrect:
            fp += 1; wrong.append(("FALSE FLAG ", r["Title"], r["Source Query"].split(" in ")[0], why))
        elif not pred_incorrect and not truth_incorrect: tn += 1
        else:
            fn += 1; wrong.append(("MISSED     ", r["Title"], r["Source Query"].split(" in ")[0], r["Verdict"]))

    decided = tp + fp + tn + fn
    acc = (tp + tn) / decided if decided else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    print(f"NAME-ONLY calibration vs {len(rows)} human labels")
    print(f"  decided: {decided}   abstained (REVIEW): {abstain}  ({100*abstain//len(rows)}%)")
    print(f"  accuracy on decided : {acc:.0%}")
    print(f"  error-detection precision: {prec:.0%}   recall: {rec:.0%}")
    print(f"  confusion  TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"\n  disagreements ({len(wrong)}):")
    for tag, title, cat, note in wrong[:25]:
        print(f"    {tag} {title[:38]:40} [{cat}]  {note[:40]}")

if __name__ == "__main__":
    main()
