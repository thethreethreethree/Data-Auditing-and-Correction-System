# DACS — Data Auditing & Correction System

A browser-based tool that audits scraped Google-Maps place data for **category-relevance
errors** — does each place actually match the amenity it was filed under? — and lets a human
correct them. Drop in a CSV, every row is judged (green = matches, red = mismatch, amber =
needs review) with the reasoning shown, you set the final call per row, and export a
corrected CSV. **Everything runs client-side; no data leaves your machine.**

## Live site

Once GitHub Pages is enabled (Settings → Pages → Deploy from a branch → `main` → `/root`):

**https://thethreethreethree.github.io/Data-Auditing-and-Correction-System/**

Or just open `index.html` locally in any browser.

## How it works

The error class: a scraper queries "X in <place>" and Google returns tangential results — a
pawnshop under "atm", a coffee shop under "convenience store", a river under "tourist
information". Roughly **half** of scraped rows are mislabeled.

The auditor is **deterministic and reviewable** — the rubric is a table (`engine.js` /
`tools/audit_engine.py`), not a model that's "right most of the time." For each row it
compares the place's real type (its cleaned `Industry`) against the queried amenity, with
name-based fallback and name-dominant handling for the two categories where Google's own type
is unreliable (transportation, tourist information).

### Validation

Scored against a 236-row human-labeled answer key (`data/palawan_answer_key.csv`):

```
accuracy 99%  |  error-detection precision 98%  |  recall 98%
```

The browser engine (`engine.js`) is verified byte-identical to the Python engine on real data
(`node tools/parity_check.js` → `CORRECT:243 INCORRECT:114 REVIEW:8`).

## Repo layout

| path | what |
|---|---|
| `index.html`, `app.js`, `engine.js` | the static web app (the deployed site) |
| `tools/audit_engine.py` | the engine + rubric (single source of truth, Python) |
| `tools/calibrate.py` | scores the engine against the answer key |
| `tools/export_audit.py` | batch-audit a file to CSV |
| `tools/parity_check.js` | asserts JS ≡ Python |
| `data/` | answer key + audit outputs |
| `DACS Constitution.md` | the operating discipline this project is built under |

## Local dev / validation

```bash
python tools/calibrate.py        # precision/recall vs the answer key
python tools/audit_engine.py     # CLI audit summary
node   tools/parity_check.js     # JS/Python parity
```
