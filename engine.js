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

  // ---------- hospitality taxonomy (deterministic; mirrors tools/audit_engine.py) ----------
  const HOSP_LODGING_CATS = new Set(["hotels", "hostels", "guesthouses", "bed and breakfast", "resorts"]);
  const ACCOM_FILED = new Set([...HOSP_LODGING_CATS, "apartments"]);
  const HOSP_CATS = new Set([...ACCOM_FILED, "restaurants", "cafes", "bars", "nightclubs", "nightlife", "tours", "things to do", "dive shops"]);
  const HOSP_SAT = { restaurant: ["restaurants"], cafe: ["cafes"], bar: ["bars", "nightlife"], nightclub: ["nightclubs", "nightlife"],
                     tour: ["tours"], attraction: ["things to do"], "dive shop": ["dive shops"],
                     lodging: ["hotels", "hostels", "guesthouses", "bed and breakfast", "resorts"] };
  const HOSP_TARGET = { restaurant: "restaurants", cafe: "cafes", bar: "bars", nightclub: "nightclubs", tour: "tours",
                        attraction: "things to do", "dive shop": "dive shops", lodging: "lodging",
                        hotels: "hotels", hostels: "hostels", guesthouses: "guesthouses",
                        "bed and breakfast": "bed and breakfast", resorts: "resorts" };
  // name keyword -> accommodation subtype (villa->guesthouses, apartment/homestay->B&B, ...)
  const ACCOM_SUBTYPE = [
    ["resort","resorts"],["hostel","hostels"],["dorm","hostels"],["bunk","hostels"],["coliving","hostels"],
    ["co-living","hostels"],["capsule","hostels"],["backpacker","hostels"],
    ["bed and breakfast","bed and breakfast"],["bed & breakfast","bed and breakfast"],["b&b","bed and breakfast"],
    ["aparthotel","bed and breakfast"],["apartelle","bed and breakfast"],["apartment","bed and breakfast"],
    ["homestay","bed and breakfast"],["home stay","bed and breakfast"],
    ["villa","guesthouses"],["casita","guesthouses"],["guest house","guesthouses"],["guesthouse","guesthouses"],
    ["pension","guesthouses"],["inn","guesthouses"],["lodge","guesthouses"],["hotel","hotels"],["suite","hotels"],
  ];
  const ACCOM_RE = ACCOM_SUBTYPE.map(([kw, sub]) =>
    [new RegExp("\\b" + kw.replace(/[.*+?^${}()|[\]\\&]/g, "\\$&") + (kw === "inn" ? "\\b" : "")), sub]);
  function accomSubtype(name) {
    for (const [rx, sub] of ACCOM_RE) if (rx.test(name)) return sub;
    return null;
  }
  const HOSP_PRED = [
    ["massage","non-hospitality"],["spa","non-hospitality"],["wellness","non-hospitality"],["ice bath","non-hospitality"],
    ["gym","non-hospitality"],["fitness","non-hospitality"],["jiu","non-hospitality"],["tennis","non-hospitality"],
    ["tattoo","non-hospitality"],["piercing","non-hospitality"],["coworking","non-hospitality"],["co-working","non-hospitality"],
    ["car rental","non-hospitality"],["motorbike rental","non-hospitality"],["pharmacy","non-hospitality"],["salon","non-hospitality"],
    ["tourism office","non-hospitality"],["tourism information","non-hospitality"],["tourist information","non-hospitality"],
    ["public market","non-hospitality"],["graphics","non-hospitality"],["multimedia","non-hospitality"],["drone","non-hospitality"],
    ["surf shop","non-hospitality"],["surfshop","non-hospitality"],["boardriders","non-hospitality"],
    ["resort","lodging"],["hostel","lodging"],["bed and breakfast","lodging"],["bed & breakfast","lodging"],["b&b","lodging"],
    ["guest house","lodging"],["guesthouse","lodging"],["pension","lodging"],["homestay","lodging"],["home stay","lodging"],
    ["villa","lodging"],["bungalow","lodging"],["apartelle","lodging"],["apartment","lodging"],["coliving","lodging"],
    ["dorm","lodging"],["capsule","lodging"],["reddoorz","lodging"],["inn","lodging"],["lodge","lodging"],["lodging","lodging"],
    ["suite","lodging"],["rooms","lodging"],["transient","lodging"],["hotel","lodging"],["casa","lodging"],["retreat","lodging"],["camp","lodging"],
    ["diving","dive shop"],["dive center","dive shop"],["scuba","dive shop"],["freediv","dive shop"],
    ["beach","attraction"],["island","attraction"],["lagoon","attraction"],["sandbar","attraction"],["falls","attraction"],
    ["cave","attraction"],["rock formation","attraction"],["viewpoint","attraction"],["park","attraction"],["port","attraction"],
    ["firefly","attraction"],["cove","attraction"],["reef","attraction"],["sanctuary","attraction"],["surf school","attraction"],
    ["surf spot","attraction"],["surfing area","attraction"],["surf academy","attraction"],["kite","attraction"],["hideaway","attraction"],
    ["gastropub","bar"],["restobar","bar"],["beach club","bar"],["cocktail","bar"],["brewery","bar"],
    ["night club","nightclub"],["nightclub","nightclub"],["disco","nightclub"],
    ["coffee","cafe"],["cafe","cafe"],["café","cafe"],["espresso","cafe"],["matcha","cafe"],["bakery","cafe"],["bakeshop","cafe"],
    ["restaurant","restaurant"],["resto","restaurant"],["bistro","restaurant"],["grill","restaurant"],["bbq","restaurant"],
    ["barbecue","restaurant"],["eatery","restaurant"],["diner","restaurant"],["seafood","restaurant"],["kitchen","restaurant"],
    ["panciteria","restaurant"],["pizza","restaurant"],["shawarma","restaurant"],["kebab","restaurant"],["food","restaurant"],
    ["travel and tour","tour"],["tour operator","tour"],["tour agency","tour"],["travel agency","tour"],
    ["boat tour","tour"],["island hopping","tour"],["expedition","tour"],["tours","tour"],
    ["bar","bar"],
  ];
  function predictHospType(title, ind) {
    const hay = (ind + " " + title).toLowerCase();
    for (const [kw, t] of HOSP_PRED) if (hay.includes(kw)) return t;
    return null;
  }
  function classifyHospitality(row) {
    const amenity = amenityOf(row);
    const title = String(row["Title"] || "").toLowerCase();
    const tt = predictHospType(String(row["Title"] || ""), cleanIndustry(row["Industry"] || ""));
    if (ACCOM_FILED.has(amenity)) {                          // accommodation -> assign subtype from name
      if (["restaurant", "cafe", "bar", "nightclub", "attraction", "dive shop", "tour"].includes(tt))
        return ["INCORRECT", `reads as ${tt}, not lodging`, tt];
      if (tt === "non-hospitality") return ["INCORRECT", "not a hospitality place", "non-hospitality"];
      const sub = accomSubtype(title);
      if (sub === null) {
        if (HOSP_LODGING_CATS.has(amenity)) return ["CORRECT", `kept as ${amenity}`, amenity];
        return ["INCORRECT", "apartment -> bed and breakfast", "bed and breakfast"];
      }
      if (sub === amenity) return ["CORRECT", `name reads as ${sub}`, sub];
      return ["INCORRECT", `name reads as ${sub}`, sub];
    }
    if (tt === null) return ["REVIEW", "type unclear from name", ""];
    if (tt === "non-hospitality") return ["INCORRECT", "not a hospitality place", "non-hospitality"];
    if ((HOSP_SAT[tt] || []).includes(amenity)) return ["CORRECT", `reads as ${tt}`, tt];
    return ["INCORRECT", `reads as ${tt}, not ${amenity}`, tt];
  }

  // returns [verdict, reason, realType]
  function classify(row) {
    const amenity = amenityOf(row);
    const ind = cleanIndustry(row["Industry"] || "");
    const title = String(row["Title"] || "").toLowerCase();
    const rule = RULES[amenity];

    if (DEAD.test(String(row["Industry"] || "") + " " + String(row["Title"] || "")))
      return ["INCORRECT", "business not operating", ind];
    if (HOSP_CATS.has(amenity)) return classifyHospitality(row);
    if (!rule) {
      const sub = accomSubtype(title);                      // blank/unknown Source Query: catch accommodation by name
      if (sub) return ["INCORRECT", `name reads as ${sub}`, sub];
      return ["REVIEW", `no rule for amenity '${amenity}'`, ind];
    }
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

  // Run the matrix in reverse: which amenities WOULD accept this real type?
  function reclassifyTargets(real) {
    if (!real) return [];
    const out = [];
    for (const am of Object.keys(RULES)) {
      const r = RULES[am];
      if (r.accept.some((a) => real.includes(a)) && !r.reject.some((x) => real.includes(x))) out.push(am);
    }
    return out;
  }

  // Full-automation policy (no human gate); flags anything uncertain or changed.
  function autoDecision(row) {
    const [verdict, reason, real] = classify(row);
    const cur = amenityOf(row);
    if (verdict === "CORRECT") return { action: "keep", target: cur, verdict, reason, note: "", flagged: false };
    if (verdict === "REVIEW") return { action: "keep", target: cur, verdict, reason, note: "uncertain — kept by default", flagged: true };
    if (HOSP_CATS.has(cur) || HOSP_LODGING_CATS.has(real)) {  // hospitality re-file/remove (incl. blank-SQ accommodation)
      const target = HOSP_TARGET[real];
      if (target && target !== cur) return { action: "reclassify", target, verdict, reason, note: `re-filed ${cur || "(none)"} → ${target}`, flagged: true };
      if (target === cur) return { action: "keep", target: cur, verdict, reason, note: "", flagged: false };
      return { action: "remove", target: null, verdict, reason, note: `not a ${cur || "hospitality"} place — removed`, flagged: true };
    }
    const targets = reclassifyTargets(real).filter((t) => t !== cur);
    if (targets.length === 1) return { action: "reclassify", target: targets[0], verdict, reason, note: `re-filed ${cur} → ${targets[0]}`, flagged: true };
    if (targets.length === 0) return { action: "remove", target: null, verdict, reason, note: "fits no amenity — removed", flagged: true };
    return { action: "reclassify", target: targets[0], verdict, reason, note: `ambiguous [${targets}]; chose ${targets[0]}`, flagged: true };
  }

  const api = { RULES, SPECIAL, NAME_REJECT, amenityOf, cleanIndustry, classify, reclassifyTargets,
                autoDecision, parseCSV, toCSV, AMENITIES: Object.keys(RULES).sort() };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DACS = api;
})(typeof window !== "undefined" ? window : this);
