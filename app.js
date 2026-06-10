/* app.js — DACS browser UI. Fully client-side: nothing leaves your machine. */
(function () {
  "use strict";
  const E = window.DACS;
  const $ = (s) => document.querySelector(s);

  let state = { header: [], audited: [], fileName: "" };
  let filter = "all", search = "";

  const LABEL = { CORRECT: "MATCH", INCORRECT: "MISMATCH", REVIEW: "REVIEW" };

  function decode(buf) {
    try { return new TextDecoder("utf-8", { fatal: true }).decode(buf); }
    catch { return new TextDecoder("windows-1252").decode(buf); }   // Palawan files are cp1252
  }
  const confOf = (v, reason) => v === "REVIEW" ? "low" : (reason.startsWith("type '") ? "high" : "medium");
  const defaultDecision = (v) => (v === "INCORRECT" ? "remove" : "keep");

  async function handleFile(file) {
    const text = decode(await file.arrayBuffer());
    const { header, rows } = E.parseCSV(text);
    if (!header.includes("Source Query") || !header.includes("Title")) {
      alert("That CSV has no 'Title'/'Source Query' columns — it doesn't look like a scraped places file.");
      return;
    }
    const audited = rows.map((r, i) => {
      const [verdict, reason, real] = E.classify(r);
      return {
        idx: i, row: r, title: r["Title"] || "", city: r["City"] || "",
        filed_as: E.amenityOf(r), real_type: real || "—", verdict, reason,
        confidence: confOf(verdict, reason), decision: defaultDecision(verdict),
        maps: r["Google Maps Link"] || "",
      };
    });
    state = { header, audited, fileName: file.name };
    filter = "all"; search = "";
    if ($("#search")) $("#search").value = "";
    render();
  }

  function counts() {
    const c = { CORRECT: 0, INCORRECT: 0, REVIEW: 0 };
    state.audited.forEach((a) => c[a.verdict]++);
    return c;
  }

  function visible() {
    return state.audited.filter((a) => {
      if (filter === "CORRECT" && a.verdict !== "CORRECT") return false;
      if (filter === "INCORRECT" && a.verdict !== "INCORRECT") return false;
      if (filter === "REVIEW" && a.verdict !== "REVIEW") return false;
      if (filter === "flagged" && a.verdict === "CORRECT") return false;
      if (search) {
        const hay = (a.title + " " + a.filed_as + " " + a.real_type + " " + a.city).toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });
  }

  function decisionSelect(a) {
    const opts = [
      `<option value="keep" ${a.decision === "keep" ? "selected" : ""}>✓ Keep</option>`,
      `<option value="remove" ${a.decision === "remove" ? "selected" : ""}>✕ Remove</option>`,
    ];
    const re = E.AMENITIES.map((am) =>
      `<option value="reclassify:${am}" ${a.decision === "reclassify:" + am ? "selected" : ""}>→ ${am}</option>`
    ).join("");
    return `<select class="decision" data-idx="${a.idx}">${opts.join("")}<optgroup label="Reclassify as…">${re}</optgroup></select>`;
  }

  function render() {
    const c = counts(), n = state.audited.length;
    $("#summary").innerHTML = n === 0 ? "" : `
      <div class="card"><div class="num">${n}</div><div class="lbl">rows</div></div>
      <div class="card ok"><div class="num">${c.CORRECT}</div><div class="lbl">matches</div></div>
      <div class="card bad"><div class="num">${c.INCORRECT}</div><div class="lbl">mismatches</div></div>
      <div class="card warn"><div class="num">${c.REVIEW}</div><div class="lbl">review</div></div>
      <div class="card"><div class="num">${Math.round(100 * c.CORRECT / Math.max(n, 1))}%</div><div class="lbl">pass</div></div>`;

    $("#toolbar").style.display = n ? "flex" : "none";
    $("#fileBadge").textContent = state.fileName ? `${state.fileName} — ${n} rows` : "";

    document.querySelectorAll(".filter").forEach((b) =>
      b.classList.toggle("active", b.dataset.filter === filter));

    const rows = visible();
    const body = rows.map((a) => `
      <tr class="v-${a.verdict}">
        <td class="t">${esc(a.title)}<div class="sub">${esc(a.city)}</div></td>
        <td>${esc(a.filed_as)}</td>
        <td class="rt">${esc(a.real_type)}</td>
        <td><span class="chip ${a.verdict}">${LABEL[a.verdict]}</span></td>
        <td><span class="conf ${a.confidence}">${a.confidence}</span></td>
        <td class="reason">${esc(a.reason)}${a.maps ? ` · <a href="${esc(a.maps)}" target="_blank" rel="noopener">map</a>` : ""}${a.note ? `<div class="note">→ ${esc(a.note)}</div>` : ""}</td>
        <td>${decisionSelect(a)}</td>
      </tr>`).join("");

    $("#tableWrap").innerHTML = n === 0 ? "" : `
      <table>
        <thead><tr>
          <th>Place</th><th>Filed as</th><th>Real type</th><th>Verdict</th>
          <th>Conf.</th><th>Why</th><th>Decision</th>
        </tr></thead>
        <tbody>${body || `<tr><td colspan="7" class="empty">No rows match this filter.</td></tr>`}</tbody>
      </table>`;

    $("#count").textContent = n ? `showing ${rows.length} of ${n}` : "";
  }

  function exportCorrected() {
    if (!state.audited.length) return;
    const out = [];
    for (const a of state.audited) {
      if (a.decision === "remove") continue;
      const row = Object.assign({}, a.row);
      if (a.decision.startsWith("reclassify:")) {
        const cat = a.decision.split(":")[1];
        const parts = String(row["Source Query"]).split(" in ");
        row["Source Query"] = cat + (parts.length > 1 ? " in " + parts.slice(1).join(" in ") : "");
      }
      out.push(row);
    }
    download(base() + "_corrected.csv", E.toCSV(state.header, out));
  }

  function exportLog() {
    if (!state.audited.length) return;
    const hdr = ["Title", "City", "Filed As", "Verdict", "Reason", "Decision", "Final Category"];
    const rows = state.audited.map((a) => {
      let fc = a.filed_as;
      if (a.decision === "remove") fc = "(removed)";
      else if (a.decision.startsWith("reclassify:")) fc = a.decision.split(":")[1];
      return { Title: a.title, City: a.city, "Filed As": a.filed_as, Verdict: a.verdict,
               Reason: a.reason, Decision: a.decision, "Final Category": fc };
    });
    download(base() + "_audit_log.csv", E.toCSV(hdr, rows));
  }

  function autoCorrect() {
    if (!state.audited.length) return;
    let kept = 0, refiled = 0, removed = 0, flagged = 0;
    for (const a of state.audited) {
      const d = E.autoDecision(a.row);
      a.note = d.note;
      if (d.action === "remove") { a.decision = "remove"; removed++; }
      else if (d.action === "reclassify") { a.decision = "reclassify:" + d.target; refiled++; }
      else { a.decision = "keep"; kept++; }
      if (d.flagged) flagged++;
    }
    const b = $("#banner");
    b.style.display = "block";
    b.innerHTML = `⚡ <b>Auto-corrected.</b> ${kept} kept · ${refiled} re-filed to true category · ${removed} removed`
      + ` · <b>${flagged}</b> flagged for optional review (${Math.round(100 * flagged / state.audited.length)}%).`
      + ` &nbsp;Export below, or hit <b>Flagged&nbsp;⚑</b> to spot-check what changed.`;
    filter = "flagged";
    render();
  }

  const base = () => state.fileName.replace(/\.csv$/i, "") || "audit";
  function download(name, text) {
    const blob = new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }); // BOM for Excel
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ---- wiring ----
  window.addEventListener("DOMContentLoaded", () => {
    $("#file").addEventListener("change", (e) => { if (e.target.files[0]) handleFile(e.target.files[0]); });
    const drop = $("#drop");
    ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); });

    document.querySelectorAll(".filter").forEach((b) =>
      b.addEventListener("click", () => { filter = b.dataset.filter; render(); }));
    $("#search").addEventListener("input", (e) => { search = e.target.value.toLowerCase().trim(); render(); });
    $("#tableWrap").addEventListener("change", (e) => {
      if (e.target.classList.contains("decision")) {
        state.audited[+e.target.dataset.idx].decision = e.target.value;
      }
    });
    $("#autoBtn").addEventListener("click", autoCorrect);
    $("#exportBtn").addEventListener("click", exportCorrected);
    $("#logBtn").addEventListener("click", exportLog);
    $("#acceptAll").addEventListener("click", () => {
      state.audited.forEach((a) => { a.decision = defaultDecision(a.verdict); });
      render();
    });
  });
})();
