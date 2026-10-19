# 🎮 Mission Game

A web-based party game where guests complete fun missions, upload photos, and compete for points.  
Perfect for dinners, birthdays, Halloween parties, team events, and more.

> *Turn any party into a game. Missions, photos, points — pure fun.*

**Curated by JB**

## ▶️ Play now

**👉 [Open the game](https://allseas-christmas-game.onrender.com)**

*The first load can take up to a minute while the server wakes up.*

---

## ⭐ Features

### 🎨 Multi-Theme Support
Choose a theme that fits your event:
- 🎄 **Christmas** — snowflakes, festive missions
- 🎂 **Birthday** — balloons, party vibes
- 🎃 **Halloween** — spooky atmosphere
- 🎉 **Party** — universal fun for any occasion

### 🕹️ Game Modes
The host picks which games to activate:
- **📋 Individual Missions** — each player gets a unique set of missions to complete
- **👥 Group Missions** — team-based challenges
- **🎭 Secret Talent** — guess who has which hidden talent

### 👤 Player Experience
- Enter your name and join the game
- Complete missions and upload photos
- Automatic score calculation
- Simple, fast, mobile-friendly interface

### 📊 Host Dashboard
- View all submissions in real time
- Check completion rates
- Monitor scores and leaderboard
- Download results as CSV

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

### 5. Open in browser
- **Game:** [http://127.0.0.1:5001](http://127.0.0.1:5001)
- **Admin Dashboard:** [http://127.0.0.1:5001/login](http://127.0.0.1:5001/login)

---

## 📁 Project Structure

```
├── app.py                  # Main Flask application
├── missions.json           # Mission packs (tagged by theme)
├── group_missions.json     # Group/team missions
├── render.yaml             # Render.com deployment config
├── requirements.txt        # Python dependencies
├── static/
│   └── style.css
├── templates/              # HTML templates (Jinja2)
│   ├── welcome.html        # Landing page (theme + feature selection)
│   ├── index.html          # Player join page
│   ├── participant.html    # Main game interface
│   ├── secret_talent.html  # Talent guessing game
│   ├── group_missions.html # Team missions
│   ├── leaderboard.html    # Scoreboard
│   ├── login.html          # Admin login
│   ├── dashboard.html      # Admin dashboard
│   └── organizer.html      # Organizer view
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
