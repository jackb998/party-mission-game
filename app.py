import datetime
import json
import os
import random
import re
import secrets
import sqlite3
import string
import time
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'data.db'))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
IMAGE_EXTENSIONS = tuple('.' + ext for ext in sorted(ALLOWED_EXTENSIONS))

# Themes and game modes an event can be built from.
THEMES = {
    'christmas': {'label': 'Christmas', 'icon': '🎄'},
    'birthday': {'label': 'Birthday', 'icon': '🎂'},
    'halloween': {'label': 'Halloween', 'icon': '🎃'},
    'party': {'label': 'Party', 'icon': '🎉'},
}
FEATURES = {
    'missions': 'Individual Missions',
    'group_missions': 'Group Missions',
    'secret_talent': 'Secret Talent',
    'tshirt': 'Voting',  # not offered on the landing page yet
}
DEFAULT_FEATURES = ['missions', 'group_missions']

CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no 0/O/1/I
CODE_LENGTH = 6
POINTS = {'easy': 5, 'medium': 7, 'hard': 10}
TALENT_POINTS = 15


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_text(value, max_len):
    return ' '.join((value or '').split())[:max_len]


def clean_name(value):
    return clean_text(value, 40)


def load_json(filename, default):
    try:
        with open(os.path.join(BASE_DIR, filename), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return default


GROUP_MISSIONS_ALL = load_json('group_missions.json', [])


def get_group_missions(theme):
    """Group missions for a theme: missions without a 'themes' key fit every theme."""
    result = []
    for table in GROUP_MISSIONS_ALL:
        missions = [m for m in table['missions'] if theme in m.get('themes', list(THEMES))]
        if missions:
            result.append({'table': table['table'], 'missions': missions})
    return result


def normalize_answer(text):
    """Normalise an answer for comparison (spaces, punctuation, case, common accents)"""
    if not text:
        return ""
    text = text.lower().strip()
    text = ' '.join(text.split())
    text = text.translate(str.maketrans('', '', string.punctuation))
    replacements = {'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e', 'à': 'a', 'â': 'a', 'î': 'i', 'ï': 'i', 'ô': 'o', 'û': 'u', 'ù': 'u', 'ç': 'c'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def check_riddle_answer(user_answer, correct_answer="A Christmas Tree"):
    """Check a riddle answer (fuzzy, multilingual) - used by the Christmas riddle."""
    user_norm = normalize_answer(user_answer)
    if not user_norm:
        return False

    accepted_answers = [
        "christmas tree", "xmas tree", "a christmas tree", "the christmas tree", "tree",
        "sapin", "sapin de noel", "un sapin", "le sapin", "sapin de noël", "arbre de noel", "arbre de noël",
        "albero di natale", "albero", "lalbero di natale",
        "weihnachtsbaum", "tannenbaum",
        "arbol de navidad", "árbol de navidad",
        "arvore de natal", "árvore de natal"
    ]
    accepted_normalized = [normalize_answer(ans) for ans in accepted_answers]
    if user_norm in accepted_normalized:
        return True

    keywords = ["tree", "sapin", "albero", "baum", "arbol", "arvore", "tannen", "weihnacht", "christmas", "noel", "natal", "natale", "navidad"]
    return any(kw in user_norm for kw in keywords)


# ==================== DATABASE ====================

def get_db_conn():
    return sqlite3.connect(DB_PATH, timeout=10)


def init_db():
    # A database from before events existed cannot be migrated in place: keep it aside.
    if os.path.exists(DB_PATH):
        conn = get_db_conn()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(participants)").fetchall()]
        conn.close()
        if cols and 'event_code' not in cols:
            stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            os.replace(DB_PATH, f"{DB_PATH}.legacy-{stamp}")

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            theme TEXT NOT NULL,
            features TEXT NOT NULL,
            host_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_code TEXT NOT NULL,
            name TEXT NOT NULL,
            secret_talent TEXT DEFAULT '',
            UNIQUE (event_code, name)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_code TEXT NOT NULL,
            name TEXT,
            difficulty TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_code TEXT NOT NULL,
            participant TEXT,
            mission_id INTEGER,
            filename TEXT,
            people_selected TEXT DEFAULT '',
            points INTEGER,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS talent_guesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_code TEXT NOT NULL,
            guesser TEXT,
            target TEXT,
            guessed_person TEXT,
            guessed_talent TEXT,
            correct INTEGER,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS group_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_code TEXT NOT NULL,
            participant TEXT,
            table_name TEXT,
            mission_id INTEGER,
            mission_name TEXT,
            completed INTEGER DEFAULT 0,
            riddle_answer TEXT DEFAULT '',
            photo_filename TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tshirt_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_code TEXT NOT NULL,
            voter TEXT,
            voted_for TEXT,
            timestamp TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_sub_event ON submissions (event_code, participant)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_gsub_event ON group_submissions (event_code, participant)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_guess_event ON talent_guesses (event_code, guesser)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_mission_event ON missions (event_code)")
    conn.commit()
    conn.close()


def get_event(code):
    conn = get_db_conn()
    row = conn.execute("SELECT code, name, theme, features, host_hash FROM events WHERE code=?", (code,)).fetchone()
    conn.close()
    if not row:
        return None
    theme = row[2] if row[2] in THEMES else 'party'
    try:
        features = [f for f in json.loads(row[3]) if f in FEATURES]
    except ValueError:
        features = list(DEFAULT_FEATURES)
    return {'code': row[0], 'name': row[1], 'theme': theme, 'icon': THEMES[theme]['icon'],
            'features': features, 'host_hash': row[4]}


def generate_code(conn):
    for _ in range(50):
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not conn.execute("SELECT 1 FROM events WHERE code=?", (code,)).fetchone():
            return code
    raise RuntimeError("Could not generate a free event code")


def seed_event_missions(cursor, code, theme):
    """Copy the missions that fit the theme into the new event."""
    missions = load_json('missions.json', [
        {"name": "Take a selfie with someone", "difficulty": "easy", "themes": ["party"]},
        {"name": "Dance with someone", "difficulty": "easy", "themes": ["party"]},
        {"name": "Make a funny video", "difficulty": "medium", "themes": ["party"]},
    ])
    rows = [(code, m['name'], m.get('difficulty', 'easy'))
            for m in missions if theme in m.get('themes', ['party'])]
    cursor.executemany("INSERT INTO missions (event_code, name, difficulty) VALUES (?,?,?)", rows)


def load_secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    path = os.path.join(BASE_DIR, '.secret_key')
    try:
        with open(path, 'r') as f:
            key = f.read().strip()
        if key:
            return key
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(path, 'w') as f:
            f.write(key)
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=30)
app.secret_key = load_secret_key()


# ==================== EVENT CONTEXT ====================

@app.url_value_preprocessor
def load_event(endpoint, values):
    """Routes under /e/<code>/ get their event loaded into g; `code` is not passed to the view."""
    g.event = None
    g.code = None
    if values and 'code' in values:
        event = get_event(str(values.pop('code')).upper())
        if not event:
            abort(404)
        g.event = event
        g.code = event['code']


@app.url_defaults
def add_event_code(endpoint, values):
    """url_for() inside an event fills in the event code automatically."""
    if 'code' in values or not g.get('code'):
        return
    if app.url_map.is_endpoint_expecting(endpoint, 'code'):
        values['code'] = g.code


@app.context_processor
def inject_event():
    event = g.get('event')
    if not event:
        return {}
    return {'event': event, 'game_features': event['features'],
            'game_theme': event['theme'], 'is_host': is_host()}


@app.errorhandler(404)
def not_found(_):
    return render_template('error.html', message="We couldn't find that page or game."), 404


@app.errorhandler(413)
def too_large(_):
    return render_template('error.html', message="That file is too big (16 MB maximum)."), 413


def skey(key):
    return f"{g.code}:{key}"


def sget(key, default=''):
    return session.get(skey(key), default)


def sset(key, value):
    session[skey(key)] = value
    session.permanent = True


def spop(key):
    session.pop(skey(key), None)


def is_host():
    return bool(g.get('code')) and session.get(skey('host')) is True


def host_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_host():
            flash('Please login first')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapper


def feature_required(feature):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if feature not in g.event['features']:
                flash("This game mode is not enabled for this event.")
                return redirect(url_for('index'))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def participant_exists(name):
    if not name:
        return False
    conn = get_db_conn()
    row = conn.execute("SELECT 1 FROM participants WHERE event_code=? AND name=?", (g.code, name)).fetchone()
    conn.close()
    return row is not None


def list_participants():
    conn = get_db_conn()
    rows = conn.execute("SELECT id, name, secret_talent FROM participants WHERE event_code=? ORDER BY name COLLATE NOCASE",
                        (g.code,)).fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'talent': r[2] or ''} for r in rows]


def get_current_user():
    """Current player of this event: from the URL or the session (only if they exist)."""
    name = clean_name(request.args.get('name', '')) or sget('current_user')
    return name if participant_exists(name) else ''


def save_photo(photo, *parts):
    ext = photo.filename.rsplit('.', 1)[1].lower()
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    safe = '_'.join(secure_filename(str(p).replace(' ', '_')) for p in parts)
    filename = f"{g.code}_{safe}_{stamp}.{ext}"
    photo.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def assign_random_missions(name, num_easy=3, num_medium=1, num_hard=1):
    conn = get_db_conn()
    all_missions = conn.execute("SELECT id, name, difficulty FROM missions WHERE event_code=?", (g.code,)).fetchall()
    conn.close()

    first_name = name.strip().split()[0]
    pattern = re.compile(re.escape(first_name), re.IGNORECASE)
    available = [m for m in all_missions if not pattern.search(m[1])]

    easy_selfie = [m for m in available if m[2] == 'easy' and "Take a selfie" in m[1]]
    easy_other = [m for m in available if m[2] == 'easy' and "Take a selfie" not in m[1]]
    medium = [m for m in available if m[2] == 'medium']
    hard = [m for m in available if m[2] == 'hard']

    selected = random.sample(easy_selfie, min(1, len(easy_selfie))) + \
        random.sample(easy_other, min(num_easy - 1, len(easy_other))) + \
        random.sample(medium, min(num_medium, len(medium))) + \
        random.sample(hard, min(num_hard, len(hard)))
    if not selected:
        selected = random.sample(available, min(5, len(available)))

    return [(m[0], m[1], m[2], POINTS.get(m[2], 10)) for m in selected]


# ==================== LANDING / CREATE / JOIN ====================

@app.route('/')
def welcome():
    """Landing page: join a game with a code, or create your own."""
    return render_template('welcome.html', features={k: v for k, v in FEATURES.items() if k != 'tshirt'})


@app.route('/create', methods=['POST'])
def create_event():
    name = clean_text(request.form.get('name', ''), 60) or 'Mission Game'
    theme = request.form.get('theme', 'party')
    if theme not in THEMES:
        theme = 'party'
    features = [f for f in request.form.getlist('features') if f in FEATURES and f != 'tshirt']
    if not features:
        features = list(DEFAULT_FEATURES)
    password = request.form.get('password', '')
    if len(password) < 4:
        flash("Choose a host password of at least 4 characters.")
        return redirect(url_for('welcome'))

    conn = get_db_conn()
    code = generate_code(conn)
    conn.execute("INSERT INTO events (code, name, theme, features, host_hash, created_at) VALUES (?,?,?,?,?,?)",
                 (code, name, theme, json.dumps(features), generate_password_hash(password),
                  datetime.datetime.now().isoformat()))
    seed_event_missions(conn.cursor(), code, theme)
    conn.commit()
    conn.close()

    session[f"{code}:host"] = True
    session.permanent = True
    return redirect(url_for('event_created', code=code))


@app.route('/join', methods=['GET', 'POST'])
def join():
    code = clean_text(request.values.get('code', ''), 12).upper()
    if get_event(code):
        return redirect(url_for('index', code=code))
    flash("We couldn't find a game with that code.")
    return redirect(url_for('welcome'))


@app.route('/e/<code>/created')
@host_required
def event_created():
    join_url = url_for('index', _external=True)
    return render_template('event_created.html', join_url=join_url)


# ==================== PLAYER AREA ====================

@app.route('/e/<code>/select', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = clean_name(request.form.get('name', ''))
        if not name:
            flash("Please enter your name")
            return redirect(url_for('index'))
        talent = clean_text(request.form.get('talent', ''), 200)
        conn = get_db_conn()
        conn.execute("INSERT OR IGNORE INTO participants (event_code, name, secret_talent) VALUES (?,?,?)",
                     (g.code, name, talent))
        if talent:
            conn.execute("UPDATE participants SET secret_talent=? WHERE event_code=? AND name=? AND COALESCE(secret_talent,'')=''",
                         (talent, g.code, name))
        conn.commit()
        conn.close()
        sset('current_user', name)
        return redirect(url_for('index'))

    name = get_current_user()
    if not name:
        spop('current_user')
        return render_template('index.html', participants=list_participants(),
                               ask_talent='secret_talent' in g.event['features'])
    sset('current_user', name)

    features = g.event['features']
    if 'missions' not in features:
        first = next((f for f in ('group_missions', 'secret_talent') if f in features), None)
        if first:
            return redirect(url_for(first, name=name))

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT mission_id, filename, people_selected, points FROM submissions WHERE event_code=? AND participant=?",
              (g.code, name))
    rows = c.fetchall()
    submissions = {}
    missions = []

    if not rows:
        for mid, mname, diff, points in assign_random_missions(name):
            c.execute("INSERT INTO submissions (event_code, participant, mission_id, filename, people_selected, points, timestamp) VALUES (?,?,?,?,?,?,?)",
                      (g.code, name, mid, "NOT COMPLETED", "", points, datetime.datetime.now().isoformat()))
            submissions[str(mid)] = {'filename': "NOT COMPLETED", 'points': points, 'people': []}
            missions.append((mid, mname, diff, points))
        conn.commit()
    else:
        for mid, filename, people_selected, points in rows:
            c.execute("SELECT name, difficulty FROM missions WHERE id=? AND event_code=?", (mid, g.code))
            mrow = c.fetchone()
            if mrow:
                missions.append((mid, mrow[0], mrow[1], points))
                people_list = [p.strip() for p in people_selected.split(',')] if people_selected else []
                submissions[str(mid)] = {'filename': filename, 'points': points, 'people': people_list}

    total_score = sum(submissions[str(m[0])]['points'] for m in missions
                      if submissions[str(m[0])]['filename'] != "NOT COMPLETED")
    conn.close()

    people = [p['name'] for p in list_participants() if p['name'] != name]
    return render_template('participant.html', name=name, missions=missions, submissions=submissions,
                           total_score=total_score, people=people)


@app.route('/e/<code>/submit_all', methods=['POST'])
@feature_required('missions')
def submit_all():
    name = clean_name(request.form.get('participant', ''))
    if not participant_exists(name):
        flash("Participant not found")
        return redirect(url_for('index'))
    conn = get_db_conn()
    c = conn.cursor()
    for key in request.form.keys():
        if not key.startswith("mission_"):
            continue
        mission_id = key.split("_")[1]
        c.execute("SELECT name, difficulty FROM missions WHERE id=? AND event_code=?", (mission_id, g.code))
        mission = c.fetchone()
        if not mission:
            continue
        points = POINTS.get(mission[1], 10)
        completed = request.form.get(f"completed_{mission_id}") == "on"

        if not completed:
            value = "NOT COMPLETED"
            people_str = ""
        else:
            people_selected = request.form.getlist(f"people_{mission_id}")
            people_str = ", ".join(people_selected) if people_selected else ""
            photo = request.files.get(f"photo_{mission_id}")
            if photo and photo.filename and allowed_file(photo.filename):
                value = save_photo(photo, name, f"mission{mission_id}")
            else:
                value = people_str if people_str else "COMPLETED"

        c.execute("SELECT id, filename FROM submissions WHERE event_code=? AND participant=? AND mission_id=?",
                  (g.code, name, mission_id))
        row = c.fetchone()
        if row:
            existing_filename = row[1]
            if value in ["COMPLETED", people_str] and existing_filename and existing_filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                value = existing_filename
            c.execute("UPDATE submissions SET filename=?, people_selected=?, points=?, timestamp=? WHERE id=?",
                      (value, people_str, points, datetime.datetime.now().isoformat(), row[0]))
        else:
            c.execute("INSERT INTO submissions (event_code, participant, mission_id, filename, people_selected, points, timestamp) VALUES (?,?,?,?,?,?,?)",
                      (g.code, name, mission_id, value, people_str, points, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("All missions submitted successfully!")
    return redirect(url_for('index', name=name))


@app.route('/e/<code>/autosave_mission', methods=['POST'])
@feature_required('missions')
def autosave_mission():
    """Auto-save a single mission via AJAX"""
    data = request.get_json(silent=True)
    if not data:
        return {'success': False, 'error': 'No data'}, 400

    name = clean_name(data.get('participant', ''))
    mission_id = data.get('mission_id')
    completed = data.get('completed', False)
    people_selected = data.get('people', [])
    if not participant_exists(name) or not mission_id:
        return {'success': False, 'error': 'Missing data'}, 400

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT name, difficulty FROM missions WHERE id=? AND event_code=?", (mission_id, g.code))
    mission = c.fetchone()
    if not mission:
        conn.close()
        return {'success': False, 'error': 'Mission not found'}, 404

    points = POINTS.get(mission[1], 10)
    people_str = ", ".join(clean_name(str(p)) for p in people_selected) if people_selected else ""

    c.execute("SELECT id, filename FROM submissions WHERE event_code=? AND participant=? AND mission_id=?", (g.code, name, mission_id))
    row = c.fetchone()
    if not completed:
        value = "NOT COMPLETED"
        people_str = ""
    elif row and row[1] and row[1].lower().endswith(IMAGE_EXTENSIONS):
        value = row[1]  # keep the uploaded photo
    else:
        value = people_str or "COMPLETED"

    if row:
        c.execute("UPDATE submissions SET filename=?, people_selected=?, points=?, timestamp=? WHERE id=?",
                  (value, people_str, points, datetime.datetime.now().isoformat(), row[0]))
    else:
        c.execute("INSERT INTO submissions (event_code, participant, mission_id, filename, people_selected, points, timestamp) VALUES (?,?,?,?,?,?,?)",
                  (g.code, name, mission_id, value, people_str, points, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return {'success': True, 'value': value, 'points': points}


@app.route('/e/<code>/autosave_group_mission', methods=['POST'])
@feature_required('group_missions')
def autosave_group_mission():
    """Auto-save a group mission via AJAX"""
    data = request.get_json(silent=True)
    if not data:
        return {'success': False, 'error': 'No data'}, 400

    name = clean_name(data.get('participant', ''))
    table = clean_text(data.get('table', ''), 60)
    mission_id = data.get('mission_id')
    completed = data.get('completed', False)
    riddle_answer = clean_text(data.get('riddle_answer', ''), 200)
    if not participant_exists(name) or not table or not mission_id:
        return {'success': False, 'error': 'Missing data'}, 400

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM group_submissions WHERE event_code=? AND participant=? AND table_name=? AND mission_id=?",
              (g.code, name, table, mission_id))
    row = c.fetchone()
    if row:
        c.execute("UPDATE group_submissions SET completed=?, riddle_answer=? WHERE id=?",
                  (1 if completed else 0, riddle_answer, row[0]))
    else:
        mission_name = ""
        for tm in get_group_missions(g.event['theme']):
            if tm['table'] == table:
                for m in tm['missions']:
                    if m['id'] == mission_id:
                        mission_name = m['name']
        c.execute("INSERT INTO group_submissions (event_code, participant, table_name, mission_id, mission_name, completed, riddle_answer) VALUES (?,?,?,?,?,?,?)",
                  (g.code, name, table, mission_id, mission_name, 1 if completed else 0, riddle_answer))
    conn.commit()
    conn.close()
    return {'success': True}


@app.route('/e/<code>/autosave_selection', methods=['POST'])
def autosave_selection():
    """Remember a dropdown choice (table, player, ...) in the session"""
    data = request.get_json(silent=True)
    if not data:
        return {'success': False, 'error': 'No data'}, 400

    selection_type = data.get('type', '')
    value = clean_text(str(data.get('value', '')), 80)
    keys = {'table': 'selected_table', 'player': 'selected_player', 'tshirt_vote': 'selected_tshirt_vote'}
    if selection_type not in keys:
        return {'success': False, 'error': 'Unknown selection type'}, 400
    sset(keys[selection_type], value)
    return {'success': True, 'saved': value}


@app.route('/e/<code>/restart')
def restart():
    """Forget the current player on this device so someone else can play"""
    for key in ('current_user', 'selected_table', 'selected_player', 'selected_tshirt_vote'):
        spop(key)
    return redirect(url_for('index'))


# ==================== SECRET TALENT ====================

@app.route('/e/<code>/secret_talent', methods=['GET', 'POST'])
@feature_required('secret_talent')
def secret_talent():
    name = get_current_user()
    if not name:
        flash("Please enter your name first")
        return redirect(url_for('index'))

    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, secret_talent FROM participants WHERE event_code=? AND secret_talent IS NOT NULL AND secret_talent != '' ORDER BY id",
              (g.code,))
    players_with_talent = [{'id': r[0], 'name': r[1], 'talent': r[2]} for r in c.fetchall()]
    players_names_sorted = sorted([p['name'] for p in players_with_talent], key=str.lower)

    if request.method == 'POST':
        try:
            player_id = int(request.form.get('player_id', '0'))
        except ValueError:
            player_id = 0
        guessed_person = clean_name(request.form.get('guessed_person', ''))
        player_data = next((p for p in players_with_talent if p['id'] == player_id), None)
        if player_data and guessed_person:
            c.execute("SELECT 1 FROM talent_guesses WHERE event_code=? AND guesser=? AND target=?",
                      (g.code, name, player_data['name']))
            if c.fetchone():
                flash("You already guessed this talent!")
            else:
                correct = 1 if guessed_person == player_data['name'] else 0
                c.execute("INSERT INTO talent_guesses (event_code, guesser, target, guessed_person, guessed_talent, correct, timestamp) VALUES (?,?,?,?,?,?,?)",
                          (g.code, name, player_data['name'], guessed_person, player_data['talent'], correct,
                           datetime.datetime.now().isoformat()))
                conn.commit()
                flash("Your guess has been recorded!")
        conn.close()
        return redirect(url_for('secret_talent', name=name))

    c.execute("SELECT guessed_talent, guessed_person, correct, target FROM talent_guesses WHERE event_code=? AND guesser=?",
              (g.code, name))
    previous_guesses = [{'talent': r[0], 'guessed_person': r[1], 'correct': r[2], 'target': r[3]} for r in c.fetchall()]
    conn.close()
    return render_template('secret_talent.html', name=name, players=players_with_talent,
                           players_names_sorted=players_names_sorted, previous_guesses=previous_guesses,
                           saved_player=sget('selected_player'))


# ==================== VOTING (not offered on the landing page yet) ====================

@app.route('/e/<code>/tshirt_voting')
@feature_required('tshirt')
def tshirt_voting():
    name = get_current_user()
    if not name:
        flash("Please enter your name first")
        return redirect(url_for('index'))

    conn = get_db_conn()
    row = conn.execute("SELECT voted_for FROM tshirt_votes WHERE event_code=? AND voter=?", (g.code, name)).fetchone()
    conn.close()
    return render_template('tshirt_voting.html', name=name, players=list_participants(), has_voted=row is not None,
                           voted_for=row[0] if row else None, saved_vote=sget('selected_tshirt_vote'))


@app.route('/e/<code>/submit_tshirt_vote', methods=['POST'])
@feature_required('tshirt')
def submit_tshirt_vote():
    name = clean_name(request.form.get('voter', ''))
    voted_for = clean_name(request.form.get('voted_for', ''))
    if not participant_exists(name) or not participant_exists(voted_for):
        flash("Missing information")
        return redirect(url_for('tshirt_voting'))

    conn = get_db_conn()
    if conn.execute("SELECT COUNT(*) FROM tshirt_votes WHERE event_code=? AND voter=?", (g.code, name)).fetchone()[0] > 0:
        flash("You have already voted!")
    else:
        conn.execute("INSERT INTO tshirt_votes (event_code, voter, voted_for, timestamp) VALUES (?,?,?,?)",
                     (g.code, name, voted_for, datetime.datetime.now().isoformat()))
        conn.commit()
        flash("Your vote has been recorded!")
    conn.close()
    return redirect(url_for('tshirt_voting', name=name))


# ==================== GROUP MISSIONS ====================

@app.route('/e/<code>/group_missions', methods=['GET', 'POST'])
@feature_required('group_missions')
def group_missions():
    force_select = request.args.get('force_select', '') == '1'
    name = clean_name(request.form.get('name', '')) or get_current_user()
    if not participant_exists(name):
        flash("Please enter your name first")
        return redirect(url_for('index'))
    sset('current_user', name)

    groups = get_group_missions(g.event['theme'])
    if force_select:
        table = clean_text(request.form.get('table', ''), 60)
    else:
        table = clean_text(request.form.get('table', '') or request.args.get('table', ''), 60) or sget('selected_table')

    if not table and not force_select:
        conn = get_db_conn()
        row = conn.execute("SELECT table_name FROM group_submissions WHERE event_code=? AND participant=? LIMIT 1",
                           (g.code, name)).fetchone()
        conn.close()
        if row:
            table = row[0]

    if table:
        sset('selected_table', table)

    if table:
        table_missions = next((tm['missions'] for tm in groups if tm['table'] == table), None)
        if not table_missions:
            flash("Table not found")
            spop('selected_table')
            return redirect(url_for('group_missions'))

        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT mission_id, completed, riddle_answer, photo_filename FROM group_submissions WHERE event_code=? AND participant=? AND table_name=?",
                  (g.code, name, table))
        submissions = {r[0]: {'completed': r[1], 'riddle_answer': r[2] or '', 'photo_filename': r[3] or ''} for r in c.fetchall()}

        if not submissions:
            for mission in table_missions:
                c.execute("INSERT INTO group_submissions (event_code, participant, table_name, mission_id, mission_name, completed, riddle_answer, photo_filename) VALUES (?,?,?,?,?,?,?,?)",
                          (g.code, name, table, mission['id'], mission['name'], 0, '', ''))
            conn.commit()
            submissions = {m['id']: {'completed': 0, 'riddle_answer': '', 'photo_filename': ''} for m in table_missions}
        conn.close()

        return render_template('group_missions.html', name=name, table=table, missions=table_missions,
                               submissions=submissions, tables=[tm['table'] for tm in groups])

    return render_template('group_missions_select.html', tables=[tm['table'] for tm in groups],
                           name=name, saved_table=sget('selected_table'))


@app.route('/e/<code>/change_table')
@feature_required('group_missions')
def change_table():
    spop('selected_table')
    return redirect(url_for('group_missions', force_select='1'))


@app.route('/e/<code>/submit_group_missions', methods=['POST'])
@feature_required('group_missions')
def submit_group_missions():
    name = clean_name(request.form.get('participant', ''))
    table = clean_text(request.form.get('table', ''), 60)
    if not participant_exists(name) or not table:
        flash("Missing information")
        return redirect(url_for('group_missions'))

    valid_ids = set()
    for tm in get_group_missions(g.event['theme']):
        if tm['table'] == table:
            valid_ids = {m['id'] for m in tm['missions']}

    conn = get_db_conn()
    c = conn.cursor()
    for key in request.form.keys():
        if not key.startswith("completed_"):
            continue
        try:
            mission_id = int(key.split("_")[1])
        except ValueError:
            continue
        if mission_id not in valid_ids:
            continue
        completed = request.form.get(key) == "on"

        photo_filename = ""
        photo = request.files.get(f"photo_{mission_id}")
        if photo and photo.filename and allowed_file(photo.filename):
            photo_filename = save_photo(photo, name, table, f"mission{mission_id}")

        c.execute("SELECT photo_filename FROM group_submissions WHERE event_code=? AND participant=? AND table_name=? AND mission_id=?",
                  (g.code, name, table, mission_id))
        row = c.fetchone()
        existing_photo = row[0] if row and row[0] else ""
        c.execute("UPDATE group_submissions SET completed=?, photo_filename=? WHERE event_code=? AND participant=? AND table_name=? AND mission_id=?",
                  (1 if completed else 0, photo_filename or existing_photo, g.code, name, table, mission_id))
    conn.commit()
    conn.close()

    flash("Group missions updated successfully!")
    return redirect(url_for('group_missions', name=name, table=table))


# ==================== HOST AREA ====================

_failed_logins = {}


def too_many_attempts(key):
    now = time.time()
    recent = [t for t in _failed_logins.get(key, []) if now - t < 600]
    _failed_logins[key] = recent
    return len(recent) >= 10


@app.route('/e/<code>/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        key = (request.remote_addr, g.code)
        if too_many_attempts(key):
            flash('Too many attempts. Try again in a few minutes.')
        elif check_password_hash(g.event['host_hash'], request.form.get('password', '')):
            sset('host', True)
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            _failed_logins.setdefault(key, []).append(time.time())
            flash('Invalid password')
    return render_template('login.html')


@app.route('/e/<code>/logout')
def logout():
    spop('host')
    flash('Logged out successfully')
    return redirect(url_for('login'))


def event_score_rows(c):
    """Raw data of the event used by dashboard and leaderboard."""
    c.execute("SELECT DISTINCT participant FROM submissions WHERE event_code=? ORDER BY participant", (g.code,))
    participants = [r[0] for r in c.fetchall()]
    return participants


def group_mission_info(theme):
    info = {}
    for tm in get_group_missions(theme):
        for m in tm['missions']:
            info[(tm['table'], m['id'])] = m
    return info


@app.route('/e/<code>/dashboard')
@host_required
def dashboard():
    conn = get_db_conn()
    c = conn.cursor()
    participants = event_score_rows(c)

    c.execute("SELECT id, name, difficulty FROM missions WHERE event_code=? ORDER BY id", (g.code,))
    missions = {r[0]: {'name': r[1], 'difficulty': r[2]} for r in c.fetchall()}

    c.execute("SELECT participant, mission_id, filename, people_selected, points FROM submissions WHERE event_code=?", (g.code,))
    submissions = c.fetchall()

    c.execute("SELECT guesser, target, guessed_person, guessed_talent, correct, timestamp FROM talent_guesses WHERE event_code=? ORDER BY timestamp", (g.code,))
    talent_guesses = c.fetchall()

    c.execute("SELECT participant, table_name, mission_id, mission_name, completed, riddle_answer, photo_filename FROM group_submissions WHERE event_code=?", (g.code,))
    group_submissions = c.fetchall()

    c.execute("SELECT voter, voted_for, timestamp FROM tshirt_votes WHERE event_code=?", (g.code,))
    tshirt_votes = c.fetchall()
    conn.close()

    participant_data = {}
    for participant in participants:
        participant_data[participant] = {
            'total_score': 0, 'individual_score': 0, 'group_score': 0, 'talent_score': 0,
            'missions': {}, 'group_missions': {}, 'talent_guesses': [],
            'tshirt_votes_received': 0, 'voted_for': None
        }

    for participant, mission_id, filename, people_selected, points in submissions:
        if participant in participant_data:
            if filename != 'NOT COMPLETED':
                participant_data[participant]['individual_score'] += points
                participant_data[participant]['total_score'] += points
            participant_data[participant]['missions'][mission_id] = {
                'filename': filename,
                'people_selected': people_selected or '',
                'points': points,
                'mission_name': missions.get(mission_id, {}).get('name', 'Unknown')
            }

    group_info = group_mission_info(g.event['theme'])
    for participant, table_name, mission_id, mission_name, completed, riddle_answer, photo_filename in group_submissions:
        if participant not in participant_data:
            continue
        mission = group_info.get((table_name, mission_id), {})
        points = mission.get('points', 0)
        has_riddle = 'riddle' in mission

        riddle_correct = None
        if has_riddle:
            riddle_correct = check_riddle_answer(riddle_answer) if riddle_answer else False
            if completed and riddle_correct:
                participant_data[participant]['group_score'] += points
                participant_data[participant]['total_score'] += points
        elif completed:
            participant_data[participant]['group_score'] += points
            participant_data[participant]['total_score'] += points

        participant_data[participant]['group_missions'].setdefault(table_name, []).append({
            'mission_name': mission_name,
            'points': points,
            'completed': completed,
            'riddle_answer': riddle_answer or '',
            'riddle_correct': riddle_correct,
            'has_riddle': has_riddle,
            'photo_filename': photo_filename or ''
        })

    for guesser, target, guessed_person, guessed_talent, correct, timestamp in talent_guesses:
        if guesser in participant_data:
            participant_data[guesser]['talent_guesses'].append({
                'target': target, 'guessed_person': guessed_person, 'talent': guessed_talent,
                'correct': correct, 'timestamp': timestamp
            })
            if correct:
                participant_data[guesser]['talent_score'] += TALENT_POINTS
                participant_data[guesser]['total_score'] += TALENT_POINTS

    for voter, voted_for, timestamp in tshirt_votes:
        if voter in participant_data:
            participant_data[voter]['voted_for'] = voted_for
        if voted_for in participant_data:
            participant_data[voted_for]['tshirt_votes_received'] += 1

    return render_template('dashboard.html', participant_data=participant_data, missions=missions,
                           players=list_participants())


# ==================== ADMIN ERASE ROUTES ====================

def erase(tables, participant):
    conn = get_db_conn()
    for table, column in tables:
        conn.execute(f"DELETE FROM {table} WHERE event_code=? AND {column}=?", (g.code, participant))
    conn.commit()
    conn.close()


@app.route('/e/<code>/admin/erase_all/<participant>')
@host_required
def erase_all(participant):
    erase([('submissions', 'participant'), ('group_submissions', 'participant'),
           ('talent_guesses', 'guesser'), ('tshirt_votes', 'voter')], participant)
    flash(f"All data for {participant} has been erased!")
    return redirect(url_for('dashboard'))


@app.route('/e/<code>/admin/erase_individual/<participant>')
@host_required
def erase_individual(participant):
    erase([('submissions', 'participant')], participant)
    flash(f"Individual missions for {participant} have been erased!")
    return redirect(url_for('dashboard'))


@app.route('/e/<code>/admin/erase_group/<participant>')
@host_required
def erase_group(participant):
    erase([('group_submissions', 'participant')], participant)
    flash(f"Group missions for {participant} have been erased!")
    return redirect(url_for('dashboard'))


@app.route('/e/<code>/admin/erase_talent/<participant>')
@host_required
def erase_talent(participant):
    erase([('talent_guesses', 'guesser')], participant)
    flash(f"Secret talent guesses for {participant} have been erased!")
    return redirect(url_for('dashboard'))


@app.route('/e/<code>/admin/erase_vote/<participant>')
@host_required
def erase_vote(participant):
    erase([('tshirt_votes', 'voter')], participant)
    flash(f"Vote by {participant} has been erased!")
    return redirect(url_for('dashboard'))


@app.route('/e/<code>/admin/erase_all_data')
@host_required
def erase_all_data():
    conn = get_db_conn()
    for table in ('submissions', 'group_submissions', 'talent_guesses', 'tshirt_votes'):
        conn.execute(f"DELETE FROM {table} WHERE event_code=?", (g.code,))
    conn.commit()
    conn.close()
    flash("⚠️ ALL GAME DATA has been erased!")
    return redirect(url_for('dashboard'))


# ==================== LEADERBOARD ====================

TIEBREAK_QUESTIONS = [
    {'question': "How many continents are there?", 'answer': "7"},
    {'question': "What is the chemical symbol for gold?", 'answer': "Au"},
    {'question': "In which year did humans first land on the Moon?", 'answer': "1969"},
]


@app.route('/e/<code>/leaderboard')
@host_required
def leaderboard():
    conn = get_db_conn()
    c = conn.cursor()
    participants = event_score_rows(c)

    c.execute("SELECT participant, mission_id, filename, points FROM submissions WHERE event_code=?", (g.code,))
    submissions = c.fetchall()
    c.execute("SELECT participant, table_name, mission_id, completed, riddle_answer FROM group_submissions WHERE event_code=?", (g.code,))
    group_submissions = c.fetchall()
    c.execute("SELECT guesser, correct FROM talent_guesses WHERE event_code=?", (g.code,))
    talent_guesses = c.fetchall()
    c.execute("SELECT voted_for, COUNT(*) AS votes FROM tshirt_votes WHERE event_code=? GROUP BY voted_for ORDER BY votes DESC", (g.code,))
    tshirt_results = c.fetchall()
    conn.close()

    scores = {p: {'individual': 0, 'group': 0, 'talent': 0, 'total': 0, 'missions_completed': 0} for p in participants}

    for participant, mission_id, filename, points in submissions:
        if participant in scores and filename != 'NOT COMPLETED':
            scores[participant]['individual'] += points
            scores[participant]['missions_completed'] += 1

    group_info = group_mission_info(g.event['theme'])
    for participant, table_name, mission_id, completed, riddle_answer in group_submissions:
        if participant in scores and completed:
            mission = group_info.get((table_name, mission_id))
            if not mission:
                continue
            if 'riddle' in mission and not (riddle_answer and check_riddle_answer(riddle_answer)):
                continue
            scores[participant]['group'] += mission['points']
            scores[participant]['missions_completed'] += 1

    for guesser, correct in talent_guesses:
        if guesser in scores and correct:
            scores[guesser]['talent'] += TALENT_POINTS

    for data in scores.values():
        data['total'] = data['individual'] + data['group'] + data['talent']

    manual_winner = sget('manual_winner', None)

    def sort_key(item):
        participant, data = item
        return (1 if participant == manual_winner else 0, data['total'], data['missions_completed'])

    sorted_scores = sorted(scores.items(), key=sort_key, reverse=True)

    tied_participants = []
    if len(sorted_scores) >= 2 and not manual_winner:
        top = sorted_scores[0][1]
        tied_participants = [p for p, d in sorted_scores
                             if d['total'] == top['total'] and d['missions_completed'] == top['missions_completed']]
        if len(tied_participants) <= 1:
            tied_participants = []

    leaderboard_data = {
        'labels': [p[0] for p in sorted_scores],
        'individual_scores': [p[1]['individual'] for p in sorted_scores],
        'group_scores': [p[1]['group'] for p in sorted_scores],
        'total_scores': [p[1]['total'] for p in sorted_scores]
    }
    tshirt_data = {'labels': [r[0] for r in tshirt_results], 'votes': [r[1] for r in tshirt_results]}

    return render_template('leaderboard.html', leaderboard_data=leaderboard_data, tshirt_data=tshirt_data,
                           sorted_scores=sorted_scores, tshirt_results=tshirt_results,
                           tied_participants=tied_participants, manual_winner=manual_winner,
                           quiz_questions=TIEBREAK_QUESTIONS)


@app.route('/e/<code>/mark_winner/<participant>')
@host_required
def mark_winner(participant):
    sset('manual_winner', participant)
    flash(f"🏆 {participant} has been marked as the winner!")
    return redirect(url_for('leaderboard'))


@app.route('/e/<code>/clear_winner')
@host_required
def clear_winner():
    spop('manual_winner')
    flash("Winner selection has been cleared.")
    return redirect(url_for('leaderboard'))


# ==================== PHOTOS ====================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/e/<code>/pictures')
@host_required
def pictures():
    """Gallery of all photos uploaded in this event"""
    image_filter = "(%s LIKE '%%.jpg' OR %s LIKE '%%.jpeg' OR %s LIKE '%%.png' OR %s LIKE '%%.gif' OR %s LIKE '%%.webp')"
    conn = get_db_conn()
    c = conn.cursor()

    c.execute(f"""
        SELECT s.participant, s.mission_id, s.filename, s.timestamp, m.name
        FROM submissions s
        JOIN missions m ON s.mission_id = m.id
        WHERE s.event_code = ? AND {image_filter % (('s.filename',) * 5)}
        ORDER BY s.timestamp DESC
    """, (g.code,))
    photos = []
    for participant, mission_id, filename, timestamp, mission_name in c.fetchall():
        if os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
            photos.append({'participant': participant, 'mission_id': mission_id, 'filename': filename,
                           'timestamp': timestamp, 'mission_name': mission_name, 'type': 'individual'})

    c.execute(f"""
        SELECT participant, mission_id, mission_name, photo_filename, table_name
        FROM group_submissions
        WHERE event_code = ? AND {image_filter % (('photo_filename',) * 5)}
    """, (g.code,))
    for participant, mission_id, mission_name, filename, table_name in c.fetchall():
        if os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
            photos.append({'participant': participant, 'mission_id': mission_id, 'filename': filename,
                           'timestamp': '', 'mission_name': f"{mission_name} ({table_name})", 'type': 'group'})
    conn.close()
    return render_template('pictures.html', photos=photos)


init_db()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    # The Werkzeug debugger must never be reachable from the network.
    debug = os.environ.get('FLASK_ENV') != 'production' and host in ('127.0.0.1', 'localhost')
    app.run(host=host, port=port, debug=debug)
