import csv
import math
import queue
import re
import subprocess
import threading
import zlib
from collections import Counter, deque
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_TITLE = "Nearby Wi-Fi Scanner Pro"
AUTO_SCAN_MS = 10_000
HISTORY_LEN = 30
FILTERS = ["All", "Saved", "Strong (70%+)", "Open / risky", "2.4 GHz", "5 GHz+"]

THEMES = {
    "dark": dict(
        bg="#0F172A", panel="#1B2638", card="#243349", fg="#E2E8F0", muted="#94A3B8",
        accent="#22C55E", accent_hover="#4ADE80", accent_fg="#04210F", border="#334155",
        sel="#34527A", strong="#4ADE80", medium="#FACC15", weak="#F87171",
        saved="#1E3B34", conn="#1F3F66", grid="#334155",
    ),
    "light": dict(
        bg="#F1F5F9", panel="#FFFFFF", card="#FFFFFF", fg="#0F172A", muted="#64748B",
        accent="#16A34A", accent_hover="#22C55E", accent_fg="#FFFFFF", border="#CBD5E1",
        sel="#BFDBFE", strong="#15803D", medium="#A16207", weak="#B91C1C",
        saved="#DCFCE7", conn="#DBEAFE", grid="#E2E8F0",
    ),
}


# --------------------------------------------------------------------------- netsh helpers
def run_netsh(args):
    result = subprocess.run(
        ["netsh", "wlan", *args],
        capture_output=True, text=True, encoding="mbcs", errors="replace",
        timeout=20, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "netsh command failed.")
    return result.stdout


def parse_saved_profiles(output):
    profiles = []
    for line in output.splitlines():
        m = re.match(r"\s*All User Profile\s*:\s*(.*?)\s*$", line, re.I)
        if m:
            profiles.append(m.group(1))
    return profiles


def get_saved_password(profile_name):
    try:
        output = run_netsh(["show", "profile", f"name={profile_name}", "key=clear"])
    except Exception:
        return None
    for line in output.splitlines():
        m = re.match(r"\s*Key Content\s*:\s*(.*?)\s*$", line, re.I)
        if m:
            return m.group(1) or None
    return None


def get_connected_ssid():
    try:
        out = run_netsh(["show", "interfaces"])
    except Exception:
        return None
    ssid, state = None, ""
    for line in out.splitlines():
        m = re.match(r"\s*(SSID|State)\s*:\s*(.*?)\s*$", line, re.I)
        if m:
            if m.group(1).lower() == "ssid":
                ssid = m.group(2)
            else:
                state = m.group(2).lower()
    return ssid if ssid and state == "connected" else None


def parse_networks(output):
    networks, cur, bss = [], None, None

    def flush_bss():
        nonlocal bss
        if cur is not None and bss is not None:
            ch = bss["channel"]
            if not bss["band"] and ch and ch.isdigit():
                bss["band"] = "2.4 GHz" if int(ch) <= 14 else "5 GHz"
            cur["bss"].append(bss)
        bss = None

    def finish():
        nonlocal cur
        flush_bss()
        if cur:
            best = max(cur["bss"], key=lambda b: -1 if b["signal"] is None else b["signal"], default=None)
            cur["signal"] = best["signal"] if best else None
            cur["channel"] = (best["channel"] if best and best["channel"] else "?")
            cur["band"] = (best["band"] if best and best["band"] else "?")
            cur["bssid_count"] = len(cur["bss"])
            networks.append(cur)
        cur = None

    for raw in output.splitlines():
        line = raw.strip()
        m = re.match(r"SSID\s+\d+\s*:\s*(.*)$", line, re.I)
        if m:
            finish()
            cur = {"ssid": m.group(1).strip() or "(Hidden network)", "security": "Unknown", "bss": []}
            continue
        if cur is None or ":" not in line:
            continue
        key, value = (p.strip() for p in line.split(":", 1))
        key = key.lower()
        if key == "authentication":
            cur["security"] = value or "Unknown"
        elif re.fullmatch(r"bssid\s*\d*", key):
            flush_bss()
            bss = {"signal": None, "channel": None, "band": None}
        elif bss is not None:
            if key == "signal":
                s = re.search(r"(\d+)\s*%", value)
                bss["signal"] = int(s.group(1)) if s else None
            elif key == "channel":
                bss["channel"] = value
            elif key == "band":
                bss["band"] = value
    finish()

    merged = {}
    for n in networks:
        e = merged.get(n["ssid"])
        if e is None:
            merged[n["ssid"]] = n
            continue
        e["bss"] += n["bss"]
        e["bssid_count"] += n["bssid_count"]
        if (n["signal"] or -1) > (e["signal"] or -1):
            e.update(signal=n["signal"], channel=n["channel"], band=n["band"])
    return list(merged.values())


# --------------------------------------------------------------------------- small utils
def signal_bars(sig):
    if sig is None:
        return "▱▱▱▱"
    n = 4 if sig >= 75 else 3 if sig >= 50 else 2 if sig >= 25 else 1
    return "▰" * n + "▱" * (4 - n)


def is_risky(security):
    s = security.lower()
    return "open" in s or "wep" in s


def mix(c1, c2, a):
    p1 = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    p2 = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x * a + y * (1 - a)) for x, y in zip(p1, p2))


# --------------------------------------------------------------------------- app
class WifiScannerApp:
    COLS = ("ssid", "bars", "signal", "security", "band", "channel", "aps", "saved", "password")
    HEAD = {"ssid": "Wi-Fi Name", "bars": "Strength", "signal": "Signal", "security": "Security",
            "band": "Band", "channel": "Ch", "aps": "APs", "saved": "Saved", "password": "Password"}
    WIDTH = {"ssid": 210, "bars": 80, "signal": 65, "security": 150, "band": 75,
             "channel": 55, "aps": 50, "saved": 65, "password": 150}

    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(1360, int(sw * 0.94)), min(780, int(sh * 0.86))
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 24)}")
        root.minsize(980, 540)

        self.theme_name = "dark"
        self.t = THEMES["dark"]
        self.q = queue.Queue()
        self.networks, self.saved, self.passwords = [], {}, {}
        self.connected = None
        self.history = {}
        self.sort_col, self.sort_rev = "signal", True
        self.scan_busy, self.auto_job = False, None
        self.radar_angle = 0
        self.revealed = set()
        self.pw_var = tk.StringVar()

        self.var_auto = tk.BooleanVar(value=False)
        self.var_reveal = tk.BooleanVar(value=False)
        self.var_search = tk.StringVar()
        self.var_filter = tk.StringVar(value="All")
        self.var_search.trace_add("write", lambda *_: self.render())

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.build_ui()
        self.apply_theme()

        root.bind("<F5>", lambda _e: self.start_scan())
        root.bind("<Control-f>", lambda _e: self.ent_search.focus_set())
        root.after(100, self.poll_queue)
        root.after(60, self.animate_radar)
        root.after(300, self.start_scan)

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        outer = ttk.Frame(self.root, padding=(14, 10))
        outer.pack(fill="both", expand=True)

        head = ttk.Frame(outer)
        head.pack(fill="x")
        left = ttk.Frame(head)
        left.pack(side="left")
        ttk.Label(left, text="Wi-Fi Scanner Pro", style="Title.TLabel").pack(anchor="w")
        self.lbl_conn = ttk.Label(left, text="Not connected", style="Muted.TLabel")
        self.lbl_conn.pack(anchor="w")
        self.btn_scan = ttk.Button(head, text="⟳  Scan now (F5)", style="Accent.TButton", command=self.start_scan)
        self.btn_scan.pack(side="right")
        self.btn_theme = ttk.Button(head, text="☀ Light", command=self.toggle_theme)
        self.btn_theme.pack(side="right", padx=8)
        ttk.Checkbutton(head, text="Auto-scan (10s)", variable=self.var_auto,
                        command=self.toggle_auto).pack(side="right", padx=12)

        cards = ttk.Frame(outer)
        cards.pack(fill="x", pady=(10, 8))
        self.card_vals = {}
        for i, (key, title) in enumerate([("total", "Networks found"), ("strong", "Strong signal (70%+)"),
                                          ("saved", "Saved & in range"), ("risky", "Open / WEP (risky)")]):
            f = ttk.Frame(cards, style="Card.TFrame", padding=(14, 6))
            f.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            cards.columnconfigure(i, weight=1)
            ttk.Label(f, text=title, style="Card.TLabel").pack(anchor="w")
            v = ttk.Label(f, text="—", style="CardValue.TLabel")
            v.pack(anchor="w")
            self.card_vals[key] = v

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Search").pack(side="left")
        self.ent_search = ttk.Entry(bar, textvariable=self.var_search, width=26)
        self.ent_search.pack(side="left", padx=6)
        cb = ttk.Combobox(bar, textvariable=self.var_filter, state="readonly", width=16, values=FILTERS)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.render())
        ttk.Checkbutton(bar, text="Show all passwords", variable=self.var_reveal,
                        command=self.on_toggle_all).pack(side="left", padx=14)
        ttk.Button(bar, text="⬇ Export CSV", command=self.export_csv).pack(side="right")

        # footer is packed BEFORE the main area so it can never be cut off
        foot = ttk.Frame(outer)
        foot.pack(side="bottom", fill="x", pady=(6, 0))
        self.lbl_status = ttk.Label(foot, text="Ready", style="Muted.TLabel")
        self.lbl_status.pack(side="left")
        ttk.Label(foot, text="🔒 Passwords are hidden by default • CSV export never includes passwords",
                  style="Muted.TLabel").pack(side="right")

        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True)

        tf = ttk.Frame(main)
        tf.pack(side="left", fill="both", expand=True)
        self.table = ttk.Treeview(tf, columns=self.COLS, show="headings", selectmode="browse")
        for c in self.COLS:
            self.table.heading(c, text=self.HEAD[c], command=lambda col=c: self.sort_by(col))
            self.table.column(c, width=self.WIDTH[c], minwidth=45,
                              anchor="w" if c in ("ssid", "security", "password") else "center")
        ys = ttk.Scrollbar(tf, orient="vertical", command=self.table.yview)
        xs = ttk.Scrollbar(tf, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        self.table.bind("<<TreeviewSelect>>", self.on_select)
        self.table.bind("<Button-3>", self.on_right_click)
        self.table.bind("<ButtonRelease-1>", self.on_table_click)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Copy Wi-Fi name", command=self.copy_ssid)
        self.menu.add_command(label="Copy saved password", command=self.copy_password)
        self.menu.add_command(label="Show / hide password", command=self.toggle_selected_pw)
        self.menu.add_separator()
        self.menu.add_command(label="Connect (saved profile)", command=self.connect_selected)

        right = ttk.Frame(main, style="Panel.TFrame", padding=8)
        right.pack(side="right", fill="y", padx=(10, 0))

        # details pinned to the bottom of the right panel
        det = ttk.Frame(right, style="Panel.TFrame")
        det.pack(side="bottom", fill="x", pady=(8, 0))
        self.lbl_detail = ttk.Label(det, text="Select a network to see details.", style="Panel.TLabel",
                                    wraplength=350, justify="left")
        self.lbl_detail.pack(fill="x")
        pr = ttk.Frame(det, style="Panel.TFrame")
        pr.pack(fill="x", pady=(8, 6))
        ttk.Label(pr, text="Password", style="PanelMuted.TLabel").pack(side="left")
        self.btn_eye = ttk.Button(pr, text="👁 Show", width=9, command=self.toggle_selected_pw, state="disabled")
        self.btn_eye.pack(side="right")
        self.ent_pw = ttk.Entry(pr, textvariable=self.pw_var, state="readonly", show="•")
        self.ent_pw.pack(side="left", fill="x", expand=True, padx=8)
        btns = ttk.Frame(det, style="Panel.TFrame")
        btns.pack(fill="x")
        ttk.Button(btns, text="Copy name", command=self.copy_ssid).pack(side="left")
        ttk.Button(btns, text="Copy password", command=self.copy_password).pack(side="left", padx=6)
        ttk.Button(btns, text="Connect", command=self.connect_selected).pack(side="left")

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        self.radar = tk.Canvas(self.nb, width=360, height=220, highlightthickness=0, bg="#061510")
        self.hist = tk.Canvas(self.nb, width=360, height=220, highlightthickness=0)
        self.chan = tk.Canvas(self.nb, width=360, height=220, highlightthickness=0)
        self.nb.add(self.radar, text="Radar")
        self.nb.add(self.hist, text="Signal history")
        self.nb.add(self.chan, text="Channels")
        self.hist.bind("<Configure>", lambda _e: self.draw_history())
        self.chan.bind("<Configure>", lambda _e: self.draw_channels())
        self.nb.bind("<<NotebookTabChanged>>", lambda _e: self.draw_all_charts())

    def apply_theme(self):
        t, s = self.t, self.style
        self.root.configure(bg=t["bg"])
        s.configure(".", background=t["bg"], foreground=t["fg"], font=("Segoe UI", 10))
        s.configure("TFrame", background=t["bg"])
        s.configure("Panel.TFrame", background=t["panel"])
        s.configure("Card.TFrame", background=t["card"], relief="flat")
        s.configure("TLabel", background=t["bg"], foreground=t["fg"])
        s.configure("Panel.TLabel", background=t["panel"], foreground=t["fg"])
        s.configure("Muted.TLabel", background=t["bg"], foreground=t["muted"], font=("Segoe UI", 9))
        s.configure("Card.TLabel", background=t["card"], foreground=t["muted"], font=("Segoe UI", 9))
        s.configure("CardValue.TLabel", background=t["card"], foreground=t["fg"], font=("Segoe UI", 18, "bold"))
        s.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        s.configure("TButton", background=t["card"], foreground=t["fg"], bordercolor=t["border"],
                    padding=(10, 6), focuscolor=t["card"])
        s.map("TButton", background=[("active", t["border"])])
        s.configure("Accent.TButton", background=t["accent"], foreground=t["accent_fg"],
                    font=("Segoe UI", 10, "bold"), padding=(16, 8), borderwidth=0)
        s.map("Accent.TButton", background=[("disabled", t["border"]), ("active", t["accent_hover"])])
        s.configure("PanelMuted.TLabel", background=t["panel"], foreground=t["muted"], font=("Segoe UI", 9))
        s.configure("TCheckbutton", background=t["bg"], foreground=t["fg"], indicatorbackground=t["panel"],
                    indicatorforeground=t["accent_fg"], bordercolor=t["border"])
        s.map("TCheckbutton", background=[("active", t["bg"])],
              indicatorbackground=[("selected", t["accent"]), ("!selected", t["panel"])],
              indicatorforeground=[("selected", t["accent_fg"])])
        s.configure("TEntry", fieldbackground=t["panel"], foreground=t["fg"], insertcolor=t["fg"],
                    bordercolor=t["border"], lightcolor=t["panel"], darkcolor=t["panel"])
        s.map("TEntry", fieldbackground=[("readonly", t["card"]), ("!disabled", t["panel"])],
              foreground=[("readonly", t["fg"])])
        s.configure("TCombobox", fieldbackground=t["panel"], background=t["card"], foreground=t["fg"],
                    arrowcolor=t["fg"], bordercolor=t["border"], selectbackground=t["panel"],
                    selectforeground=t["fg"], lightcolor=t["panel"], darkcolor=t["panel"])
        s.map("TCombobox", fieldbackground=[("readonly", t["panel"])], foreground=[("readonly", t["fg"])],
              selectbackground=[("readonly", t["panel"])], selectforeground=[("readonly", t["fg"])],
              background=[("active", t["border"])])
        self.root.option_add("*TCombobox*Listbox.background", t["panel"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["fg"])
        s.configure("Treeview", background=t["panel"], fieldbackground=t["panel"], foreground=t["fg"],
                    rowheight=28, borderwidth=0, font=("Segoe UI", 10),
                    bordercolor=t["panel"], lightcolor=t["panel"], darkcolor=t["panel"])
        s.map("Treeview", background=[("selected", t["sel"])], foreground=[("selected", t["fg"])])
        s.configure("Treeview.Heading", background=t["card"], foreground=t["fg"], relief="flat",
                    font=("Segoe UI", 9, "bold"), padding=(4, 6))
        s.map("Treeview.Heading", background=[("active", t["border"])])
        s.configure("TNotebook", background=t["panel"], borderwidth=0)
        s.configure("TNotebook.Tab", background=t["bg"], foreground=t["muted"], padding=(14, 6))
        s.map("TNotebook.Tab", background=[("selected", t["card"])], foreground=[("selected", t["fg"])])
        s.configure("TScrollbar", background=t["card"], troughcolor=t["panel"], arrowcolor=t["fg"],
                    bordercolor=t["panel"])

        for tag, key in (("strong", "strong"), ("medium", "medium"), ("weak", "weak")):
            self.table.tag_configure(tag, foreground=t[key])
        self.table.tag_configure("even", background=t["panel"])
        self.table.tag_configure("odd", background=t["card"])
        self.table.tag_configure("saved", background=t["saved"])
        self.table.tag_configure("connected", background=t["conn"])
        self.hist.configure(bg=t["panel"])
        self.chan.configure(bg=t["panel"])
        self.update_headings()

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.t = THEMES[self.theme_name]
        self.btn_theme.configure(text="🌙 Dark" if self.theme_name == "light" else "☀ Light")
        self.apply_theme()
        self.render()
        self.draw_all_charts()

    def set_status(self, text):
        self.lbl_status.configure(text=text)

    # ------------------------------------------------------------------ scanning
    def start_scan(self):
        if self.scan_busy:
            return
        self.scan_busy = True
        self.btn_scan.configure(state="disabled", text="Scanning…")
        self.set_status("Scanning nearby networks…")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            nets = parse_networks(run_netsh(["show", "networks", "mode=bssid"]))
            profiles = parse_saved_profiles(run_netsh(["show", "profiles"]))
            saved = {p.casefold(): p for p in profiles}
            nearby = {n["ssid"].casefold() for n in nets}
            passwords = {k: get_saved_password(p) for k, p in saved.items() if k in nearby}
            self.q.put(("ok", nets, saved, passwords, get_connected_ssid()))
        except subprocess.TimeoutExpired:
            self.q.put(("err", "Scan timed out. Try again."))
        except Exception as exc:
            self.q.put(("err", f"{exc}\n\nCheck that the Wi-Fi adapter is on and the WLAN service is running."))

    def poll_queue(self):
        try:
            while True:
                self.handle_result(self.q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.poll_queue)

    def handle_result(self, msg):
        self.scan_busy = False
        self.btn_scan.configure(state="normal", text="⟳  Scan now (F5)")
        if msg[0] == "err":
            self.set_status("Scan failed.")
            if not self.var_auto.get():
                messagebox.showerror("Wi-Fi scan failed", msg[1])
        else:
            _, nets, saved, pw, conn = msg
            prev = {n["ssid"] for n in self.networks}
            self.networks, self.saved, self.passwords, self.connected = nets, saved, pw, conn
            names = {n["ssid"] for n in nets}
            for n in nets:
                self.history.setdefault(n["ssid"], deque(maxlen=HISTORY_LEN)).append(n["signal"])
            for ssid, dq in self.history.items():
                if ssid not in names:
                    dq.append(None)
            new_saved = [n["ssid"] for n in nets if prev and n["ssid"] not in prev
                         and n["ssid"].casefold() in saved]
            text = f"Last scan {datetime.now():%H:%M:%S}  •  {len(nets)} networks"
            if conn:
                text += f"  •  Connected: {conn}"
            if new_saved:
                text += f"  •  🔔 Saved network in range: {', '.join(new_saved)}"
            if not nets:
                text = "No networks detected. Check that Wi-Fi is enabled."
            self.set_status(text)
            self.lbl_conn.configure(text=f"● Connected: {conn}" if conn else "Not connected")
            self.update_cards()
            self.render()
            self.refresh_pw_row()
            self.draw_all_charts()
        if self.var_auto.get():
            self.schedule_auto()

    def toggle_auto(self):
        if self.auto_job:
            self.root.after_cancel(self.auto_job)
            self.auto_job = None
        if self.var_auto.get() and not self.scan_busy:
            self.schedule_auto()

    def schedule_auto(self):
        if self.auto_job:
            self.root.after_cancel(self.auto_job)
        self.auto_job = self.root.after(AUTO_SCAN_MS, self._auto_fire)

    def _auto_fire(self):
        self.auto_job = None
        if self.var_auto.get():
            self.start_scan()

    # ------------------------------------------------------------------ table
    def update_cards(self):
        n = self.networks
        self.card_vals["total"].configure(text=str(len(n)))
        self.card_vals["strong"].configure(text=str(sum(1 for x in n if (x["signal"] or 0) >= 70)))
        self.card_vals["saved"].configure(text=str(sum(1 for x in n if x["ssid"].casefold() in self.saved)))
        self.card_vals["risky"].configure(text=str(sum(1 for x in n if is_risky(x["security"]))))

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, col in ("signal", "bars", "aps")
        self.update_headings()
        self.render()

    def update_headings(self):
        for c in self.COLS:
            arrow = (" ▼" if self.sort_rev else " ▲") if c == self.sort_col else ""
            self.table.heading(c, text=self.HEAD[c] + arrow)

    def sort_key(self, n):
        c = self.sort_col
        key = n["ssid"].casefold()
        if c in ("signal", "bars"):
            return -1 if n["signal"] is None else n["signal"]
        if c == "ssid":
            return n["ssid"].lower()
        if c == "security":
            return n["security"]
        if c == "band":
            return n["band"]
        if c == "channel":
            return int(n["channel"]) if str(n["channel"]).isdigit() else 0
        if c == "aps":
            return n["bssid_count"]
        if c == "saved":
            return key in self.saved
        return bool(self.passwords.get(key))

    def filtered(self):
        q = self.var_search.get().strip().lower()
        f = self.var_filter.get()
        out = []
        for n in self.networks:
            if q and q not in n["ssid"].lower():
                continue
            if f == "Saved" and n["ssid"].casefold() not in self.saved:
                continue
            if f == "Strong (70%+)" and (n["signal"] or 0) < 70:
                continue
            if f == "Open / risky" and not is_risky(n["security"]):
                continue
            if f == "2.4 GHz" and not n["band"].startswith("2.4"):
                continue
            if f == "5 GHz+" and (n["band"].startswith("2.4") or n["band"] == "?"):
                continue
            out.append(n)
        return sorted(out, key=self.sort_key, reverse=self.sort_rev)

    def render(self):
        prev = self.table.selection()
        self.table.delete(*self.table.get_children())
        all_shown = self.var_reveal.get()
        for i, n in enumerate(self.filtered()):
            key = n["ssid"].casefold()
            sig = n["signal"]
            pw = self.passwords.get(key)
            if pw:
                pw_text = f"{pw}  🙈" if (all_shown or n["ssid"] in self.revealed) else "••••••••  👁"
            else:
                pw_text = "Not found"
            is_conn = n["ssid"] == self.connected
            bg = "connected" if is_conn else "saved" if key in self.saved else ("odd" if i % 2 else "even")
            tags = ("medium" if sig is None else "strong" if sig >= 70 else "medium" if sig >= 40 else "weak", bg)
            sec = ("⚠ " if is_risky(n["security"]) else "") + n["security"]
            self.table.insert("", "end", iid=n["ssid"], tags=tags, values=(
                ("● " if is_conn else "") + n["ssid"], signal_bars(sig),
                f"{sig}%" if sig is not None else "?", sec, n["band"], n["channel"],
                n["bssid_count"], "Yes" if key in self.saved else "No", pw_text))
        if prev and self.table.exists(prev[0]):
            self.table.selection_set(prev[0])

    def selected_network(self):
        sel = self.table.selection()
        if not sel:
            return None
        return next((n for n in self.networks if n["ssid"] == sel[0]), None)

    def on_select(self, _e=None):
        self.refresh_pw_row()
        n = self.selected_network()
        if not n:
            return
        key = n["ssid"].casefold()
        sig = f"{n['signal']}%" if n["signal"] is not None else "unknown"
        lines = [n["ssid"] + ("  (connected)" if n["ssid"] == self.connected else ""),
                 f"Signal {sig} • {n['security']} • {n['band']} ch {n['channel']} • {n['bssid_count']} AP(s)",
                 f"Saved profile: {'Yes' if key in self.saved else 'No'}"]
        if is_risky(n["security"]):
            lines.append("⚠ Weak/no encryption — avoid sensitive logins here.")
        self.lbl_detail.configure(text="\n".join(lines))
        self.draw_all_charts()

    def refresh_pw_row(self):
        n = self.selected_network()
        pw = n and self.passwords.get(n["ssid"].casefold())
        if not pw:
            self.pw_var.set("No saved password" if n else "")
            self.ent_pw.configure(show="")
            self.btn_eye.configure(state="disabled", text="👁 Show")
            return
        shown = self.var_reveal.get() or n["ssid"] in self.revealed
        self.pw_var.set(pw)
        self.ent_pw.configure(show="" if shown else "•")
        self.btn_eye.configure(state="normal", text="🙈 Hide" if shown else "👁 Show")

    def toggle_selected_pw(self):
        n = self.selected_network()
        if not n or not self.passwords.get(n["ssid"].casefold()):
            return
        if self.var_reveal.get():
            self.var_reveal.set(False)
            self.revealed.clear()
        elif n["ssid"] in self.revealed:
            self.revealed.discard(n["ssid"])
        else:
            self.revealed.add(n["ssid"])
        self.render()
        self.refresh_pw_row()

    def on_toggle_all(self):
        if not self.var_reveal.get():
            self.revealed.clear()
        self.render()
        self.refresh_pw_row()

    def on_table_click(self, event):
        if self.table.identify_region(event.x, event.y) != "cell":
            return
        if self.table.identify_column(event.x) != f"#{self.COLS.index('password') + 1}":
            return
        row = self.table.identify_row(event.y)
        if row and self.passwords.get(row.casefold()):
            self.table.selection_set(row)
            self.toggle_selected_pw()

    def on_right_click(self, event):
        row = self.table.identify_row(event.y)
        if row:
            self.table.selection_set(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------ actions
    def _clipboard(self, text, label):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status(f"{label} copied" + (" (clipboard clears in 30s)" if "assword" in label else ""))
        if "assword" in label:
            self.root.after(30_000, lambda: self._clear_if(text))

    def _clear_if(self, text):
        try:
            if self.root.clipboard_get() == text:
                self.root.clipboard_clear()
        except tk.TclError:
            pass

    def copy_ssid(self):
        n = self.selected_network()
        if n:
            self._clipboard(n["ssid"], "Wi-Fi name")

    def copy_password(self):
        n = self.selected_network()
        pw = n and self.passwords.get(n["ssid"].casefold())
        if pw:
            self._clipboard(pw, "Password")
        else:
            messagebox.showinfo("No password", "No saved password is available for this network.")

    def connect_selected(self):
        n = self.selected_network()
        if not n:
            return
        profile = self.saved.get(n["ssid"].casefold())
        if not profile:
            messagebox.showinfo("Not saved", "Only networks with a saved Windows profile can be connected from here.")
            return
        if not messagebox.askyesno("Connect", f"Connect to “{n['ssid']}”?"):
            return
        try:
            out = run_netsh(["connect", f"name={profile}", f"ssid={n['ssid']}"])
            self.set_status(out.strip() or "Connection requested.")
        except Exception as exc:
            messagebox.showerror("Connect failed", str(exc))

    def export_csv(self):
        rows = self.filtered()
        if not rows:
            messagebox.showinfo("Nothing to export", "Run a scan first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=f"wifi_scan_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["SSID", "Signal %", "Security", "Band", "Channel", "Access points", "Saved profile"])
            for n in rows:
                w.writerow([n["ssid"], n["signal"], n["security"], n["band"], n["channel"],
                            n["bssid_count"], "Yes" if n["ssid"].casefold() in self.saved else "No"])
        self.set_status(f"Exported {len(rows)} networks to {path}")

    # ------------------------------------------------------------------ charts
    def draw_all_charts(self):
        self.draw_history()
        self.draw_channels()

    def animate_radar(self):
        try:
            if self.nb.index(self.nb.select()) == 0:
                self.draw_radar()
        except tk.TclError:
            return
        self.root.after(60, self.animate_radar)

    def draw_radar(self):
        c = self.radar
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 300)
        cx, cy, R = w / 2, h / 2, min(w, h) * 0.42
        for f in (0.25, 0.5, 0.75, 1.0):
            c.create_oval(cx - R * f, cy - R * f, cx + R * f, cy + R * f, outline="#176344")
        c.create_line(cx - R, cy, cx + R, cy, fill="#176344")
        c.create_line(cx, cy - R, cx, cy + R, fill="#176344")
        for i in range(10, 0, -1):
            a = math.radians(self.radar_angle - i * 3)
            c.create_line(cx, cy, cx + R * math.cos(a), cy + R * math.sin(a),
                          fill=mix("#52FF9A", "#061510", 1 - i / 11), width=2)
        a = math.radians(self.radar_angle)
        c.create_line(cx, cy, cx + R * math.cos(a), cy + R * math.sin(a), fill="#52FF9A", width=2)
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#6CFFB2", outline="")

        sel = self.table.selection()
        sel = sel[0] if sel else None
        for n in self.networks:
            sig = n["signal"] if n["signal"] is not None else 35
            r = R * (0.18 + (100 - sig) / 100 * 0.78)
            ang = math.radians(zlib.crc32(n["ssid"].encode("utf-8", "ignore")) % 360)
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            col = "#65FF9E" if not is_risky(n["security"]) else "#FF8A65"
            if n["ssid"] == self.connected:
                c.create_oval(x - 11, y - 11, x + 11, y + 11, outline="#38BDF8", width=2)
            if n["ssid"] == sel:
                c.create_oval(x - 14, y - 14, x + 14, y + 14, outline="#FFD966", width=2)
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=col, outline="")
            c.create_arc(x - 9, y - 9, x + 9, y + 9, start=35, extent=110, style="arc", outline=col, width=2)
            label = n["ssid"] if len(n["ssid"]) <= 13 else n["ssid"][:12] + "…"
            c.create_text(x, y + 16, text=label, fill="#B9FFD4", font=("Segoe UI", 7))
            if n["ssid"].casefold() in self.saved:
                c.create_text(x + 12, y - 10, text="✓", fill="#FFD966", font=("Segoe UI", 9, "bold"))
        c.create_text(8, h - 8, anchor="sw", fill="#65FF9E", font=("Segoe UI", 7),
                      text="green = secure • orange = open/WEP • cyan ring = connected\n"
                           "closer to center = stronger (angle is illustrative)")
        self.radar_angle = (self.radar_angle + 3) % 360

    def draw_history(self):
        c, t = self.hist, self.t
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 300)
        sel = self.table.selection()
        l, r, tp, b = 38, w - 14, 30, h - 28
        c.create_text(l, 10, anchor="w", fill=t["fg"], font=("Segoe UI", 10, "bold"),
                      text=(sel[0] if sel else "Select a network to see its signal history"))
        for v in (0, 25, 50, 75, 100):
            y = b - (b - tp) * v / 100
            c.create_line(l, y, r, y, fill=t["grid"])
            c.create_text(l - 6, y, anchor="e", fill=t["muted"], font=("Segoe UI", 8), text=f"{v}%")
        if not sel or sel[0] not in self.history:
            return
        data = list(self.history[sel[0]])
        step = (r - l) / max(HISTORY_LEN - 1, 1)
        x0 = r - step * (len(data) - 1)
        pts, last = [], None
        for i, v in enumerate(data):
            if v is None:
                if len(pts) > 1:
                    c.create_line(*pts, fill=t["accent"], width=2, smooth=True)
                pts = []
                continue
            x, y = x0 + i * step, b - (b - tp) * v / 100
            pts += [x, y]
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=t["accent"], outline="")
            last = (x, y, v)
        if len(pts) > 2:
            c.create_line(*pts, fill=t["accent"], width=2, smooth=True)
        if last:
            c.create_text(last[0], last[1] - 12, text=f"{last[2]}%", fill=t["fg"], font=("Segoe UI", 9, "bold"))
        c.create_text((l + r) / 2, h - 10, fill=t["muted"], font=("Segoe UI", 8), text="older  ←  scans  →  newer")

    def draw_channels(self):
        c, t = self.chan, self.t
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 300)
        counts = Counter()
        for n in self.networks:
            for b in n["bss"]:
                if b["channel"] and b["channel"].isdigit():
                    counts[(int(b["channel"]), b["band"] or "")] += 1
        c.create_text(12, 12, anchor="w", fill=t["fg"], font=("Segoe UI", 10, "bold"),
                      text="Channel congestion (access points per channel)")
        if not counts:
            c.create_text(w / 2, h / 2, fill=t["muted"], text="Run a scan to see channel usage")
            return
        items = sorted(counts.items())
        top = max(counts.values())
        l, r, tp, b = 16, w - 16, 44, h - 70
        bw = (r - l) / len(items)
        for i, ((ch, band), cnt) in enumerate(items):
            x = l + i * bw
            bh = (b - tp) * cnt / top
            col = "#F59E0B" if band.startswith("2.4") or ch <= 14 else "#14B8A6"
            c.create_rectangle(x + 2, b - bh, x + bw - 2, b, fill=col, outline="")
            c.create_text(x + bw / 2, b - bh - 8, text=str(cnt), fill=t["fg"], font=("Segoe UI", 8))
            c.create_text(x + bw / 2, b + 9, text=str(ch), fill=t["muted"], font=("Segoe UI", 7))
        c.create_text(l, b + 28, anchor="w", fill="#F59E0B", font=("Segoe UI", 8), text="■ 2.4 GHz")
        c.create_text(l + 70, b + 28, anchor="w", fill="#14B8A6", font=("Segoe UI", 8), text="■ 5 GHz+")
        c24 = Counter({ch: v for (ch, band), v in counts.items() if ch <= 14})
        if c24:
            scores = {ch: sum(v for k, v in c24.items() if abs(k - ch) <= 4) for ch in (1, 6, 11)}
            best = min(scores, key=scores.get)
            tip = f"💡 Best 2.4 GHz channel for your router: {best}"
        else:
            tip = "💡 No 2.4 GHz networks detected"
        c.create_text(l, h - 14, anchor="w", fill=t["fg"], font=("Segoe UI", 9, "bold"), text=tip)

    def on_close(self):
        if self.auto_job:
            self.root.after_cancel(self.auto_job)
        self.root.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    app = WifiScannerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
