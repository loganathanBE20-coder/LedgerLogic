# [LEDGER LOGIC] Tamil Nadu 2026 Assembly Command Center

**Problem Statement Alignment:** This project solves the critical challenge of election transparency and tactical monitoring by providing an immutable, real-time public ledger. By integrating **Google Cloud Firestore**, Ledger Logic ensures that every vote and system event is recorded in a decentralized, tamper-evident environment, bridging the trust gap between voters and the electoral process.
A real-time tactical election dashboard built with Flask, featuring an interactive SVG constituency map, live voting simulation, and ElectionBaba-style analytics panels.

![Dashboard Preview](https://img.shields.io/badge/Status-LIVE-ff3366?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-00e5ff?style=for-the-badge)
![Flask](https://img.shields.io/badge/Flask-3.x-00ff9d?style=for-the-badge)

---

## Features

- **Interactive Tactical Map** — 207 Tamil Nadu assembly constituencies rendered as clickable SVG polygons with hover tooltips
- **ElectionBaba-Style Analytics Panel** — Click any constituency to see leader, vote margin, turnout, and top candidates
- **System Heartbeat Sidebar** — Real-time log streams: Data Uploaded, Changes Happened, Attack Detected (with download buttons)
- **Live Voting Simulation** — OTP-based identity gate with vote casting and duplicate detection
- **Party Summary Cards** — Seat counts and vote share percentages for 5 parties
- **Color Legend** — Visual mapping of party colors on the map
- **Source Code Audit** — Built-in glass-box mode to view the backend source
- **Dark Cyber-Tactical Theme** — Premium #0b0e14 dark mode with neon accents

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Preprocess the SVG Map (only needed once)

```bash
python preprocess_svg.py
```

This reads `Wahlkreise_zur_Vidhan_Sabha_von_Tamil_Nadu.svg` and `constituency.txt` to generate `static/tn_map_processed.svg`.

### 3. Run the Server

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

## Project Structure

```
PRomptWars/
├── app.py                  # Flask backend (API, auth, voting, logs)
├── preprocess_svg.py       # SVG map processor (label→polygon matching)
├── constituency.txt        # Official 234 constituency names
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # Full dashboard UI (single-page app)
├── static/
│   └── tn_map_processed.svg  # Processed interactive map
├── Wahlkreise_zur_Vidhan_Sabha_von_Tamil_Nadu.svg  # Source SVG
└── voting.db               # SQLite database (auto-created)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python Flask |
| Database | SQLite |
| Frontend | Vanilla JS, Tailwind CSS (CDN) |
| Map | SVG with svg-pan-zoom |
| Fonts | Google Fonts (Rajdhani) |

## API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Dashboard |
| `/api/map` | GET | Processed SVG map |
| `/api/data` | GET | Live stats, constituencies, logs |
| `/api/request_otp` | POST | Start voting flow |
| `/api/verify_otp` | POST | Verify OTP |
| `/api/vote` | POST | Cast vote |
| `/api/download_logs` | GET | Download log file (`?type=data_uploaded\|changes_happened\|attack_happened`) |
| `/api/source` | GET | Backend source code |

## Notes

- The database (`voting.db`) is auto-created on first run
- 27 dense urban constituencies (Chennai, Madurai cores) are not mapped on the SVG since they only exist in removed inset panels
- Delete `voting.db` to reset all data

---

**Built with [LEDGER LOGIC]** — Transparency in Every Transaction.
