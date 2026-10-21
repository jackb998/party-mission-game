# 🎮 Mission Game

A web-based party game where guests complete fun missions, upload photos, and compete for points.  
Perfect for dinners, birthdays, Halloween parties, team events, and more.

> *Turn any party into a game. Missions, photos, points — pure fun.*

**Curated by JB**

## ▶️ Play now

**👉 [Open the game](https://party-mission-game.onrender.com)**

*The first load can take up to a minute while the server wakes up.*

---

## ⭐ Features

### 🎨 Multi-Theme Support
Choose a theme that fits your event:
- 🎄 **Christmas** — snowflakes, festive missions
- 🎂 **Birthday** — balloons, party vibes
- 🎃 **Halloween** — spooky atmosphere
- 🎉 **Party** — universal fun for any occasion

### 🔑 Games with a code
Anyone can create a game in a few seconds: pick a theme, the game modes and a host password.
You get a **6-character code** and a link to share. Guests join by typing the code (or opening the link) and entering their name.
Every game is completely separate: its own players, missions, photos and scores.

### 🕹️ Game Modes
The host picks which games to activate:
- **📋 Individual Missions** — each player gets a unique set of missions to complete
- **👥 Group Missions** — team-based challenges
- **🎭 Secret Talent** — guess who has which hidden talent

### 👤 Player Experience
- Enter your name and join the game (no account needed)
- Complete missions and upload photos
- Automatic score calculation
- Simple, fast, mobile-friendly interface

### 📊 Host Dashboard
- Protected by the host password chosen when the game is created
- View all submissions and photos
- Monitor scores and leaderboard (with tie-break quiz)
- Erase a player's data, or the whole game's data

---

## 🚀 Quick Start

### 1. Install Python (3.9+)

### 2. (Optional) Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install flask werkzeug
```

### 4. Start the application
```bash
PORT=5001 python app.py
```
(On macOS port 5000 is used by AirPlay, so 5001 is used here.)

To try it from a phone on the same Wi-Fi, listen on the network (this turns the debugger off):
```bash
HOST=0.0.0.0 PORT=5001 python app.py
```

Optional environment variables: `SECRET_KEY` (session signing key), `DB_PATH` (SQLite file) and `UPLOAD_FOLDER` (photo folder).

### 5. Open in browser
- **Game:** [http://127.0.0.1:5001](http://127.0.0.1:5001)
- Create a game on the home page, then open the host dashboard from the "game is ready" page.

---

## 📁 Project Structure

```
├── app.py                  # Main Flask application
├── missions.json           # Mission packs (tagged by theme)
├── group_missions.json     # Group/team missions (optionally tagged by theme)
├── render.yaml             # Render.com deployment config
├── requirements.txt        # Python dependencies
├── static/
│   └── style.css
├── templates/              # HTML templates (Jinja2)
│   ├── welcome.html        # Landing page (join with a code / create a game)
│   ├── event_created.html  # Code and share link after creating a game
│   ├── index.html          # Player join page
│   ├── error.html          # Friendly error page
│   ├── participant.html    # Main game interface
│   ├── secret_talent.html  # Talent guessing game
│   ├── group_missions.html # Team missions
│   ├── leaderboard.html    # Scoreboard
│   ├── login.html          # Host login
│   ├── pictures.html       # Photo gallery (host)
│   └── dashboard.html      # Host dashboard
└── uploads/                # Photo uploads
```

---

## 🌐 Deploy Your Own

Deploy for free on any of these platforms:

| Platform | Guide |
|----------|-------|
| [Render](https://render.com) | Uses included `render.yaml` |
| [Railway](https://railway.app) | Connect GitHub repo |
| [Heroku](https://heroku.com) | Standard Python buildpack |

Or run on any VPS / local server for private events.

---

## 📬 Contact

Questions or feedback? Reach out at **jacopobeghetto98@gmail.com**
