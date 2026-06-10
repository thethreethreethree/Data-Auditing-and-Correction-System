/*
 * engine.js — Category-relevance auditor, JS port of tools/audit_engine.py.
 *
 * Single rubric, two runtimes: this browser/Node port MUST stay byte-identical in
 * logic to the Python engine, which is validated against the 236-row answer key
 * (99% acc / 98 precision / 98 recall). tools/parity_check.js asserts they agree.
 *
 * Deterministic and reviewable (DACS A11): the rubric is the RULES table, not a model.
 */
(function (root) {
  "use strict";

  const RULES = {
    "atm":               { accept: ["atm","bank"], reject: ["pawn","money transfer","salon","spa"] },
    "bank":              { accept: ["bank","financial institution"], reject: ["pawn","foundation","hub"] },
    "currency exchange": { accept: ["money transfer","currency","foreign exchange","financial institution","remittance"], reject: ["spa","massage","rental"] },
    "pharmacy":          { accept: ["pharmacy","drugstore","drug store"], reject: [] },
    "medical clinic":    { accept: ["medical clinic","medical center","clinic","hospital","dental","dentist","optical","optometr","health consultant","health unit","health center","rural health","urgent care","diagnostic","physician","doctor"],
                           reject: ["pharmacy","drugstore","veterinar","spa","aesthetic","gym","fitness","tattoo","yoga","dive","lodge","hostel","laundry","hotel"] },
    "massage spa":       { accept: ["massage","spa","beauty salon","nail salon","wellness","health club","therapist","retreat","physical therapy"], reject: [] },
    "gym":               { accept: ["gym","fitness","yoga","pilates","climbing","boxing","muay thai","personal trainer","recreation","swimming instructor","martial art"],
                           reject: ["restaurant","housing","playground","hotel","store"] },
    "convenience store": { accept: ["convenience store","grocery","supermarket","general store","mini mart","minimart","sari","market","food products","store"],
                           reject: ["coffee","cafe","café","bakery","deli","ice cream","frozen yogurt","dessert","cake","juice","souvenir","gift","cigar","meat","butcher","wholesal"] },
    "laundry":           { accept: ["laundry","laundromat","dry clean","wash"], reject: ["car wash","lodging"] },
    "scooter rental":    { accept: ["motorcycle rental","scooter rental","motorbike rental","car rental","moto rental","motor rental","rental car","bike rental"],
                           reject: ["tour","vape","travel","hostel","hotel","information"] },
    "luggage storage":   { accept: ["luggage"], reject: [] },
    "gas station":       { accept: ["gas station","gas","fuel","petrol","gasoline"], reject: ["express"] },
    "public wifi":       { accept: ["cafe","café","coffee"], reject: ["hostel","hotel","resort","lodging","inn"] },
    "sim card":          { accept: ["phone","cellphone","cell phone","mobile","telecom","electronics","accessor"], reject: [] },
    "embassy":           { accept: ["embassy","consulate","immigration"], reject: [] },
    "coworking space":   { accept: ["coworking","co-working","shared office"], reject: ["hostel","hotel"] },
    "post office":       { accept: ["post office","postal","courier"], reject: [] },
    "public restroom":   { accept: ["restroom","toilet","comfort room","public toilet"], reject: [] },
    "tourist information": { accept: ["tourist information","visitor center","information center"], reject: [] },
    "transportation":    { accept: ["ferry","port","bus","van","terminal","jeepney","tricycle","transport"], reject: [] },
  };
  const SPECIAL = new Set(["transportation", "tourist information"]);
  const NAME_REJECT = {
    "transportation":      ["private","boat","island tour","rental","expedition","charter"],
    "tourist information": ["travel","tour","agency","hopping","expedition","ecotour","adventure",
                            "river","cave","falls","waterfall","island","islet","beach","rock","lagoon",
                            "sandbar","sand bar","spring","lake","mountain","sanctuary","cove","reef"],
  };
  const DEAD = /permanently closed|not operational|do not visit|closed permanently/i;
  const PLUS = /[A-Z0-9]{4,}\+[A-Z0-9]{2,}/g;

  function amenityOf(row) {
    return String(row["Source Query"] || "").split(" in ")[0].trim().toLowerCase();
  }

  function cleanIndustry(s) {
    if (!s || !s.trim()) return "";
    s = Array.from(s).filter(ch => { const c = ch.codePointAt(0); return !(c >= 0xE000 && c <= 0xF8FF); }).join("");
    s = s.replace(/^[₱P][0-9,\-–—]+/, "");
    s = s.replace(PLUS, "");
    s = s.split(/\s{2,}/)[0];
    s = s.split(/(Open|Closed|Closes|Opens|Permanently)/)[0];
    return s.trim().toLowerCase();
  }

  const has = (s, arr) => arr.some(x => s.includes(x));

  // returns [verdict, reason, realType]
  function classify(row) {
    const amenity = amenityOf(row);
    const ind = cleanIndustry(row["Industry"] || "");
    const title = String(row["Title"] || "").toLowerCase();
    const rule = RULES[amenity];

    if (DEAD.test(String(row["Industry"] || "") + " " + String(row["Title"] || "")))
      return ["INCORRECT", "business not operating", ind];
    if (!rule) return ["REVIEW", `no rule for amenity '${amenity}'`, ind];
    const acc = rule.accept, rej = rule.reject;

    if (SPECIAL.has(amenity)) {
      if (has(title, acc)) return ["CORRECT", `name reads as ${amenity}`, ind];
      if (has(title, NAME_REJECT[amenity] || [])) return ["INCORRECT", `name implies not a real ${amenity}`, ind];
    }
    if (ind) {
      if (has(ind, acc)) return ["CORRECT", `type '${ind}' matches ${amenity}`, ind];
      if (has(ind, rej)) return ["INCORRECT", `type '${ind}' is excluded from ${amenity}`, ind];
      if (has(title, acc)) return ["CORRECT", `type '${ind}', but name reads as ${amenity}`, ind];
      return ["INCORRECT", `type '${ind}' is not a ${amenity}`, ind];
    }
    if (has(title, acc)) return ["CORRECT", `name reads as ${amenity}`, ind];
    if (has(title, rej)) return ["INCORRECT", `name implies not a ${amenity}`, ind];
    return ["REVIEW", "Industry blank — cannot judge", ind];
  }

  // ---- CSV utilities (RFC-4180-ish, handles quotes, commas, newlines) ----
  function parseCSV(text) {
    const rows = [];
    let field = "", row = [], inQ = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (inQ) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else inQ = false; }
        else field += c;
      } else {
        if (c === '"') inQ = true;
        else if (c === ",") { row.push(field); field = ""; }
        else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
        else if (c === "\r") { /* skip */ }
        else field += c;
      }
    }
    if (field !== "" || row.length) { row.push(field); rows.push(row); }
    if (!rows.length) return { header: [], rows: [] };
    const header = rows[0];
    const out = [];
    for (let r = 1; r < rows.length; r++) {
      if (!rows[r].some(c => c.trim() !== "")) continue;       // skip blank rows
      const obj = {};
      header.forEach((h, j) => { obj[h] = rows[r][j] !== undefined ? rows[r][j] : ""; });
      out.push(obj);
    }
    return { header, rows: out };
  }

  function csvCell(v) {
    v = v === undefined || v === null ? "" : String(v);
    return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }
  function toCSV(header, rows) {
    const lines = [header.map(csvCell).join(",")];
    for (const r of rows) lines.push(header.map(h => csvCell(r[h])).join(","));
    return lines.join("\r\n");
  }

  const api = { RULES, SPECIAL, NAME_REJECT, amenityOf, cleanIndustry, classify, parseCSV, toCSV,
                AMENITIES: Object.keys(RULES).sort() };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DACS = api;
})(typeof window !== "undefined" ? window : this);
