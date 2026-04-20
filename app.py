import os
import sqlite3
import random
import string
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g, session, send_file, make_response

app = Flask(__name__)
app.secret_key = 'super_secret_cyfocus_key'
DATABASE = 'voting.db'

# --- FIREBASE INTEGRATION ---
try:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
    db_firestore = firestore.client()
    print("Firebase Initialized Successfully!")
except Exception as e:
    print(f"Firebase Init Error: {e}")
    db_firestore = None

def log_system_active():
    if db_firestore:
        try:
            doc_ref = db_firestore.collection('system_logs').document('heartbeat')
            doc_ref.set({
                'status': 'ONLINE',
                'last_pulse': datetime.now(),
                'server': 'Local-Development-Node'
            })
            print("Firebase Heartbeat Sent!")
        except Exception as e:
            print(f"Firebase Heartbeat Error: {e}")

log_system_active()

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def log_event(log_type, message):
    db = get_db()
    db.execute('INSERT INTO logs (type, message) VALUES (?, ?)', (log_type, message))
    db.commit()

def init_db():
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
            except:
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

        # Log to local DB
        log_event('attack_happened', f'THREAT: Malicious Input Detected | IP: {masked_ip} | Path: {request.path}')

        # Log to Firebase for Live Threat Telemetry
        if db_firestore:
            try:
                db_firestore.collection('hack_attempts').add({
                    'type': 'Malicious Input Detected',
                    'ip_masked': masked_ip,
                    'timestamp': datetime.now(),
                    'path': request.path,
                    'payload_signature': 'BLOCKED'
                })
            except Exception as e:
                print(f"Firebase hack log error: {e}")

        return "Security Violation Logged.", 403

@app.before_request
def log_request_info():
    if request.path == '/' and request.method == 'GET':
        log_event('changes_happened', 'Main Route Accessed')

@app.route('/')
def index():
    response = make_response(render_template('index.html'))
    # Efficiency Boost: Cache static elements for 5 minutes for mobile low-bandwidth networks
    response.headers['Cache-Control'] = 'public, max-age=300'
    return response

@app.route('/api/map')
def api_map():
    return send_file('static/tn_map_processed.svg', mimetype='image/svg+xml')

def generate_mock_details(c):
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
def api_data():
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
def api_request_otp():
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
    session['pending_user'] = {'name': name, 'mobile': mobile, 'otp': otp}
    
    log_event('changes_happened', f"Generated OTP for {name}: {otp}")
    return jsonify({'success': True, 'message': 'OTP generated. Check System Heartbeat logs.'})

@app.route('/api/verify_otp', methods=['POST'])
def api_verify_otp():
    data = request.json
    otp_submitted = data.get('otp', '').strip()
    
    pending = session.get('pending_user')
    if not pending:
        return jsonify({'error': 'No pending authentication'}), 400
        
    if otp_submitted == pending['otp']:
        session['user'] = {'name': pending['name'], 'mobile': pending['mobile']}
        log_event('changes_happened', f"Identity Verified for {pending['name']}")
        return jsonify({'success': True})
    else:
        log_event('attack_happened', f"THREAT: Invalid OTP | {pending['name']} | {datetime.now().isoformat()}")
        return jsonify({'error': 'Invalid OTP'}), 401

@app.route('/api/vote', methods=['POST'])
def api_vote():
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
                print(f"Firebase Vote Sync Error: {e}")
        
        # Clear session to prevent multiple votes
        session.pop('user', None)
        session.pop('pending_user', None)
        
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        log_event('attack_happened', f"THREAT: Duplicate Vote Attempt | {name} | {datetime.now().isoformat()}")
        return jsonify({'error': 'You have already voted!'}), 403

@app.route('/api/source')
def api_source():
    try:
        with open(__file__, 'r') as f:
            source = f.read()
        return jsonify({'source': source})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_logs')
def api_download_logs():
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
    
    from flask import Response
    return Response(
        content,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename=ledger_logic_{log_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'}
    )

# --- TELECASTING: Live Count Endpoint (High-Efficiency, Lightweight) ---
@app.route('/api/live-count')
def api_live_count():
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
            print(f"Telecast sync error: {e}")
    
    return jsonify({'total_votes': total, 'status': 'live'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
