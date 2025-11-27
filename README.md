🎄 Christmas Missions Web App (Flask)

A lightweight, event-friendly Flask web application designed to manage a fun “missions game” during a Christmas dinner or team event. Participants receive a set of missions, complete them (sometimes with a required photo upload), and collect points. An organizer can monitor all submissions through a simple dashboard.

This project is ideal for small private events and can run locally on any laptop.

⭐ Features
Participant Experience

Enter your name and access your assigned missions

Complete missions and upload photos when required

Automatic score calculation

Simple and fast mobile-friendly interface

Organizer Dashboard

View all submissions in real time

Check completion rates

Download all results as a CSV

Photos stored locally inside the uploads/ directory

Technical Characteristics

Zero external services required

Uses a lightweight SQLite database (data.db)

Runs fully offline on a local network

Simple HTML templates powered by Jinja2

🚀 How to Run the App
1. Install Python (3.9+)

Make sure Python and pip are available on your system.

2. (Optional) Create a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

3. Install dependencies
pip install flask werkzeug

4. Start the application
python app.py

5. Access the web interface

Participant page:
http://127.0.0.1:5000

Organizer dashboard:
http://127.0.0.1:5000/organizer

📁 Project Structure
/ (root)
  ├── app.py                 # Main Flask application
  ├── data.db                # SQLite database (generated automatically)
  ├── gitignore.db
  ├── group_missions.json    # Group missions list for the game
  ├── missions.json          # Individual missions list for the game
  ├── people.json            # Participant dataset name
  ├── render.yaml            # Application rendering
  ├── requirements.txt       # App requirement packages 
  ├── static/                # Style settings
        ├── style.css
  ├── templates/             # HTML templates (Jinja2)
        ├── dashboard.html
        ├── group_missions_select.html
        ├── group_missions.html
        ├── index.html
        ├── leaderboard.html
        ├── login.html
        ├── organizer.html
        ├── participant.html
        ├── secret_talent.html
        └── tshirt_voting.html
  └── uploads/               # Photo uploads

🎨 Branding & Styling (optional)

The interface can be customized using Allseas branding guidelines (colors, typography, tone).
If you want the UI to match the Allseas identity exactly, it can be styled based on the brand information available here:

https://brandfetch.com/allseas.com?view=library&library=default

I can generate a fully branded CSS theme if needed.

📬 Contact

If you would like to try the app, request access, or need help adapting it for your event, contact the administrator:

jacopobeghetto98@gmail.com

🌐 Deployment Options

For events where guests are not on the same local network, the app can be deployed on:

Render

Railway

Heroku (free tier alternatives may apply)

Any small VPS or internal server