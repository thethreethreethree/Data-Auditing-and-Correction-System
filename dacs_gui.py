"""
dacs_gui.py — DACS desktop app (Tkinter, no installs needed).

A real window: pick a CSV, watch a live progress bar, and see every row color-coded —
green kept, blue updated/re-filed, red rejected, amber uncertain — with summary cards
and one-click access to the output folder. Processing runs on a worker thread so the UI
stays responsive. Same engine as dacs.py.
"""
import os, sys, threading, queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dacs

BG, PANEL, PANEL2, LINE = "#0f1419", "#171d26", "#1d2531", "#2a3340"
INK, MUT, ACC = "#e6edf3", "#8b97a7", "#4493f8"
OK, UPD, BAD, WARN = "#3fb950", "#58a6ff", "#f85149", "#d29922"
COLOR = {"kept": OK, "updated": UPD, "rejected": BAD, "uncertain": WARN}
LABEL = {"kept": "KEPT", "updated": "UPDATED", "rejected": "REJECTED", "uncertain": "UNCERTAIN"}


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.results = []
        self.files = {}
        self.filt = tk.StringVar(value="changed")
        root.title("DACS — Data Auditing & Correction System")
        root.configure(bg=BG)
        root.geometry("1120x740")
        root.minsize(900, 600)
        self._style()
        self._build()
        self._poll()

    # ---------- styling ----------
    def _style(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("Treeview", background=PANEL, foreground=INK, fieldbackground=PANEL,
                    rowheight=26, borderwidth=0, font=("Segoe UI", 10))
        s.configure("Treeview.Heading", background=PANEL2, foreground=MUT, relief="flat",
                    font=("Segoe UI Semibold", 9))
        s.map("Treeview.Heading", background=[("active", PANEL2)])
        s.map("Treeview", background=[("selected", "#264f78")], foreground=[("selected", INK)])
        s.configure("DACS.Horizontal.TProgressbar", background=ACC, troughcolor=PANEL2, borderwidth=0, thickness=10)

    def _lbl(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", BG), fg=kw.pop("fg", INK), **kw)

    def _btn(self, parent, text, cmd, bg=PANEL2, fg=INK, **kw):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=bg,
                      activeforeground=fg, relief="flat", bd=0, padx=14, pady=7, cursor="hand2",
                      font=("Segoe UI Semibold", 10), **kw)
        return b

    # ---------- layout ----------
    def _build(self):
        head = tk.Frame(self.root, bg=PANEL, height=58); head.pack(fill="x"); head.pack_propagate(False)
        self._lbl(head, "DACS", bg=PANEL, font=("Segoe UI", 17, "bold")).pack(side="left", padx=(20, 10), pady=12)
        self._lbl(head, "Data Auditing & Correction System", bg=PANEL, fg=MUT,
                  font=("Segoe UI", 11)).pack(side="left", pady=16)

        # input controls
        ctl = tk.Frame(self.root, bg=BG); ctl.pack(fill="x", padx=20, pady=(16, 6))
        self._lbl(ctl, "Input file").grid(row=0, column=0, sticky="w", pady=4)
        self.in_var = tk.StringVar()
        e1 = tk.Entry(ctl, textvariable=self.in_var, bg=PANEL2, fg=INK, insertbackground=INK,
                      relief="flat", font=("Segoe UI", 10)); e1.grid(row=0, column=1, sticky="we", padx=8, ipady=5)
        self._btn(ctl, "Browse…", self.browse_in).grid(row=0, column=2)
        self._lbl(ctl, "Output to").grid(row=1, column=0, sticky="w", pady=4)
        self.out_var = tk.StringVar(value=dacs.DEFAULT_OUT)
        e2 = tk.Entry(ctl, textvariable=self.out_var, bg=PANEL2, fg=INK, insertbackground=INK,
                      relief="flat", font=("Segoe UI", 10)); e2.grid(row=1, column=1, sticky="we", padx=8, ipady=5)
        self._btn(ctl, "Browse…", self.browse_out).grid(row=1, column=2)
        self.run_btn = self._btn(ctl, "▶  Run Audit", self.run, bg=ACC, fg="#04101f")
        self.run_btn.grid(row=0, column=3, rowspan=2, padx=(12, 0), ipady=4)
        ctl.columnconfigure(1, weight=1)

        # progress
        pg = tk.Frame(self.root, bg=BG); pg.pack(fill="x", padx=20, pady=(6, 4))
        self.pb = ttk.Progressbar(pg, style="DACS.Horizontal.TProgressbar", mode="determinate")
        self.pb.pack(fill="x", side="left", expand=True)
        self.status = self._lbl(pg, "Choose a CSV and press Run.", fg=MUT, font=("Segoe UI", 9))
        self.status.pack(side="left", padx=12)

        # summary cards
        self.cards = tk.Frame(self.root, bg=BG); self.cards.pack(fill="x", padx=18, pady=8)
        self.card = {}
        for key, txt, col in [("total", "ROWS", INK), ("kept", "KEPT", OK), ("updated", "UPDATED", UPD),
                              ("rejected", "REJECTED", BAD), ("uncertain", "UNCERTAIN", WARN)]:
            f = tk.Frame(self.cards, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
            f.pack(side="left", padx=6, ipadx=14, ipady=8)
            n = self._lbl(f, "—", bg=PANEL, fg=col, font=("Segoe UI", 20, "bold")); n.pack()
            self._lbl(f, txt, bg=PANEL, fg=MUT, font=("Segoe UI", 9)).pack()
            self.card[key] = n

        # filters
        fr = tk.Frame(self.root, bg=BG); fr.pack(fill="x", padx=20, pady=(2, 6))
        for key, txt in [("changed", "Changes"), ("updated", "Updated"), ("rejected", "Rejected"),
                         ("uncertain", "Uncertain"), ("all", "All")]:
            tk.Radiobutton(fr, text=txt, value=key, variable=self.filt, command=self.populate,
                           bg=PANEL2, fg=INK, selectcolor=ACC, indicatoron=False, relief="flat", bd=0,
                           padx=12, pady=5, font=("Segoe UI", 9), activebackground=PANEL2,
                           cursor="hand2").pack(side="left", padx=3)
        self.count_lbl = self._lbl(fr, "", fg=MUT, font=("Segoe UI", 9)); self.count_lbl.pack(side="left", padx=12)

        # table
        wrap = tk.Frame(self.root, bg=LINE); wrap.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        cols = ("title", "tagged", "action", "new", "reason")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for c, txt, w in [("title", "Place", 300), ("tagged", "Tagged as", 150), ("action", "Result", 110),
                          ("new", "Changed to", 150), ("reason", "Why", 320)]:
            self.tree.heading(c, text=txt); self.tree.column(c, width=w, anchor="w")
        for a, col in COLOR.items():
            self.tree.tag_configure(a, foreground=col)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True); vs.pack(side="right", fill="y")

        # status bar
        sb = tk.Frame(self.root, bg=PANEL, height=40); sb.pack(fill="x"); sb.pack_propagate(False)
        self.sb_lbl = self._lbl(sb, "", bg=PANEL, fg=MUT, font=("Segoe UI", 9)); self.sb_lbl.pack(side="left", padx=16)
        self.open_btn = self._btn(sb, "Open output folder", self.open_out, bg=PANEL2)
        self.open_btn.pack(side="right", padx=14, pady=6); self.open_btn.config(state="disabled")

    # ---------- actions ----------
    def browse_in(self):
        p = filedialog.askopenfilename(title="Choose a CSV", filetypes=[("CSV files", "*.csv"), ("All", "*.*")])
        if p: self.in_var.set(p)

    def browse_out(self):
        p = filedialog.askdirectory(title="Output folder")
        if p: self.out_var.set(p)

    def run(self):
        infile = self.in_var.get().strip().strip('"')
        if not infile or not os.path.isfile(infile):
            messagebox.showwarning("DACS", "Pick a valid CSV file first."); return
        out = self.out_var.get().strip() or dacs.DEFAULT_OUT
        name = os.path.splitext(os.path.basename(infile))[0]
        self.run_btn.config(state="disabled"); self.open_btn.config(state="disabled")
        self.tree.delete(*self.tree.get_children())
        for k in self.card: self.card[k].config(text="—")
        self.pb["value"] = 0; self.status.config(text="Loading…", fg=MUT)
        threading.Thread(target=self._worker, args=(infile, out, name), daemon=True).start()

    def _worker(self, infile, out, name):
        try:
            res = dacs.process(infile, out, name, progress=lambda d, t: self.q.put(("progress", d, t)))
            self.q.put(("done", res))
        except Exception as e:
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "progress":
                    d, t = m[1], m[2]; self.pb["maximum"] = t; self.pb["value"] = d
                    self.status.config(text=f"Processing…  {d:,} / {t:,} rows", fg=INK)
                elif m[0] == "done":
                    self._done(m[1])
                elif m[0] == "error":
                    self.status.config(text="Error: " + m[1], fg=BAD)
                    messagebox.showerror("DACS", m[1]); self.run_btn.config(state="normal")
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def _done(self, res):
        self.results = res["results"]; self.files = res["files"]; s = res["summary"]
        self.card["total"].config(text=f"{res['total']:,}")
        for k in ("kept", "updated", "rejected", "uncertain"):
            self.card[k].config(text=f"{s.get(k, 0):,}")
        self.pb["value"] = self.pb["maximum"]
        self.status.config(text=f"Done — {res['mode']} mode.", fg=OK)
        self.populate()
        outdir = os.path.dirname(self.files.get("corrected", ""))
        self.sb_lbl.config(text="Saved to:  " + outdir)
        self.run_btn.config(state="normal"); self.open_btn.config(state="normal")

    def populate(self):
        self.tree.delete(*self.tree.get_children())
        f = self.filt.get()
        keep = {"changed": {"updated", "rejected", "uncertain"}, "all": None}.get(f, {f})
        shown = 0
        for r in self.results:
            if keep is not None and r["action"] not in keep:
                continue
            self.tree.insert("", "end", tags=(r["action"],),
                             values=(r["title"][:70], r["tagged"], LABEL[r["action"]], r["new"], r["reason"]))
            shown += 1
            if shown >= 4000:  # cap UI rows for responsiveness
                break
        self.count_lbl.config(text=f"showing {shown:,} of {len(self.results):,}"
                              + ("  (capped at 4000)" if shown >= 4000 else ""))

    def open_out(self):
        d = os.path.dirname(self.files.get("corrected", "")) or self.out_var.get()
        if os.path.isdir(d):
            try: os.startfile(d)
            except Exception: pass


def main():
    root = tk.Tk()
    app = App(root)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):   # a CSV dragged onto the shortcut
        app.in_var.set(sys.argv[1])
    root.mainloop()


if __name__ == "__main__":
    main()
