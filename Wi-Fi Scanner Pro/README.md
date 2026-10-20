
# Wi-Fi Scanner Pro

A professional Windows Wi-Fi scanner built with **Python & Tkinter** that discovers nearby networks, analyzes signal strength, visualizes channel congestion and signal history on a live radar, and manages saved Wi-Fi profiles — all in a sleek dark/light themed desktop app.

[![Wi-Fi Scanner Pro — dark theme](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/dark_theme.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/dark_theme.png)[![Wi-Fi Scanner Pro — light theme](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/light_theme.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/light_theme.png)

Dark + light theme. Same layout, one-click toggle.

* * *

## ✨ Features


- **Live network discovery** — scans all nearby Wi-Fi networks via `netsh wlan` and shows SSID, signal %, security, band (2.4 / 5 GHz), channel and access-point count
- **Animated radar view** — polar sweep with per-network dots; distance from center reflects signal strength, colour reflects security (green = WPA, orange = open/WEP), cyan ring = currently connected
- **Signal history graph** — line chart tracking a network's signal over the last 30 scans, with the latest value labelled
- **Channel congestion chart** — bar chart of access points per channel with a recommendation for the best 2.4 GHz channel
- **Smart filtering & sorting** — search by name (Ctrl+F), filter by Saved / Strong (70%+) / Open & risky / 2.4 GHz / 5 GHz+, click any column header to sort ascending/descending
- **Saved password retrieval** — pulls saved Wi-Fi passwords from Windows profiles via `netsh show profile … key=clear`; hidden by default, reveal per-row or all at once
- **One-click connect** — connect directly to a saved Windows profile from the details pane
- **Dark / Light themes** — one-click toggle between a slate-blue dark look and a clean white light look
- **Auto-scan mode** — optional 10-second auto refresh
- **CSV export** — export filtered results (passwords are never included in CSV)
- **Clipboard safety** — copied passwords auto-clear from clipboard after 30 seconds

* * *

##  How it works


1. **Pick your filter** — All, Saved, Strong (70%+), Open / risky, 2.4 GHz, or 5 GHz+
2. **Press Scan** (or F5) — nearby networks populate the table instantly
3. **Select a network** — the right panel shows details, signal history, channel congestion and radar position
4. **Connect or Copy** — use a saved profile, or copy SSID/password for manual setup

* * *

## 💻 Run locally


No external dependencies — pure Python standard library only.

```
python wifi_scan.py
```

Or double-click `wifi_scan.py` directly.

**Requirements**

| Requirement | Why |
| --- | --- |
| Windows 10 / 11 | Uses `netsh wlan` (Windows-only) |
| Python 3.9+ | Tkinter ships with the official Windows installer |
| Administrator rights | Required for `netsh` to read saved passwords |

* * *

## 📸 Screenshots


|  |  |
| :-: | :-: |
| [![Dark theme](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/dark_theme.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/dark_theme.png) | [![Light theme](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/light_theme.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/light_theme.png) |
| _Dark theme — full UI, radar & detail pane_ | _Light theme — same layout, light palette_ |

|  |  |
| :-: | :-: |
| [![Radar view](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/radar_view.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/radar_view.png) | [![Channel congestion](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/channel_congestion.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/channel_congestion.png) |
| _Animated radar with sweep beam and per-network dots_ | _Channel congestion bar chart with best-channel tip_ |

|  |
| :-: |
| [![Signal history](https://github.com/MaksBloxX/Python-Project/raw/main/Wi-Fi%20Scanner%20Pro/images/signal_history.png)](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/images/signal_history.png) |
| _Signal history line chart — last 30 scans for the selected network_ |

* * *

## 🗂 Project structure


```
Wi-Fi Scanner Pro/
├── wifi_scan.py     # Single-file application (scanner + GUI)
├── images/          # Screenshots used in this README
│   ├── dark_theme.png
│   ├── light_theme.png
│   ├── radar_view.png
│   ├── channel_congestion.png
│   └── signal_history.png
└── README.md
```

* * *

##  Network table columns


| Column | Description |
| --- | --- |
| **Wi-Fi Name** | SSID (● prefix = currently connected) |
| **Strength** | Visual signal bars (▰) |
| **Signal** | Signal percentage |
| **Security** | Authentication type ( warning for Open/WEP) |
| **Band** | 2.4 GHz or 5 GHz |
| **Ch** | Channel number |
| **APs** | Number of access points (BSSIDs) |
| **Saved** | Whether a Windows profile exists |
| **Password** | Saved password (hidden by default) |

* * *

## ️ Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| **F5** | Scan now |
| **Ctrl+F** | Focus the search bar |

* * *

## 🛠 Troubleshooting


| Symptom | Fix |
| --- | --- |
| "Scan failed" / empty list | Run as **Administrator**; make sure WLAN AutoConfig is running (`net start Wlansvc`) |
| "Access denied" on `netsh` | Right-click the terminal / Python launcher → **Run as administrator** |
| No saved passwords shown | Passwords are only retrievable for profiles stored on this machine; connect to the network once first |
| "CSV export" button greyed out | Run a scan first — export works on the currently filtered list |
| Radar looks crowded | Many networks in range = more dots; use the filter dropdown to narrow by band or signal strength |
| Clipboard still has password after 30 s | Auto-clear only works if no other app has overwritten the clipboard; clear it manually |

* * *

## 📄 License

MIT — see [LICENSE](https://github.com/MaksBloxX/Python-Project/blob/main/Wi-Fi%20Scanner%20Pro/LICENSE).
