# [Project: LEDGER LOGIC]
## Theme: The "Frictionless Voting" Protocol
### Problem: 
Current voting systems in Tamil Nadu suffer from high operational costs (polling booths, security, logistics) and accessibility barriers (long queues, travel requirements, manual counting).

### Our Solution:
1. **Remote Mobile Access:** Eliminates travel and queues by allowing secure voting from any mobile device, drastically increasing voter turnout.
2. **Zero-Booth Architecture:** Removes the overhead cost of physical polling stations, reducing the election commission's budget by estimated 60-70%.
3. **Real-time Telecasting:** Uses Google Cloud Firestore to "telecast" live, audited vote counts to the public dashboard, ensuring total transparency and eliminating "waiting for results."
4. **Data Integrity:** Leveraging Firebase Authentication and Firestore to ensure "One Person, One Vote" without human intervention.

---

## Tech Stack
| Component | Technology |
|-----------|-----------|
| Backend | Python / Flask |
| Frontend | HTML5, Tailwind CSS, Vanilla JS |
| Database | SQLite (local) + Google Cloud Firestore (live sync) |
| Map Engine | SVG Pan-Zoom with 234-constituency interactive map |
| Auth | OTP-based Identity Gate |
| Deployment | AWS EC2 (Gunicorn + Nginx) |

## Architecture
```
[Mobile/Desktop Browser]
        |
    [Flask Server]  ──────►  [Google Cloud Firestore]
        |                        (Real-time Telecast)
    [SQLite DB]
  (Local Ledger)
```

## Key Features
- **Interactive Tamil Nadu Map** — 234 constituencies, color-coded by party, with hover tooltips and click-to-inspect analytics panel
- **System Heartbeat** — Live Firebase sync with DATA UPLOADED / CHANGES HAPPENED / ATTACK HAPPENED logs
- **Glass-Box Audit Mode** — View the full server source code from within the app for transparency
- **OTP Authentication** — 4-digit identity verification before casting a vote
- **Real-time Telecasting** — Firestore `onSnapshot` listener pushes live vote counts to the dashboard without page refresh
- **Log Download** — Export system logs (data, changes, attacks) as plaintext files

## Setup & Run
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

# Run tests
python -m pytest test_app.py -v
```

## Testing
```bash
python -m pytest test_app.py -v
```
Tests cover:
- Homepage rendering & UI availability
- API data integrity (constituencies, stats, votes)
- OTP generation logic
- Mobile payload efficiency (Cost Reduction validation)
- Telecast availability (live-count endpoint)
- Error handling (404 for invalid routes)
- Response header security

## Environment Variables
| Variable | Description |
|----------|-------------|
| `firebase-key.json` | Google Cloud service account key (place in root directory) |
| `voting.db` | Auto-generated SQLite database |

## 🛡️ Radical Transparency Protocol (The Triple Ledger)
To ensure 100% public trust, Ledger Logic provides a real-time, public audit trail categorized into three streams:

1. **Voter List Integrity:** 
   - Every uploaded data packet is cross-referenced with the official 2026 Voter Registry.
   - Citizens can verify that their ID is active without compromising their secret ballot.

2. **Application Immutable Change-Log:** 
   - Every update, patch, or configuration change to the voting engine is logged to the Google Cloud.
   - This prevents "backdoor" changes during the election process.

🤖 The Digital Electoral Navigator
To align with the goals of civic education, LedgerLogic includes an interactive AI assistant designed to guide "laymen" through the complexities of the digital election process.

Educational Capabilities:
Legal Rights (Section 49A): The assistant provides clear, conversational explanations of Section 49A of the penal code, ensuring users understand their protections if their vote is proxied or tampered with.

OTP & Identity Security: Beyond just verifying users, the assistant educates voters on how 4-digit OTP authentication acts as a digital safeguard to prevent identity theft and ensure "One Person, One Vote."

Transparency Education: It breaks down the technical "Radical Transparency Protocol" into simple terms, explaining how real-time audit trails and public ledgers prevent fraud.
3. **Live Threat Telemetry (Hack Defense):** 
   - Every unauthorized access attempt, SQL injection, or DDoS signature is telecasted live.
   - By making attacks public, we ensure that security is not just a promise, but a visible reality.

## License
MIT — Built for the CyFocus 2026 Hackathon.
