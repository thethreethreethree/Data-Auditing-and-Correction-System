// Verify the JS engine reproduces the Python engine's verdicts on real data.
// Python (tools/audit_engine.py) gives CORRECT=243 INCORRECT=114 REVIEW=8 on essentials.
const fs = require("fs");
const path = require("path");
const E = require(path.join(__dirname, "..", "engine.js"));

const FILE = process.argv[2] ||
  "C:/Users/johns/Downloads/siargao_surigao_all_cities_essentials.csv";

const buf = fs.readFileSync(FILE);
let text;
try { text = new TextDecoder("utf-8", { fatal: true }).decode(buf); }
catch { text = new TextDecoder("windows-1252").decode(buf); }

const { rows } = E.parseCSV(text);
const c = { CORRECT: 0, INCORRECT: 0, REVIEW: 0 };
for (const r of rows) c[E.classify(r)[0]]++;
console.log("rows:", rows.length, c);
