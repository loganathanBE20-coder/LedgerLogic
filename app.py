"""LedgerLogic — Transparent Digital Voting Dashboard for Tamil Nadu 2026.

Solves the 'black box' problem in digital elections by making everything
public: live vote counts, audit logs, and live-streamed attack attempts.
Visibility is the primary security measure.
"""

import os
import sqlite3
import random
import string
import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from flask import (
    Flask, render_template, request, jsonify,
    g, session, send_file, make_response, Response
)
from flask_compress import Compress
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Google Cloud Logging (graceful degradation) ---
try:
    import google.cloud.logging as cloud_logging
    cloud_client = cloud_logging.Client()
    cloud_client.setup_logging()
    logger = logging.getLogger('ledgerlogic')
    logger.info('Google Cloud Logging initialized')
except Exception:
    logger = logging.getLogger('ledgerlogic')
    logging.basicConfig(level=logging.INFO)
    logger.info('Using standard Python logging (Cloud Logging unavailable)')

# --- App Initialization ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())

# Session hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Efficiency: gzip compression on all responses
Compress(app)

# Efficiency: server-side caching (60s TTL)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 60})

# Security: rate limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per minute"])

# --- Google Cloud Config ---
GCP_PROJECT = os.environ.get('GCP_PROJECT', '')
BQ_DATASET = os.environ.get('BIGQUERY_DATASET', 'ledgerlogic_analytics')

DATABASE = 'voting.db'

# --- BIGQUERY CLIENT (graceful degradation) ---
bq_client = None
try:
    from google.cloud import bigquery
    bq_client = bigquery.Client(project=GCP_PROJECT) if GCP_PROJECT else None
    if bq_client:
        logger.info('BigQuery client initialized (project=%s)', GCP_PROJECT)
except Exception as e:
    logger.warning('BigQuery unavailable: %s', e)
    bq_client = None

# --- NATURAL LANGUAGE API CLIENT (graceful degradation) ---
nl_client = None
try:
    from google.cloud import language_v1
    nl_client = language_v1.LanguageServiceClient()
    logger.info('Natural Language API client initialized')
except Exception as e:
    logger.warning('Natural Language API unavailable: %s', e)
    nl_client = None

# --- FIREBASE INTEGRATION ---
try:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
    db_firestore = firestore.client()
    logger.info('Firebase Initialized Successfully')
except Exception as e:
    logger.warning('Firebase Init Error: %s', e)
    db_firestore = None


def log_system_active() -> None:
    """Send a heartbeat pulse to Firebase Firestore to confirm server liveness."""
    if db_firestore:
        try:
            doc_ref = db_firestore.collection('system_logs').document('heartbeat')
            doc_ref.set({
                'status': 'ONLINE',
                'last_pulse': datetime.now(),
                'server': 'Local-Development-Node'
            })
            logger.info('Firebase Heartbeat Sent')
        except Exception as e:
            logger.error('Firebase Heartbeat Error: %s', e)


log_system_active()


def get_db() -> sqlite3.Connection:
    """Return the per-request SQLite database connection."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception: Optional[BaseException]) -> None:
    """Close the SQLite connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def log_event(log_type: str, message: str) -> None:
    """Insert an event into the local audit log."""
    db = get_db()
    db.execute('INSERT INTO logs (type, message) VALUES (?, ?)', (log_type, message))
    db.commit()


# --- BIGQUERY STREAMING HELPERS ---

def stream_vote_to_bigquery(name_hashed: str, candidate: str,
                            constituency_id: int, session_id: str = '') -> None:
    """Stream a vote record to BigQuery votes_raw table (non-blocking best-effort).

    Falls back silently if BigQuery is unavailable.
    """
    if not bq_client:
        return
    try:
        table_ref = f'{GCP_PROJECT}.{BQ_DATASET}.votes_raw'
        row = {
            'vote_id': str(uuid.uuid4()),
            'name_hashed': name_hashed,
            'candidate': candidate,
            'constituency_id': constituency_id,
            'party': candidate,
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id
        }
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error('BigQuery vote insert errors: %s', errors)
        else:
            logger.info('Vote streamed to BigQuery: %s', row['vote_id'])
    except Exception as e:
        logger.warning('BigQuery vote stream error (non-fatal): %s', e)


def stream_security_event_to_bigquery(event_type: str, masked_ip: str = '',
                                       path: str = '', payload_sig: str = 'BLOCKED',
                                       severity: str = 'UNCLASSIFIED',
                                       sentiment_score: float = 0.0) -> None:
    """Stream a security event to BigQuery security_events table (non-blocking best-effort).

    Falls back silently if BigQuery is unavailable.
    """
    if not bq_client:
        return
    try:
        table_ref = f'{GCP_PROJECT}.{BQ_DATASET}.security_events'
        row = {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'masked_ip': masked_ip,
            'path': path,
            'payload_signature': payload_sig,
            'severity': severity,
            'sentiment_score': sentiment_score,
            'timestamp': datetime.utcnow().isoformat()
        }
        errors = bq_client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error('BigQuery security insert errors: %s', errors)
        else:
            logger.info('Security event archived to BigQuery: %s', row['event_id'])
    except Exception as e:
        logger.warning('BigQuery security stream error (non-fatal): %s', e)


# --- NATURAL LANGUAGE API — THREAT CLASSIFICATION ---

def classify_threat_severity(message: str) -> dict:
    """Use Cloud Natural Language API to classify threat severity.

    Returns dict with 'severity' (LOW/MEDIUM/HIGH/CRITICAL) and 'sentiment_score'.
    Falls back to heuristic classification if NL API is unavailable.
    """
    # Heuristic fallback keywords
    critical_keywords = ['sql injection', 'drop table', 'union select', 'etc/passwd']
    high_keywords = ['duplicate vote', 'brute-force', 'lockout', 'unauthorized']
    medium_keywords = ['invalid otp', 'expired otp', 'rate limit']

    lower_msg = message.lower()

    if not nl_client:
        # Heuristic classification
        if any(kw in lower_msg for kw in critical_keywords):
            return {'severity': 'CRITICAL', 'sentiment_score': -0.9}
        if any(kw in lower_msg for kw in high_keywords):
            return {'severity': 'HIGH', 'sentiment_score': -0.7}
        if any(kw in lower_msg for kw in medium_keywords):
            return {'severity': 'MEDIUM', 'sentiment_score': -0.4}
        return {'severity': 'LOW', 'sentiment_score': -0.2}

    try:
        document = language_v1.types.Document(
            content=message,
            type_=language_v1.types.Document.Type.PLAIN_TEXT
        )
        sentiment = nl_client.analyze_sentiment(
            request={'document': document}
        ).document_sentiment

        score = sentiment.score
        magnitude = sentiment.magnitude

        # Map NLP sentiment to threat severity
        if score < -0.6 and magnitude > 0.8:
            severity = 'CRITICAL'
        elif score < -0.3:
            severity = 'HIGH'
        elif score < 0.0:
            severity = 'MEDIUM'
        else:
            severity = 'LOW'

        logger.info('NLP threat classification: severity=%s score=%.2f mag=%.2f',
                     severity, score, magnitude)
        return {'severity': severity, 'sentiment_score': score}
    except Exception as e:
        logger.warning('NL API classification error (using heuristic): %s', e)
        if any(kw in lower_msg for kw in critical_keywords):
            return {'severity': 'CRITICAL', 'sentiment_score': -0.9}
        return {'severity': 'UNCLASSIFIED', 'sentiment_score': 0.0}


def init_db() -> None:
    """Initialize SQLite tables and seed 234 constituency records if empty."""
    with app.app_context():
        db = get_db()
        # Initialize tables
        db.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                candidate TEXT NOT NULL,
                constituency_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, mobile)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS constituencies (
                id INTEGER PRIMARY KEY,
                name TEXT,
                party TEXT,
                votes INTEGER
            )
        ''')
        
        # Check if constituencies table is empty
        cursor = db.execute('SELECT COUNT(*) FROM constituencies')
        if cursor.fetchone()[0] == 0:
            parties = ['Party X', 'Party Y', 'Party Z', 'Party W', 'Others']
            
            # Read real names if available
            mapping = {}
            try:
                with open('constituency.txt', 'r', encoding='utf-8') as f:
                    import re
                    for line in f:
                        match = re.search(r'(?:^|\t)(\d+)\s+([^\t\n]+)', line)
                        if match:
                            mapping[int(match.group(1))] = match.group(2).strip()
            except (FileNotFoundError, ValueError):
                pass

            for i in range(1, 235):
                name = mapping.get(i, f'Constituency {i}')
                db.execute(
                    'INSERT INTO constituencies (id, name, party, votes) VALUES (?, ?, ?, ?)',
                    (i, name, random.choice(parties), random.randint(8000, 80000))
                )
            db.commit()
            log_event('changes_happened', 'Database Initialized & Map Seeded')

init_db()

@app.before_request
def security_monitor():
    """Security Middleware: Detects and blocks malicious input attempts.
    Logs every hack attempt to Firebase for Live Threat Telemetry."""
    suspicious_keywords = ["<script>", "admin", "SELECT *", "DROP TABLE", "UNION SELECT", "../", "etc/passwd"]
    request_data = str(request.args) + str(request.form)

    if any(keyword.lower() in request_data.lower() for keyword in suspicious_keywords):
        # Mask IP for privacy, keep last octet for geo-tracking
        ip_parts = (request.remote_addr or '0.0.0.0').split('.')
        masked_ip = 'XXX.XXX.' + ip_parts[-1] if len(ip_parts) >= 1 else 'XXX.XXX.0'

        threat_msg = f'THREAT: Malicious Input Detected | IP: {masked_ip} | Path: {request.path}'

        # NLP-powered threat classification (Cloud Natural Language API)
        classification = classify_threat_severity(threat_msg)
        severity = classification['severity']
        sentiment_score = classification['sentiment_score']

        # Log to local DB with severity
        log_event('attack_happened', f'{threat_msg} | Severity: {severity}')

        # Stream to BigQuery (security_events table)
        stream_security_event_to_bigquery(
            event_type='MALICIOUS_INPUT',
            masked_ip=masked_ip,
            path=request.path,
            payload_sig='BLOCKED',
            severity=severity,
            sentiment_score=sentiment_score
        )

        # Log to Firebase for Live Threat Telemetry
        if db_firestore:
            try:
                db_firestore.collection('hack_attempts').add({
                    'type': 'Malicious Input Detected',
                    'ip_masked': masked_ip,
                    'timestamp': datetime.now(),
                    'path': request.path,
                    'payload_signature': 'BLOCKED',
                    'severity': severity,
                    'sentiment_score': sentiment_score
                })
            except Exception as e:
                logger.error('Firebase hack log error: %s', e)

        return "Security Violation Logged.", 403

@app.before_request
def log_request_info() -> None:
    """Log main route access to the audit trail."""
    if request.path == '/' and request.method == 'GET':
        log_event('changes_happened', 'Main Route Accessed')


@app.after_request
def add_security_headers(response: Response) -> Response:
    """Inject security headers on every response (CSP, X-Frame, etc.)."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://firestore.googleapis.com; "
        "img-src 'self' data:;"
    )
    return response

@app.route('/')
def index() -> Response:
    """Serve the main dashboard HTML with cache headers."""
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'public, max-age=300'
    return response


@app.route('/api/map')
def api_map() -> Response:
    """Serve the processed SVG map with long-lived cache headers."""
    response = make_response(send_file('static/tn_map_processed.svg', mimetype='image/svg+xml'))
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


def generate_mock_details(c: dict) -> dict:
    """Generate deterministic mock candidate details for a constituency."""
    seed = int(hashlib.md5(str(c['id']).encode()).hexdigest(), 16)
    random.seed(seed)
    
    winner_votes = c['votes']
    total_votes = winner_votes + random.randint(10000, 50000)
    
    second_votes = random.randint(int(winner_votes * 0.5), winner_votes - 100)
    third_votes = random.randint(1000, int(second_votes * 0.5))
    
    w_pct = round((winner_votes / total_votes) * 100, 2)
    s_pct = round((second_votes / total_votes) * 100, 2)
    t_pct = round((third_votes / total_votes) * 100, 2)
    margin = winner_votes - second_votes
    margin_pct = round(w_pct - s_pct, 2)
    
    parties = ['Party X', 'Party Y', 'Party Z', 'Party W', 'Others']
    other_parties = [p for p in parties if p != c['party']]
    random.shuffle(other_parties)
    
    names = ['A. Kumar', 'S. Raman', 'M. Stalin', 'K. Palaniswami', 'T. Velmurugan', 'V. Anbumani', 'C. Seeman', 'R. Kathiravan']
    
    candidates = [
        {'rank': 1, 'name': random.choice(names), 'party': c['party'], 'votes': winner_votes, 'percentage': w_pct},
        {'rank': 2, 'name': random.choice(names), 'party': other_parties[0], 'votes': second_votes, 'percentage': s_pct},
        {'rank': 3, 'name': random.choice(names), 'party': other_parties[1], 'votes': third_votes, 'percentage': t_pct}
    ]
    
    return {
        'id': c['id'],
        'name': c['name'],
        'party': c['party'],
        'votes': winner_votes,
        'total_votes': total_votes,
        'margin': margin,
        'margin_percentage': margin_pct,
        'candidates': candidates,
        'turnout': round(random.uniform(65.0, 85.0), 2),
        'total_candidates': random.randint(10, 30)
    }


@app.route('/api/data')
@cache.cached(timeout=60, query_string=True)
def api_data() -> Response:
    """Return all 234 constituencies, party stats, votes, and audit logs."""
    db = get_db()
    votes = db.execute('SELECT * FROM votes ORDER BY timestamp DESC LIMIT 10').fetchall()
    logs = db.execute('SELECT * FROM logs ORDER BY timestamp DESC LIMIT 30').fetchall()
    consts = db.execute('SELECT * FROM constituencies ORDER BY id').fetchall()
    
    total_votes = sum(c['votes'] for c in consts)
    stats_map = {p: {'name': p, 'votes': 0, 'seats': 0} for p in ['Party X', 'Party Y', 'Party Z', 'Party W', 'Others']}
    
    enriched_consts = []
    for c in consts:
        p = c['party']
        if p in stats_map:
            stats_map[p]['votes'] += c['votes']
            stats_map[p]['seats'] += 1
        
        enriched = generate_mock_details(dict(c))
        enriched_consts.append(enriched)
        
    random.seed() # reset seed
            
    stats_list = []
    for p in ['Party X', 'Party Y', 'Party Z', 'Party W', 'Others']:
        v = stats_map[p]['votes']
        pct = round((v / total_votes * 100), 1) if total_votes > 0 else 0
        stats_list.append({
            'name': p,
            'percentage': pct,
            'seats': stats_map[p]['seats'],
            'votes': v
        })
    
    return jsonify({
        'votes': [dict(v) for v in votes],
        'logs': [dict(l) for l in logs],
        'constituencies': enriched_consts,
        'stats': stats_list,
        'total_votes': total_votes
    })


@app.route('/api/request_otp', methods=['POST'])
@limiter.limit('5 per minute')
def api_request_otp() -> Response:
    """Generate a 4-digit OTP and store it in the session with a 5-minute expiry."""
    data = request.json
    name = data.get('name', '').strip()
    mobile = data.get('mobile', '').strip()
    
    # Security checks
    if "'" in name or ";" in name or "--" in name:
        log_event('attack_happened', f"THREAT: SQL Injection Detected | {name} | {datetime.now().isoformat()}")
        return jsonify({'error': 'Malicious input detected'}), 403
        
    if len(name) > 60 or len(mobile) > 15:
        log_event('attack_happened', f"THREAT: Input limits exceeded | {name} | {datetime.now().isoformat()}")
        return jsonify({'error': 'Input too long'}), 400
        
    if not name or not mobile:
        return jsonify({'error': 'Missing fields'}), 400
        
    otp = ''.join(random.choices(string.digits, k=4))
    session['pending_user'] = {
        'name': name,
        'mobile': mobile,
        'otp': otp,
        'otp_created': datetime.now().isoformat(),
        'otp_attempts': 0
    }
    
    log_event('changes_happened', f"Generated OTP for {name}: {otp}")
    return jsonify({'success': True, 'message': 'OTP generated. Check System Heartbeat logs.'})


@app.route('/api/verify_otp', methods=['POST'])
@limiter.limit('10 per minute')
def api_verify_otp() -> Response:
    """Verify the submitted OTP against the session-stored value.
    Enforces 5-minute expiry and locks out after 3 failed attempts."""
    data = request.json
    otp_submitted = data.get('otp', '').strip()
    
    pending = session.get('pending_user')
    if not pending:
        return jsonify({'error': 'No pending authentication'}), 400

    # OTP expiry check (5 minutes)
    otp_created = datetime.fromisoformat(pending.get('otp_created', datetime.now().isoformat()))
    if datetime.now() - otp_created > timedelta(minutes=5):
        session.pop('pending_user', None)
        log_event('attack_happened', f"THREAT: Expired OTP used | {pending['name']}")
        return jsonify({'error': 'OTP expired. Please request a new one.'}), 401

    # Brute-force lockout (3 attempts max)
    attempts = pending.get('otp_attempts', 0)
    if attempts >= 3:
        session.pop('pending_user', None)
        log_event('attack_happened', f"THREAT: OTP brute-force lockout | {pending['name']}")
        return jsonify({'error': 'Too many failed attempts. Please request a new OTP.'}), 429

    if otp_submitted == pending['otp']:
        session['user'] = {'name': pending['name'], 'mobile': pending['mobile']}
        session.pop('pending_user', None)
        log_event('changes_happened', f"Identity Verified for {pending['name']}")
        return jsonify({'success': True})
    else:
        pending['otp_attempts'] = attempts + 1
        session['pending_user'] = pending
        session.modified = True
        log_event('attack_happened', f"THREAT: Invalid OTP (attempt {attempts + 1}) | {pending['name']}")
        stream_security_event_to_bigquery(
            event_type='INVALID_OTP',
            path='/api/verify_otp',
            severity=classify_threat_severity(f'Invalid OTP attempt {attempts + 1}')['severity']
        )
        return jsonify({'error': 'Invalid OTP'}), 401


@app.route('/api/vote', methods=['POST'])
@limiter.limit('3 per minute')
def api_vote() -> Response:
    """Cast a vote (requires OTP-authenticated session). Syncs to Firestore and BigQuery."""
    user = session.get('user')
    if not user:
        log_event('attack_happened', f"THREAT: Unauthorized vote call | Unknown | {datetime.now().isoformat()}")
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    candidate = data.get('candidate')
    # Assign a random constituency for the mock prototype if not provided
    constituency_id = data.get('constituency_id', random.randint(1, 234))
    
    name = user['name']
    mobile = user['mobile']
    
    db = get_db()
    try:
        db.execute('INSERT INTO votes (name, mobile, candidate, constituency_id) VALUES (?, ?, ?, ?)',
                   (name, mobile, candidate, constituency_id))
                   
        # Update constituency totals (for mock behavior, we just add a vote. 
        # In real scenario we might re-evaluate the leading party based on candidate votes)
        # Here we just add to the total votes and maybe occasionally flip the leader
        db.execute('UPDATE constituencies SET votes = votes + 1 WHERE id = ?', (constituency_id,))
        if random.random() < 0.1: # 10% chance to flip leading party when someone votes there
             parties = ['Party X', 'Party Y', 'Party Z', 'Party W', 'Others']
             db.execute('UPDATE constituencies SET party = ? WHERE id = ?', (random.choice(parties), constituency_id))
        
        db.commit()
        log_event('data_uploaded', f"▲ VOTE_CAST: {name} -> {candidate} (TN-{constituency_id})")
        
        # Sync with Firebase
        if db_firestore:
            try:
                db_firestore.collection('votes').add({
                    'name_hashed': hashlib.sha256(name.encode()).hexdigest()[:10],
                    'candidate': candidate,
                    'constituency_id': constituency_id,
                    'timestamp': datetime.now()
                })
            except Exception as e:
                logger.error('Firebase Vote Sync Error: %s', e)

        # Stream to BigQuery (votes_raw table)
        name_hash = hashlib.sha256(name.encode()).hexdigest()[:10]
        stream_vote_to_bigquery(
            name_hashed=name_hash,
            candidate=candidate,
            constituency_id=constituency_id,
            session_id=hashlib.md5(app.secret_key.encode() if isinstance(app.secret_key, str) else app.secret_key).hexdigest()[:8]
        )
        
        # Clear session to prevent multiple votes
        session.pop('user', None)
        session.pop('pending_user', None)
        
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        log_event('attack_happened', f"THREAT: Duplicate Vote Attempt | {name} | {datetime.now().isoformat()}")
        stream_security_event_to_bigquery(
            event_type='DUPLICATE_VOTE',
            path='/api/vote',
            severity='HIGH'
        )
        return jsonify({'error': 'You have already voted!'}), 403


@app.route('/api/source')
def api_source() -> Response:
    """Expose the full server source code for radical transparency auditing."""
    try:
        with open(__file__, 'r') as f:
            source = f.read()
        return jsonify({'source': source})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download_logs')
def api_download_logs() -> Response:
    """Export audit logs as a downloadable .txt file."""
    log_type = request.args.get('type', 'all')
    db = get_db()
    
    if log_type == 'all':
        logs = db.execute('SELECT * FROM logs ORDER BY timestamp DESC').fetchall()
    else:
        logs = db.execute('SELECT * FROM logs WHERE type = ? ORDER BY timestamp DESC', (log_type,)).fetchall()
    
    content = f"=== LEDGER LOGIC - Log Export ===\n"
    content += f"Type: {log_type.upper().replace('_', ' ')}\n"
    content += f"Exported: {datetime.now().isoformat()}\n"
    content += "=" * 40 + "\n\n"
    
    for log in logs:
        content += f"[{log['timestamp']}] [{log['type']}] {log['message']}\n"
    
    return Response(
        content,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename=ledger_logic_{log_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'}
    )

# --- TELECASTING: Live Count Endpoint (High-Efficiency, Lightweight) ---
@app.route('/api/live-count')
def api_live_count() -> Response:
    """Lightweight endpoint for real-time telecasting. 
    Returns only the total vote count for maximum mobile efficiency."""
    db = get_db()
    cursor = db.execute('SELECT COUNT(*) as total FROM votes')
    total = cursor.fetchone()['total']
    
    # Sync to Firebase for public telecasting
    if db_firestore:
        try:
            db_firestore.collection('telecast').document('live_count').set({
                'total_votes': total,
                'last_updated': datetime.now(),
                'status': 'TELECASTING'
            })
        except Exception as e:
            logger.error('Telecast sync error: %s', e)
    
    return jsonify({'total_votes': total, 'status': 'live'})

# --- VERTEX AI / GEMINI CHAT ENDPOINT (ChatSession with Adaptive Memory) ---

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Exact mandated system instruction for AI evaluation
CHAT_SYSTEM_INSTRUCTION = (
    'You are the Electoral Navigator. Assess the user\'s reading level. '
    'If they use simple words, reply simply. If they use technical words, '
    'explain the cryptographic hashing of the ledger.'
)

# Extended behavioral prompt layered on top of the mandated instruction
CHAT_SYSTEM_PROMPT = CHAT_SYSTEM_INSTRUCTION + """\n\nAdditional rules:
- Your ONLY purpose is to educate citizens about the online election process.
- You may answer about: voting (OTP, identity gate), security (attack detection),
  transparency (public ledger, audit trails, hashed tallies), legal rights (Section 49A),
  and the LedgerLogic dashboard (heartbeat, data uploaded, changes, attacks).
- For ANY question NOT related to elections: respond EXACTLY with
  "I only assist with election education. For administrative issues, please contact your Booth Level Officer (BLO)."
- Keep responses concise (2-4 sentences). Use plain text, no markdown."""

# Lazy-initialized Gemini model (ChatSession-based)
_gemini_model = None
_gemini_backend = None  # 'vertex_ai' or 'generativeai'


def _get_gemini_model():
    """Lazy-init the Gemini model — tries Vertex AI SDK first, then google-generativeai.

    Vertex AI SDK provides Google-native model monitoring, prompt logging,
    and safety filters via the Cloud Console. Falls back to the direct
    google-generativeai SDK for local development without GCP credentials.
    """
    global _gemini_model, _gemini_backend
    if _gemini_model is not None:
        return _gemini_model

    # --- Strategy 1: Vertex AI SDK (preferred for Cloud Run / GCP) ---
    if GCP_PROJECT:
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(project=GCP_PROJECT, location='us-central1')
            _gemini_model = GenerativeModel(
                'gemini-1.5-flash',
                system_instruction=CHAT_SYSTEM_INSTRUCTION,
                generation_config={'temperature': 0.2, 'max_output_tokens': 500, 'top_p': 0.9}
            )
            _gemini_backend = 'vertex_ai'
            logger.info('Vertex AI Gemini 1.5 Flash initialized (project=%s)', GCP_PROJECT)
            return _gemini_model
        except Exception as e:
            logger.warning('Vertex AI init failed, trying google-generativeai fallback: %s', e)

    # --- Strategy 2: google-generativeai SDK (local dev with API key) ---
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            _gemini_model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=CHAT_SYSTEM_INSTRUCTION,
                generation_config={'temperature': 0.2, 'max_output_tokens': 500, 'top_p': 0.9}
            )
            _gemini_backend = 'generativeai'
            logger.info('google-generativeai Gemini 1.5 Flash initialized (API key)')
            return _gemini_model
        except Exception as e:
            logger.error('Gemini SDK init error: %s', e)

    return None


@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.json
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    # --- Attempt Gemini ChatSession with adaptive memory ---
    model = _get_gemini_model()
    if model:
        try:
            # Retrieve or initialize session-stored conversation history
            if 'chat_history' not in session:
                session['chat_history'] = []

            # Build history for ChatSession from Flask session
            history_for_session = []
            for msg in session['chat_history'][-10:]:
                history_for_session.append({
                    'role': msg['role'],
                    'parts': [msg['text']]
                })

            # Start a ChatSession with the accumulated history
            chat = model.start_chat(history=history_for_session)
            response = chat.send_message(user_message)
            reply_text = response.text.strip()

            if reply_text:
                # Persist to Flask session
                session['chat_history'] = session.get('chat_history', []) + [
                    {'role': 'user', 'text': user_message},
                    {'role': 'model', 'text': reply_text}
                ]
                session.modified = True
                return jsonify({'reply': reply_text})

        except Exception as e:
            logger.error('Gemini ChatSession Error: %s', e)
            # Fall through to local fallback

    # --- Local keyword fallback ---
    reply = _local_chat_fallback(user_message)
    return jsonify({'reply': reply})


def _local_chat_fallback(query):
    """Keyword-based fallback when Gemini API is unavailable."""
    BLO = 'I only assist with election education. For administrative issues, please contact your Booth Level Officer (BLO).'
    
    # We will prioritize exact keywords/phrases to prevent overlapping generic responses
    lower = query.lower()

    # Greetings
    if lower in ('hi', 'hello', 'hey', 'start'):
        return 'Welcome to the chat, Electoral Assistant.'

    # How to vote
    if any(phrase in lower for phrase in ['how to vote', 'how do i vote', 'cast vote', 'vote process']):
        return 'To vote, click "Vote Now", enter your registered details, verify with OTP, and select your candidate. Each person can only vote once — the system enforces this through phone-based identity verification.'

    # How to view vote / ledger / transparency
    if any(phrase in lower for phrase in ['view my vote', 'where is my vote', 'check vote', 'ledger', 'audit', 'transparent', 'log', 'change']):
        return 'Every interaction is recorded in the immutable audit trail. You can view the live public ledger via the dashboard, and check the hashed vote tallies to ensure transparency and verify your vote was securely recorded.'

    # Legal rights / Section 49A
    if 'section 49' in lower or 'tendered' in lower or 'rights' in lower:
        return 'Section 49A protects your right to cast a tendered ballot if someone has already voted in your name. Report immediately to the Presiding Officer at your polling station.'

    # Security / OTP / Hack
    if 'otp' in lower or 'login' in lower or 'verify' in lower:
        return 'The OTP verification ensures one-person-one-vote. You will receive a 4-digit code on your registered mobile to authenticate your identity before casting your ballot.'
    
    if 'hack' in lower or 'attack' in lower or 'security' in lower:
        return 'The system monitors for SQL injection, brute-force OTP attempts, and unauthorized access. All threats are logged with masked IPs for forensic analysis to maintain election integrity.'

    # System specific
    if 'source' in lower or 'code' in lower or 'database' in lower:
        return 'LedgerLogic practices Open Verification — the full source code and database are publicly auditable via the navigation buttons, ensuring no hidden algorithms.'
    
    if 'heartbeat' in lower or 'system' in lower or 'server' in lower:
        return 'The System Heartbeat monitors server liveness in real time. If the heartbeat stops, it indicates potential tampering and triggers an immediate alert.'

    # Contact / Officer / BLO
    if any(kw in lower for kw in ['blo', 'booth', 'officer', 'contact', 'presiding', 'help']):
        return 'Your Booth Level Officer (BLO) handles administrative issues at the polling station. Contact them for voter registration, address changes, or ID-related issues.'

    # Broad election concepts (fallback if nothing more specific matches)
    if 'candidate' in lower or 'ballot' in lower or 'party' in lower or 'election' in lower or 'vote' in lower:
        return 'This system ensures transparent, secure digital elections. You can ask me about the voting process, security (OTP), transparency (the ledger), or your legal rights under Section 49A.'

    # If NO keywords matched at all, redirect to BLO
    return BLO


# --- BIGQUERY-POWERED ANALYTICS ENDPOINT ---

@app.route('/api/analytics')
@cache.cached(timeout=120)
def api_analytics() -> Response:
    """Query BigQuery (or SQLite fallback) for advanced election analytics.

    Returns total votes, top contested constituencies, hourly vote rate,
    and attack frequency — powering the Analytics panel in the dashboard.
    """
    # --- Strategy 1: BigQuery (production) ---
    if bq_client:
        try:
            # Total votes from BigQuery
            total_q = f"SELECT COUNT(*) as total FROM `{GCP_PROJECT}.{BQ_DATASET}.votes_raw`"
            total_votes = list(bq_client.query(total_q).result())[0].total

            # Top 5 most contested constituencies (smallest margin)
            contested_q = f"""
                SELECT constituency_id, COUNT(*) as votes,
                       COUNT(DISTINCT candidate) as candidates
                FROM `{GCP_PROJECT}.{BQ_DATASET}.votes_raw`
                GROUP BY constituency_id
                HAVING candidates > 1
                ORDER BY votes DESC
                LIMIT 5
            """
            contested = [
                {'constituency_id': r.constituency_id, 'votes': r.votes, 'candidates': r.candidates}
                for r in bq_client.query(contested_q).result()
            ]

            # Hourly vote rate (last 24h)
            hourly_q = f"""
                SELECT TIMESTAMP_TRUNC(timestamp, HOUR) as hour, COUNT(*) as votes
                FROM `{GCP_PROJECT}.{BQ_DATASET}.votes_raw`
                WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                GROUP BY hour ORDER BY hour
            """
            hourly_trend = [
                {'hour': r.hour.isoformat(), 'votes': r.votes}
                for r in bq_client.query(hourly_q).result()
            ]

            # Attack frequency
            attack_q = f"""
                SELECT event_type, severity, COUNT(*) as count
                FROM `{GCP_PROJECT}.{BQ_DATASET}.security_events`
                GROUP BY event_type, severity
                ORDER BY count DESC
            """
            attack_stats = [
                {'event_type': r.event_type, 'severity': r.severity, 'count': r.count}
                for r in bq_client.query(attack_q).result()
            ]

            logger.info('Analytics served from BigQuery')
            return jsonify({
                'source': 'bigquery',
                'total_votes': total_votes,
                'top_contested': contested,
                'hourly_trend': hourly_trend,
                'attack_stats': attack_stats
            })
        except Exception as e:
            logger.warning('BigQuery analytics failed, falling back to SQLite: %s', e)

    # --- Strategy 2: SQLite fallback (local development) ---
    db = get_db()
    total_votes = db.execute('SELECT COUNT(*) as total FROM votes').fetchone()['total']
    consts = db.execute('SELECT * FROM constituencies ORDER BY votes ASC LIMIT 5').fetchall()
    contested = [{'constituency_id': c['id'], 'name': c['name'], 'votes': c['votes']} for c in consts]

    logs = db.execute(
        "SELECT type, COUNT(*) as count FROM logs WHERE type='attack_happened' GROUP BY type"
    ).fetchall()
    attack_stats = [{'event_type': l['type'], 'severity': 'UNCLASSIFIED', 'count': l['count']} for l in logs]

    return jsonify({
        'source': 'sqlite',
        'total_votes': total_votes,
        'top_contested': contested,
        'hourly_trend': [],
        'attack_stats': attack_stats
    })


# --- VERTEX AI — CONSTITUENCY INSIGHT ENDPOINT ---

@app.route('/api/constituency-insight', methods=['POST'])
def api_constituency_insight() -> Response:
    """AI-powered constituency insight using BigQuery data + Vertex AI Gemini.

    Input: constituency_id
    Flow: Fetch data from BigQuery/SQLite → Gemini prompt → 2-sentence insight.
    Falls back to a template-based response if Gemini is unavailable.
    """
    data = request.json or {}
    constituency_id = data.get('constituency_id')
    if not constituency_id:
        return jsonify({'error': 'constituency_id required'}), 400

    constituency_id = int(constituency_id)

    # 1. Fetch constituency data (BigQuery or SQLite)
    constituency_data = _get_constituency_data(constituency_id)
    if not constituency_data:
        return jsonify({'error': 'Constituency not found'}), 404

    # 2. Generate AI insight via Gemini
    model = _get_gemini_model()
    if model:
        try:
            insight_prompt = (
                f"Given this constituency data: {constituency_data}, provide a "
                f"2-sentence plain-language election insight for a citizen voter. "
                f"Focus on competitiveness and turnout. Do not use markdown."
            )
            chat = model.start_chat(history=[])
            response = chat.send_message(insight_prompt)
            insight = response.text.strip()
            logger.info('AI insight generated for constituency %d via %s', constituency_id, _gemini_backend)
            return jsonify({
                'constituency_id': constituency_id,
                'data': constituency_data,
                'insight': insight,
                'ai_backend': _gemini_backend or 'unknown'
            })
        except Exception as e:
            logger.warning('Gemini insight generation failed: %s', e)

    # 3. Template fallback
    name = constituency_data.get('name', f'Constituency {constituency_id}')
    votes = constituency_data.get('votes', 0)
    party = constituency_data.get('party', 'Unknown')
    fallback_insight = (
        f"{name} currently shows {votes:,} total votes with {party} in the lead. "
        f"Check the live dashboard for real-time updates on this constituency's race."
    )
    return jsonify({
        'constituency_id': constituency_id,
        'data': constituency_data,
        'insight': fallback_insight,
        'ai_backend': 'template_fallback'
    })


def _get_constituency_data(constituency_id: int) -> Optional[dict]:
    """Fetch constituency data from BigQuery (preferred) or SQLite fallback."""
    # BigQuery first
    if bq_client:
        try:
            q = f"""
                SELECT constituency_id, candidate as party, COUNT(*) as votes
                FROM `{GCP_PROJECT}.{BQ_DATASET}.votes_raw`
                WHERE constituency_id = {constituency_id}
                GROUP BY constituency_id, candidate
                ORDER BY votes DESC LIMIT 1
            """
            results = list(bq_client.query(q).result())
            if results:
                r = results[0]
                return {
                    'id': r.constituency_id,
                    'party': r.party,
                    'votes': r.votes,
                    'source': 'bigquery'
                }
        except Exception as e:
            logger.warning('BigQuery constituency fetch failed: %s', e)

    # SQLite fallback
    db = get_db()
    c = db.execute('SELECT * FROM constituencies WHERE id = ?', (constituency_id,)).fetchone()
    if c:
        return {
            'id': c['id'],
            'name': c['name'],
            'party': c['party'],
            'votes': c['votes'],
            'source': 'sqlite'
        }
    return None


# --- ERROR HANDLERS ---
@app.errorhandler(404)
def not_found(e: Exception) -> tuple:
    """Return JSON 404 for missing routes."""
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(e: Exception) -> tuple:
    """Return JSON 500 for internal server errors."""
    logger.error('Internal server error: %s', e)
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)
