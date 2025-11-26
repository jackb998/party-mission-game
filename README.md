Christmas Missions Web App (Flask)
=====================================

This is a minimal, self-contained Flask web app intended as a simple tool to run the "missions" game during your Christmas dinner event.

Features:
- Participant page: participants enter their name and see the list of missions.
- Photo upload required to submit a mission.
- Organizer dashboard: view submissions, download CSV of submissions, and see completion counts.
- Simple SQLite database (data.db) stores missions, participants, and submissions.

How to run (basic):
1. Install Python 3.9+ and pip.
2. (Optional) create a virtual environment:
   python -m venv venv
   source venv/bin/activate  # mac/linux
   venv\Scripts\activate   # windows
3. Install dependencies:
   pip install flask werkzeug
4. Run the app:
   python app.py
5. Open http://127.0.0.1:5000 in your browser.
6. Organizer dashboard: http://127.0.0.1:5000/organizer

Notes and next steps:
- Uploads are saved in the 'uploads' folder.
- If you want to change missions, edit missions.json before first run, or manage DB directly.
- For short-term event use, this app can be run on any laptop and the local network shared via a hotspot; participants can connect using the laptop's local IP.
- If you want, I can help adapt this to a cloud host (Heroku, Render, Railway) or a server so it is accessible by all participants without local network steps.
