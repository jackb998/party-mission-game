import random
import re
import os
import sqlite3
import datetime
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

# Load people and talents from JSON
def load_people():
    try:
        people_file = os.path.join(os.path.dirname(__file__), 'people.json')
        with open(people_file, 'r', encoding='utf-8') as f:
            people_data = json.load(f)
        PEOPLE = [p['name'] for p in people_data]
        SECRET_TALENTS = [p['talent'] for p in people_data]
        return PEOPLE, SECRET_TALENTS
    except Exception as e:
        print(f"Errore caricamento people.json: {e}")
        return [], []

def load_players():
    try:
        people_file = os.path.join(os.path.dirname(__file__), 'people.json')
        with open(people_file, 'r', encoding='utf-8') as f:
            people_data = json.load(f)
        players_list = []
        for i, p in enumerate(people_data):
            players_list.append({
                'id': i + 1,
                'name': p['name'],
                'talent': p['talent']
            })
        return players_list
    except Exception as e:
        print(f"Errore caricamento players da people.json: {e}")
        return []

def load_group_missions():
    try:
        gm_file = os.path.join(os.path.dirname(__file__), 'group_missions.json')
        with open(gm_file, 'r', encoding='utf-8') as f:
            group_missions_data = json.load(f)
        return group_missions_data
    except Exception as e:
        print(f"Errore caricamento group_missions.json: {e}")
        return []

PEOPLE, SECRET_TALENTS = load_people()
PLAYERS = load_players()
GROUP_MISSIONS = load_group_missions()

def normalize_answer(text):
    """Normalizza una risposta per il confronto (rimuove spazi extra, punteggiatura, lowercase)"""
    if not text:
        return ""
    import string
    # Lowercase, rimuovi spazi extra, rimuovi punteggiatura comune
    text = text.lower().strip()
    text = ' '.join(text.split())  # Rimuove spazi multipli
    text = text.translate(str.maketrans('', '', string.punctuation))  # Rimuove punteggiatura
    # Normalizza accenti comuni
    replacements = {'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e', 'à': 'a', 'â': 'a', 'î': 'i', 'ï': 'i', 'ô': 'o', 'û': 'u', 'ù': 'u', 'ç': 'c'}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def check_riddle_answer(user_answer, correct_answer="A Christmas Tree"):
    """Verifica se la risposta dell'utente è corretta (fuzzy matching, multilingua)"""
    user_norm = normalize_answer(user_answer)
    
    if not user_norm:
        return False
    
    # Risposte accettate in diverse lingue
    accepted_answers = [
        # English
        "christmas tree", "xmas tree", "a christmas tree", "the christmas tree", "tree",
        # French
        "sapin", "sapin de noel", "un sapin", "le sapin", "sapin de noël", "arbre de noel", "arbre de noël",
        # Italian
        "albero di natale", "albero", "lalbero di natale",
        # German
        "weihnachtsbaum", "tannenbaum",
        # Spanish
        "arbol de navidad", "árbol de navidad",
        # Portuguese
        "arvore de natal", "árvore de natal"
    ]
    
    # Normalizza tutte le risposte accettate
    accepted_normalized = [normalize_answer(ans) for ans in accepted_answers]
    
    # Match esatto
    if user_norm in accepted_normalized:
        return True
    
    # Controlla se contiene una parola chiave
    keywords = ["tree", "sapin", "albero", "baum", "arbol", "arvore", "tannen", "weihnacht", "christmas", "noel", "natal", "natale", "navidad"]
    for kw in keywords:
        if kw in user_norm:
            return True
    
    return False

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            secret_talent TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            difficulty TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant TEXT,
            mission_id INTEGER,
            filename TEXT,
            points INTEGER,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS talent_guesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            participant TEXT,
            table_name TEXT,
            mission_id INTEGER,
            mission_name TEXT,
            completed INTEGER DEFAULT 0,
            riddle_answer TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tshirt_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter TEXT,
            voted_for TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_db_conn():
    return sqlite3.connect(DB_PATH)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.environ.get('SECRET_KEY', 'christmas-mission-game-2024-secret-key-jbh')

def load_sample_missions(force_reload=False):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM missions")
    count = c.fetchone()[0]
    conn.close()
    
    if count == 0 or force_reload:
        conn = get_db_conn()
        c = conn.cursor()
        if force_reload:
            c.execute("DELETE FROM missions")
        
        try:
            missions_file = os.path.join(os.path.dirname(__file__), 'missions.json')
            with open(missions_file, 'r', encoding='utf-8') as f:
                missions = json.load(f)
        except Exception as e:
            print(f"Errore caricamento missions.json: {e}")
            missions = [
                {"name": "Take a selfie with someone", "difficulty": "easy"},
                {"name": "Take a selfie in front of a landmark", "difficulty": "easy"},
                {"name": "Dance with someone", "difficulty": "easy"},
                {"name": "Find someone with same zodiac sign", "difficulty": "easy"},
                {"name": "Make a funny video", "difficulty": "medium"},
            ]
        
        for m in missions:
            c.execute("INSERT INTO missions (name, difficulty) VALUES (?,?)",
                      (m['name'], m.get('difficulty', 'easy')))
        conn.commit()
        conn.close()

def assign_random_missions(name, num_easy=3, num_medium=1, num_hard=1):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, difficulty FROM missions")
    all_missions = c.fetchall()
    conn.close()

    first_name = name.strip().split()[0]
    pattern = re.compile(re.escape(first_name), re.IGNORECASE)
    available = [m for m in all_missions if not pattern.search(m[1])]

    easy_selfie = [m for m in available if m[2]=='easy' and "Take a selfie" in m[1]]
    easy_other = [m for m in available if m[2]=='easy' and "Take a selfie" not in m[1]]
    medium = [m for m in available if m[2]=='medium']
    hard = [m for m in available if m[2]=='hard']

    try:
        selected = random.sample(easy_selfie, min(1, len(easy_selfie))) + \
                   random.sample(easy_other, min(num_easy-1, len(easy_other))) + \
                   random.sample(medium, min(num_medium, len(medium))) + \
                   random.sample(hard, min(num_hard, len(hard)))
    except ValueError:
        selected = random.sample(available, min(5, len(available)))

    missions_with_points = []
    for m in selected:
        points = 5 if m[2]=="easy" else 7 if m[2]=="medium" else 10
        missions_with_points.append((m[0], m[1], m[2], points))
    
    return missions_with_points

@app.route('/', methods=['GET','POST'])
def index():
    # Controlla se c'è un nome in POST, GET o sessione
    if request.method=='POST' or request.args.get('name') or session.get('current_user'):
        name = request.form.get('name', '') or request.args.get('name', '') or session.get('current_user', '')
        name = name.strip()
        if not name:
            flash("Please select your name")
            return redirect(url_for('index'))

        session['current_user'] = name

        conn = get_db_conn()
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM participants WHERE name=?", (name,))
        exists = c.fetchone()[0]
        if not exists:
            try:
                idx = PEOPLE.index(name)
                talent = SECRET_TALENTS[idx] if idx < len(SECRET_TALENTS) else ""
            except ValueError:
                talent = ""
            c.execute("INSERT INTO participants (name, secret_talent) VALUES (?,?)",
                      (name, talent))
            conn.commit()

        c.execute("SELECT mission_id, filename, points FROM submissions WHERE participant=?", (name,))
        rows = c.fetchall()
        submissions = {}
        missions = []
        
        if not rows:
            random_missions = assign_random_missions(name)
            for m in random_missions:
                mid, mname, diff, points = m
                c.execute("INSERT INTO submissions (participant,mission_id,filename,points,timestamp) VALUES (?,?,?,?,?)",
                          (name, mid, "NOT COMPLETED", points, datetime.datetime.now().isoformat()))
                submissions[str(mid)] = {'filename':"NOT COMPLETED",'points':points}
                missions.append((mid, mname, diff, points))
            conn.commit()
        else:
            for row in rows:
                mid, filename, points = row
                c.execute("SELECT name, difficulty FROM missions WHERE id=?", (mid,))
                mrow = c.fetchone()
                if mrow:
                    mname, diff = mrow
                    missions.append((mid, mname, diff, points))
                    submissions[str(mid)] = {'filename':filename,'points':points}

        total_score = sum(submissions[str(m[0])]['points'] for m in missions if submissions[str(m[0])]['filename']!="NOT COMPLETED")
        conn.close()
        
        print(f"DEBUG: name={name}, passing to template")
        return render_template('participant.html', name=name, missions=missions, submissions=submissions, total_score=total_score, people=PEOPLE)

    return render_template('index.html', people=PEOPLE)

@app.route('/submit_all', methods=['POST'])
def submit_all():
    name = request.form.get('participant','').strip()
    if not name:
        flash("Participant name missing")
        return redirect(url_for('index'))
    conn = get_db_conn()
    c = conn.cursor()
    for key in request.form.keys():
        if key.startswith("mission_"):
            mission_id = key.split("_")[1]
            c.execute("SELECT name, difficulty FROM missions WHERE id=?", (mission_id,))
            mission = c.fetchone()
            if not mission:
                continue
            mname, diff = mission
            points = 5 if diff=="easy" else 7 if diff=="medium" else 10
            completed = request.form.get(f"completed_{mission_id}")=="on"

            if not completed:
                value = "NOT COMPLETED"
            else:
                # Raccogliere tutte le persone selezionate per questa missione
                people_selected = request.form.getlist(f"people_{mission_id}")
                if people_selected:
                    value = ", ".join(people_selected)
                else:
                    value = "COMPLETED"
            
            c.execute("SELECT id FROM submissions WHERE participant=? AND mission_id=?", (name, mission_id))
            row = c.fetchone()
            if row:
                c.execute("UPDATE submissions SET filename=?, points=?, timestamp=? WHERE id=?",
                          (value, points, datetime.datetime.now().isoformat(), row[0]))
            else:
                c.execute("INSERT INTO submissions (participant,mission_id,filename,points,timestamp) VALUES (?,?,?,?,?)",
                          (name, mission_id, value, points, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("All missions submitted successfully!")
    return redirect(url_for('index') + f"?name={name}")

@app.route('/autosave_mission', methods=['POST'])
def autosave_mission():
    """Auto-save singola missione via AJAX"""
    data = request.get_json()
    if not data:
        return {'success': False, 'error': 'No data'}, 400
    
    name = data.get('participant', '').strip()
    mission_id = data.get('mission_id')
    completed = data.get('completed', False)
    people_selected = data.get('people', [])
    
    if not name or not mission_id:
        return {'success': False, 'error': 'Missing data'}, 400
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get mission info
    c.execute("SELECT name, difficulty FROM missions WHERE id=?", (mission_id,))
    mission = c.fetchone()
    if not mission:
        conn.close()
        return {'success': False, 'error': 'Mission not found'}, 404
    
    mname, diff = mission
    points = 5 if diff == "easy" else 7 if diff == "medium" else 10
    
    if not completed:
        value = "NOT COMPLETED"
    else:
        if people_selected:
            value = ", ".join(people_selected)
        else:
            value = "COMPLETED"
    
    # Update or insert
    c.execute("SELECT id FROM submissions WHERE participant=? AND mission_id=?", (name, mission_id))
    row = c.fetchone()
    if row:
        c.execute("UPDATE submissions SET filename=?, points=?, timestamp=? WHERE id=?",
                  (value, points, datetime.datetime.now().isoformat(), row[0]))
    else:
        c.execute("INSERT INTO submissions (participant,mission_id,filename,points,timestamp) VALUES (?,?,?,?,?)",
                  (name, mission_id, value, points, datetime.datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {'success': True, 'value': value, 'points': points}

@app.route('/autosave_group_mission', methods=['POST'])
def autosave_group_mission():
    """Auto-save gruppo missione via AJAX"""
    data = request.get_json()
    if not data:
        return {'success': False, 'error': 'No data'}, 400
    
    name = data.get('participant', '').strip()
    table = data.get('table', '').strip()
    mission_id = data.get('mission_id')
    completed = data.get('completed', False)
    riddle_answer = data.get('riddle_answer', '').strip()
    
    if not name or not table or not mission_id:
        return {'success': False, 'error': 'Missing data'}, 400
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Check if submission exists
    c.execute("SELECT id FROM group_submissions WHERE participant=? AND table_name=? AND mission_id=?", 
              (name, table, mission_id))
    row = c.fetchone()
    
    if row:
        c.execute("UPDATE group_submissions SET completed=?, riddle_answer=? WHERE id=?",
                  (1 if completed else 0, riddle_answer, row[0]))
    else:
        # Get mission name from GROUP_MISSIONS
        mission_name = ""
        for tm in GROUP_MISSIONS:
            if tm['table'] == table:
                for m in tm['missions']:
                    if m['id'] == mission_id:
                        mission_name = m['name']
                        break
        
        c.execute("INSERT INTO group_submissions (participant, table_name, mission_id, mission_name, completed, riddle_answer) VALUES (?,?,?,?,?,?)",
                  (name, table, mission_id, mission_name, 1 if completed else 0, riddle_answer))
    
    conn.commit()
    conn.close()
    
    return {'success': True}

@app.route('/autosave_selection', methods=['POST'])
def autosave_selection():
    """Auto-save selezione dropdown (tavolo, player, etc.) nella sessione"""
    data = request.get_json()
    if not data:
        return {'success': False, 'error': 'No data'}, 400
    
    selection_type = data.get('type', '')
    value = data.get('value', '')
    
    if selection_type == 'table':
        session['selected_table'] = value
    elif selection_type == 'player':
        session['selected_player'] = value
    elif selection_type == 'tshirt_vote':
        session['selected_tshirt_vote'] = value
    else:
        return {'success': False, 'error': 'Unknown selection type'}, 400
    
    return {'success': True, 'saved': value}

def get_current_user():
    """Ottieni il nome dell'utente corrente da URL o sessione"""
    name = request.args.get('name', '') or session.get('current_user', '')
    return name.strip()

@app.route('/secret_talent', methods=['GET','POST'])
def secret_talent():
    name = get_current_user()
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Filtra solo i player che hanno un talento (non vuoto)
    players_with_talent = [p for p in PLAYERS if p.get('talent', '').strip()]
    
    if request.method=='POST':
        guesser = request.form.get('guesser','')
        player_id = int(request.form.get('player_id','0'))
        guessed_person = request.form.get('guessed_person','')
        if guesser and player_id and guessed_person:
            # Trova il player nella lista filtrata
            player_data = next((p for p in players_with_talent if p['id'] == player_id), None)
            if player_data:
                player_name = player_data['name']  # Chi ha veramente quel talento
                talent = player_data['talent']
                correct = 1 if guessed_person == player_name else 0
                c.execute("INSERT INTO talent_guesses (guesser, target, guessed_person, guessed_talent, correct, timestamp) VALUES (?,?,?,?,?,?)",
                          (guesser, player_name, guessed_person, talent, correct, datetime.datetime.now().isoformat()))
                conn.commit()
                flash("Your guess has been recorded!")
        conn.close()
        return redirect(url_for('secret_talent', name=guesser))

    c.execute("SELECT guessed_talent, guessed_person, correct FROM talent_guesses WHERE guesser=?", (name,))
    previous_guesses = [{'talent': row[0], 'guessed_person': row[1], 'correct': row[2]} for row in c.fetchall()]
    conn.close()
    saved_player = session.get('selected_player', '')
    print(f"DEBUG secret_talent: name={name}, saved_player={saved_player}")
    # Passa solo i player con talento al template
    return render_template('secret_talent.html', name=name, players=players_with_talent, previous_guesses=previous_guesses, saved_player=saved_player)

@app.route('/organizer')
def organizer():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, difficulty FROM missions ORDER BY id")
    missions = c.fetchall()
    c.execute("SELECT participant, mission_id, filename, points, timestamp FROM submissions ORDER BY timestamp DESC")
    submissions = c.fetchall()
    conn.close()
    return render_template('organizer.html', missions=missions, submissions=submissions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == 'JBH' and password == '12345':
            session['logged_in'] = True
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        flash('Please login first')
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get all participants with their scores
    c.execute("SELECT DISTINCT participant FROM submissions ORDER BY participant")
    participants = [row[0] for row in c.fetchall()]
    
    # Get all data
    c.execute("SELECT id, name, difficulty FROM missions ORDER BY id")
    missions = {row[0]: {'name': row[1], 'difficulty': row[2]} for row in c.fetchall()}
    
    c.execute("SELECT participant, mission_id, filename, points FROM submissions")
    submissions = c.fetchall()
    
    c.execute("SELECT guesser, target, guessed_person, guessed_talent, correct, timestamp FROM talent_guesses ORDER BY timestamp")
    talent_guesses = c.fetchall()
    
    # Include riddle_answer nella query
    c.execute("SELECT participant, table_name, mission_id, mission_name, completed, riddle_answer FROM group_submissions")
    group_submissions = c.fetchall()
    
    c.execute("SELECT voter, voted_for, timestamp FROM tshirt_votes")
    tshirt_votes = c.fetchall()
    
    conn.close()
    
    # Organize data by participant
    participant_data = {}
    for participant in participants:
        participant_data[participant] = {
            'total_score': 0,
            'individual_score': 0,
            'group_score': 0,
            'talent_score': 0,
            'missions': {},
            'group_missions': {},
            'talent_guesses': [],
            'tshirt_votes_received': 0,
            'voted_for': None  # Chi ha votato questo giocatore
        }
    
    # Process individual missions
    for sub in submissions:
        participant, mission_id, filename, points = sub
        if participant in participant_data:
            if filename != 'NOT COMPLETED':
                participant_data[participant]['individual_score'] += points
                participant_data[participant]['total_score'] += points
            participant_data[participant]['missions'][mission_id] = {
                'filename': filename,
                'points': points,
                'mission_name': missions.get(mission_id, {}).get('name', 'Unknown')
            }
    
    # Process group missions
    for gsub in group_submissions:
        participant, table_name, mission_id, mission_name, completed, riddle_answer = gsub
        if participant in participant_data:
            # Get mission info from GROUP_MISSIONS
            points = 0
            has_riddle = False
            for tm in GROUP_MISSIONS:
                if tm['table'] == table_name:
                    for mission in tm['missions']:
                        if mission['id'] == mission_id:
                            points = mission['points']
                            has_riddle = 'riddle' in mission
                            break
            
            # Per missioni con riddle, verifica se la risposta è corretta
            riddle_correct = None
            if has_riddle:
                if riddle_answer:
                    riddle_correct = check_riddle_answer(riddle_answer)
                else:
                    riddle_correct = False
                
                # Punti assegnati SOLO se risposta corretta
                if completed and riddle_correct:
                    participant_data[participant]['group_score'] += points
                    participant_data[participant]['total_score'] += points
            else:
                # Missioni normali (senza riddle)
                if completed:
                    participant_data[participant]['group_score'] += points
                    participant_data[participant]['total_score'] += points
            
            if table_name not in participant_data[participant]['group_missions']:
                participant_data[participant]['group_missions'][table_name] = []
            
            participant_data[participant]['group_missions'][table_name].append({
                'mission_name': mission_name,
                'points': points,
                'completed': completed,
                'riddle_answer': riddle_answer or '',
                'riddle_correct': riddle_correct,
                'has_riddle': has_riddle
            })
    
    # Process talent guesses - 15 punti per ogni guess corretto
    TALENT_POINTS = 15
    for guess in talent_guesses:
        guesser, target, guessed_person, guessed_talent, correct, timestamp = guess
        if guesser in participant_data:
            participant_data[guesser]['talent_guesses'].append({
                'target': target,  # Chi ha veramente quel talento
                'guessed_person': guessed_person,  # Chi il guesser pensa sia
                'talent': guessed_talent,
                'correct': correct,
                'timestamp': timestamp
            })
            # Aggiungi punti se il guess è corretto
            if correct:
                participant_data[guesser]['talent_score'] += TALENT_POINTS
                participant_data[guesser]['total_score'] += TALENT_POINTS
    
    # Process T-Shirt votes
    for vote in tshirt_votes:
        voter, voted_for, timestamp = vote
        # Salva per chi ha votato questo giocatore
        if voter in participant_data:
            participant_data[voter]['voted_for'] = voted_for
        # Incrementa i voti ricevuti
        if voted_for in participant_data:
            participant_data[voted_for]['tshirt_votes_received'] += 1
    
    return render_template('dashboard.html', participant_data=participant_data, missions=missions, players=PLAYERS)

# ==================== ADMIN ERASE ROUTES ====================

@app.route('/admin/erase_all/<participant>')
def erase_all(participant):
    """Cancella tutti i dati di un partecipante"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM submissions WHERE participant=?", (participant,))
    c.execute("DELETE FROM group_submissions WHERE participant=?", (participant,))
    c.execute("DELETE FROM talent_guesses WHERE guesser=?", (participant,))
    c.execute("DELETE FROM tshirt_votes WHERE voter=?", (participant,))
    conn.commit()
    conn.close()
    
    flash(f"All data for {participant} has been erased!")
    return redirect(url_for('dashboard'))

@app.route('/admin/erase_individual/<participant>')
def erase_individual(participant):
    """Cancella le missioni individuali di un partecipante"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM submissions WHERE participant=?", (participant,))
    conn.commit()
    conn.close()
    
    flash(f"Individual missions for {participant} have been erased!")
    return redirect(url_for('dashboard'))

@app.route('/admin/erase_group/<participant>')
def erase_group(participant):
    """Cancella le missioni di gruppo di un partecipante"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM group_submissions WHERE participant=?", (participant,))
    conn.commit()
    conn.close()
    
    flash(f"Group missions for {participant} have been erased!")
    return redirect(url_for('dashboard'))

@app.route('/admin/erase_talent/<participant>')
def erase_talent(participant):
    """Cancella i guess del secret talent di un partecipante"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM talent_guesses WHERE guesser=?", (participant,))
    conn.commit()
    conn.close()
    
    flash(f"Secret talent guesses for {participant} have been erased!")
    return redirect(url_for('dashboard'))

@app.route('/admin/erase_vote/<participant>')
def erase_vote(participant):
    """Cancella il voto t-shirt di un partecipante"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("DELETE FROM tshirt_votes WHERE voter=?", (participant,))
    conn.commit()
    conn.close()
    
    flash(f"T-shirt vote by {participant} has been erased!")
    return redirect(url_for('dashboard'))

# ==================== END ADMIN ERASE ROUTES ====================

@app.route('/leaderboard')
def leaderboard():
    """Mostra la classifica con grafici"""
    if not session.get('logged_in'):
        flash('Please login first')
        return redirect(url_for('login'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Get all participants
    c.execute("SELECT DISTINCT participant FROM submissions ORDER BY participant")
    participants = [row[0] for row in c.fetchall()]
    
    # Get submissions for scores
    c.execute("SELECT participant, mission_id, filename, points FROM submissions")
    submissions = c.fetchall()
    
    # Get group submissions with riddle_answer
    c.execute("SELECT participant, table_name, mission_id, completed, riddle_answer FROM group_submissions")
    group_submissions = c.fetchall()
    
    # Get talent guesses
    c.execute("SELECT guesser, correct FROM talent_guesses")
    talent_guesses = c.fetchall()
    
    # Get tshirt votes
    c.execute("SELECT voted_for, COUNT(*) as votes FROM tshirt_votes GROUP BY voted_for ORDER BY votes DESC")
    tshirt_results = c.fetchall()
    
    conn.close()
    
    # Calculate scores per participant
    TALENT_POINTS = 15
    scores = {}
    for participant in participants:
        scores[participant] = {'individual': 0, 'group': 0, 'talent': 0, 'total': 0}
    
    # Individual scores
    for sub in submissions:
        participant, mission_id, filename, points = sub
        if participant in scores and filename != 'NOT COMPLETED':
            scores[participant]['individual'] += points
    
    # Group scores
    for gsub in group_submissions:
        participant, table_name, mission_id, completed, riddle_answer = gsub
        if participant in scores and completed:
            # Get mission info from GROUP_MISSIONS
            for tm in GROUP_MISSIONS:
                if tm['table'] == table_name:
                    for mission in tm['missions']:
                        if mission['id'] == mission_id:
                            has_riddle = 'riddle' in mission
                            points = mission['points']
                            
                            if has_riddle:
                                # Punti solo se risposta corretta
                                if riddle_answer and check_riddle_answer(riddle_answer):
                                    scores[participant]['group'] += points
                            else:
                                # Missioni normali
                                scores[participant]['group'] += points
                            break
    
    # Talent scores - 15 punti per ogni guess corretto
    for guess in talent_guesses:
        guesser, correct = guess
        if guesser in scores and correct:
            scores[guesser]['talent'] += TALENT_POINTS
    
    # Calculate totals
    for participant in scores:
        scores[participant]['total'] = scores[participant]['individual'] + scores[participant]['group'] + scores[participant]['talent']
    
    # Sort by total score descending
    sorted_scores = sorted(scores.items(), key=lambda x: x[1]['total'], reverse=True)
    
    # Prepare data for charts
    leaderboard_data = {
        'labels': [p[0] for p in sorted_scores],
        'individual_scores': [p[1]['individual'] for p in sorted_scores],
        'group_scores': [p[1]['group'] for p in sorted_scores],
        'total_scores': [p[1]['total'] for p in sorted_scores]
    }
    
    tshirt_data = {
        'labels': [r[0] for r in tshirt_results],
        'votes': [r[1] for r in tshirt_results]
    }
    
    return render_template('leaderboard.html', 
                         leaderboard_data=leaderboard_data, 
                         tshirt_data=tshirt_data,
                         sorted_scores=sorted_scores,
                         tshirt_results=tshirt_results)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Logged out successfully')
    return redirect(url_for('login'))

@app.route('/tshirt_voting', methods=['GET', 'POST'])
def tshirt_voting():
    name = get_current_user()
    
    # Se abbiamo un nome (da sessione o URL), mostra direttamente la pagina di voto
    if name:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Check if user already voted
        c.execute("SELECT voted_for FROM tshirt_votes WHERE voter=?", (name,))
        vote_row = c.fetchone()
        has_voted = vote_row is not None
        voted_for = vote_row[0] if vote_row else None
        
        conn.close()
        
        # Get saved selection from session
        saved_vote = session.get('selected_tshirt_vote', '')
        
        return render_template('tshirt_voting.html', name=name, players=PLAYERS, has_voted=has_voted, voted_for=voted_for, saved_vote=saved_vote)
    
    # Se non abbiamo nome, redirect alla home
    flash("Please select your name first")
    return redirect(url_for('index'))

@app.route('/submit_tshirt_vote', methods=['POST'])
def submit_tshirt_vote():
    name = request.form.get('voter', '').strip()
    voted_for = request.form.get('voted_for', '').strip()
    
    if not name or not voted_for:
        flash("Missing information")
        return redirect(url_for('tshirt_voting'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Check if already voted
    c.execute("SELECT COUNT(*) FROM tshirt_votes WHERE voter=?", (name,))
    if c.fetchone()[0] > 0:
        flash("You have already voted!")
        conn.close()
        return redirect(url_for('tshirt_voting') + f"?name={name}")
    
    # Record vote
    c.execute("INSERT INTO tshirt_votes (voter, voted_for, timestamp) VALUES (?,?,?)",
              (name, voted_for, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    flash("Your vote has been recorded!")
    return redirect(url_for('tshirt_voting') + f"?name={name}")

@app.route('/group_missions', methods=['GET', 'POST'])
def group_missions():
    # Controlla se l'utente vuole forzare la selezione del tavolo
    force_select = request.args.get('force_select', '') == '1'
    
    # Ottieni il nome da POST, GET o sessione
    name = request.form.get('name', '') or request.args.get('name', '') or session.get('current_user', '')
    name = name.strip()
    
    # Se force_select, non caricare il tavolo dalla sessione o DB
    if force_select:
        table = request.form.get('table', '').strip()
    else:
        table = request.form.get('table', '') or request.args.get('table', '') or session.get('selected_table', '')
        table = table.strip()
    
    # Aggiorna la sessione se abbiamo un nome valido
    if name:
        session['current_user'] = name
    
    # Se non abbiamo un tavolo e non stiamo forzando la selezione, controlla se l'utente ne ha già uno nel DB
    if not table and name and not force_select:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT table_name FROM group_submissions WHERE participant=? LIMIT 1", (name,))
        row = c.fetchone()
        conn.close()
        if row:
            table = row[0]
    
    # Salva il tavolo nella sessione
    if table:
        session['selected_table'] = table
    
    # Se abbiamo sia nome che tavolo, mostra direttamente le missioni
    if name and table:
        # Find missions for the selected table
        table_missions = None
        for tm in GROUP_MISSIONS:
            if tm['table'] == table:
                table_missions = tm['missions']
                break
        
        if not table_missions:
            flash("Table not found")
            session.pop('selected_table', None)
            return redirect(url_for('group_missions', name=name))
        
        conn = get_db_conn()
        c = conn.cursor()
        
        # Get or create group mission submissions
        c.execute("SELECT mission_id, completed, riddle_answer FROM group_submissions WHERE participant=? AND table_name=?", (name, table))
        rows = c.fetchall()
        submissions = {row[0]: {'completed': row[1], 'riddle_answer': row[2] or ''} for row in rows}
        
        # If no submissions exist, create them
        if not submissions:
            for mission in table_missions:
                c.execute("INSERT INTO group_submissions (participant, table_name, mission_id, mission_name, completed, riddle_answer) VALUES (?,?,?,?,?,?)",
                          (name, table, mission['id'], mission['name'], 0, ''))
            conn.commit()
            submissions = {mission['id']: {'completed': 0, 'riddle_answer': ''} for mission in table_missions}
        
        conn.close()
        
        return render_template('group_missions.html', name=name, table=table, 
                             missions=table_missions, submissions=submissions, 
                             tables=[tm['table'] for tm in GROUP_MISSIONS])
    
    # Se è GET senza tavolo, mostra la pagina di selezione tabella
    tables = [tm['table'] for tm in GROUP_MISSIONS]
    saved_table = session.get('selected_table', '')
    print(f"DEBUG group_missions GET: name={name}, saved_table={saved_table}")
    return render_template('group_missions_select.html', tables=tables, people=PEOPLE, name=name, saved_table=saved_table)

@app.route('/change_table')
def change_table():
    """Permette di cambiare tavolo cancellando la selezione dalla sessione"""
    session.pop('selected_table', None)
    return redirect(url_for('group_missions', force_select='1'))

@app.route('/restart')
def restart():
    """Riavvia il gioco cancellando tutta la sessione e tornando alla pagina iniziale"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/submit_group_missions', methods=['POST'])
def submit_group_missions():
    name = request.form.get('participant', '').strip()
    table = request.form.get('table', '').strip()
    
    if not name or not table:
        flash("Missing information")
        return redirect(url_for('group_missions'))
    
    conn = get_db_conn()
    c = conn.cursor()
    
    # Find missions for the table to get points
    table_missions = {}
    for tm in GROUP_MISSIONS:
        if tm['table'] == table:
            for mission in tm['missions']:
                table_missions[mission['id']] = mission['points']
            break
    
    # Update submissions
    for key in request.form.keys():
        if key.startswith("completed_"):
            mission_id = int(key.split("_")[1])
            completed = request.form.get(key) == "on"
            
            c.execute("UPDATE group_submissions SET completed=? WHERE participant=? AND table_name=? AND mission_id=?",
                      (1 if completed else 0, name, table, mission_id))
    
    conn.commit()
    conn.close()
    
    flash("Group missions updated successfully!")
    return redirect(url_for('group_missions') + f"?name={name}&table={table}")

if __name__=="__main__":
    init_db()
    load_sample_missions(force_reload=False)
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
else:
    # Per Gunicorn in produzione
    init_db()
    load_sample_missions(force_reload=False)