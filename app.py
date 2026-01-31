from flask import Flask, render_template, request, redirect, send_file
import PyPDF2
import requests
import os
import sqlite3
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "resumes"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SKILLS_LIST = ["python", "java", "javascript", "html", "css", "sql", "flask", "django"]

# ---- Resume Skill Extraction ----
def extract_skills_from_resume(path):
    skills_found = set()
    with open(path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text().lower()

    for skill in SKILLS_LIST:
        if skill in text:
            skills_found.add(skill)

    return list(skills_found)

# ---- GitHub Analyzer ----
def github_skills(username):
    url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(url)
    repos = response.json()

    languages = set()
    repo_count = len(repos)

    for repo in repos:
        lang = repo.get("language")
        if lang:
            languages.add(lang.lower())

    return list(languages), repo_count

def get_github_contributions(username):
    url = f"https://github.com/{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    # GitHub uses data-level on td or div elements in the contribution graph
    contributions = soup.find_all(["td", "rect"], class_="ContributionCalendar-day")
    
    levels = []
    for day in contributions:
        level = day.get("data-level")
        if level is not None:
            levels.append(int(level))
    
    # Return last 30 days of data for visualization
    return levels[-30:] if levels else []

def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        username TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        resume TEXT,
        github TEXT,
        score INTEGER
    )
    """)

    cur.execute("INSERT OR IGNORE INTO admin VALUES ('admin','admin123')")
    conn.commit()
    conn.close()

init_db()

# ---- Routes ----
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/verify", methods=["POST"])
def verify():
    resume = request.files["resume"]
    github = request.form["github"]

    filename = secure_filename(resume.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    resume.save(path)

    resume_skills = extract_skills_from_resume(path)

    username = github.split("/")[-1]
    github_languages, repo_count = github_skills(username)
    contribution_levels = get_github_contributions(username)

    matched = set(resume_skills).intersection(set(github_languages))
    score = int((len(matched) / len(resume_skills)) * 100) if resume_skills else 0

    status = "GENUINE PROFILE ✅" if score >= 50 else "POSSIBLY FAKE ⚠️"

    # 🔽 🔽 🔽 ADD DATABASE CODE HERE 🔽 🔽 🔽
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO results VALUES (?,?,?)",
        (filename, github, score)
    )
    conn.commit()
    conn.close()
    # 🔼 🔼 🔼 DATABASE CODE END 🔼 🔼 🔼

    return render_template(
        "result.html",
        resume_skills=resume_skills,
        github_languages=github_languages,
        score=score,
        status=status,
        repos=repo_count,
        contribution_levels=contribution_levels
    )

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin WHERE username=? AND password=?", (u,p))
        admin = cur.fetchone()
        conn.close()

        if admin:
            return redirect("/admin")
    return render_template("login.html")

@app.route("/admin")
def admin():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM results")
    rows = cur.fetchall()
    conn.close()
    return render_template("admin.html", rows=rows)

@app.route("/download")
def download_pdf():
    file = "reports/report.pdf"
    c = canvas.Canvas(file, pagesize=A4)
    c.drawString(100,800,"Resume Verification Report")
    c.drawString(100,770,f"Score: {request.args.get('score')}%")
    c.save()
    return send_file(file, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
