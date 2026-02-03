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
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Expanded Skills Database with Categories
SKILLS_DATABASE = {
    "languages": ["python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "php", "ruby", "swift", "kotlin"],
    "web_frontend": ["html", "css", "react", "vue", "angular", "svelte", "tailwind"],
    "web_backend": ["flask", "django", "fastapi", "express", "spring", "node.js", "laravel"],
    "databases": ["sql", "mysql", "postgresql", "mongodb", "redis", "sqlite", "firebase"],
    "devops": ["docker", "kubernetes", "aws", "azure", "gcp", "jenkins", "ci/cd", "terraform"],
    "tools": ["git", "github", "gitlab", "rest api", "graphql", "postman", "jira"],
    "data_ml": ["pandas", "numpy", "tensorflow", "pytorch", "scikit-learn", "machine learning", "deep learning"],
    "mobile": ["react native", "flutter", "android", "ios", "xamarin"]
}

# Flatten for resume extraction
SKILLS_LIST = [skill for category in SKILLS_DATABASE.values() for skill in category]

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
    if response.status_code != 200:
        return [], 0, 0
    repos = response.json()

    languages = set()
    repo_count = len(repos)
    fork_count = 0

    for repo in repos:
        lang = repo.get("language")
        if lang:
            languages.add(lang.lower())
        fork_count += repo.get("forks_count", 0)

    return list(languages), repo_count, fork_count

# AI Skill Suggestion Engine
def suggest_skills(resume_skills, github_languages):
    """
    Suggests complementary skills based on existing skillset
    """
    combined_skills = set([s.lower() for s in resume_skills + github_languages])
    suggestions = []
    
    # Define skill relationships and common tech stacks
    skill_recommendations = {
        "python": ["django", "flask", "fastapi", "pandas", "machine learning", "postgresql"],
        "javascript": ["react", "node.js", "typescript", "express", "mongodb"],
        "java": ["spring", "mysql", "docker", "kubernetes", "aws"],
        "react": ["typescript", "redux", "tailwind", "next.js"],
        "django": ["postgresql", "redis", "docker", "rest api"],
        "flask": ["sqlalchemy", "postgresql", "docker", "rest api"],
        "html": ["css", "javascript", "react", "tailwind"],
        "css": ["html", "javascript", "tailwind", "sass"],
        "sql": ["postgresql", "mysql", "database design"],
        "git": ["github", "ci/cd", "docker"],
        "docker": ["kubernetes", "ci/cd", "aws", "azure"],
        "machine learning": ["python", "tensorflow", "pytorch", "pandas", "numpy"],
    }
    
    # Category-based suggestions
    has_backend = any(skill in combined_skills for skill in SKILLS_DATABASE["web_backend"])
    has_frontend = any(skill in combined_skills for skill in SKILLS_DATABASE["web_frontend"])
    has_language = any(skill in combined_skills for skill in SKILLS_DATABASE["languages"])
    
    # Suggest complementary skills based on current stack
    for skill in combined_skills:
        if skill in skill_recommendations:
            for rec in skill_recommendations[skill]:
                if rec.lower() not in combined_skills and rec.lower() not in suggestions:
                    suggestions.append(rec.lower())
    
    # Add category-based suggestions
    if has_backend and not has_frontend:
        for skill in ["react", "vue", "typescript"]:
            if skill not in combined_skills and skill not in suggestions:
                suggestions.append(skill)
    
    if has_frontend and not has_backend:
        for skill in ["node.js", "express", "mongodb"]:
            if skill not in combined_skills and skill not in suggestions:
                suggestions.append(skill)
    
    # Always suggest essential tools if not present
    essential = ["git", "docker", "rest api", "postgresql"]
    for skill in essential:
        if skill not in combined_skills and skill not in suggestions:
            suggestions.append(skill)
    
    # Return top 8 suggestions
    return suggestions[:8]

def get_github_contributions(username):
    # Fetch the contribution graph for the last 4 years
    import datetime
    current_year = datetime.datetime.now().year
    years = [current_year - i for i in range(4)]
    
    total_4_years = 0
    recent_counts = []
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for year in years:
        url = f"https://github.com/users/{username}/contributions?from={year}-01-01&to={year}-12-31"
        if year == current_year:
            # For current year, we don't need the range to get the very latest
            url = f"https://github.com/users/{username}/contributions"
            
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        days = soup.find_all(["td", "rect"], class_="ContributionCalendar-day")
        
        year_counts = []
        for day in days:
            label = day.get("aria-label") or ""
            import re
            match = re.search(r"(\d+)", label)
            if match:
                val = int(match.group(1))
                year_counts.append(val)
            else:
                level = day.get("data-level")
                if level is not None:
                    year_counts.append(int(level))
        
        total_4_years += sum(year_counts)
        
        # If this is the current year (or rolling year fetched via main URL), capture the last 30 days
        if year == current_year and year_counts:
            recent_counts = year_counts[-30:]
            
    return recent_counts, total_4_years

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
    github_languages, repo_count, fork_count = github_skills(username)
    contribution_counts, total_contributions = get_github_contributions(username)

    matched = set(resume_skills).intersection(set(github_languages))
    score = int((len(matched) / len(resume_skills)) * 100) if resume_skills else 0

    status = "GENUINE PROFILE ✅" if score >= 50 else "POSSIBLY FAKE ⚠️"
    
    # Generate AI skill suggestions
    suggested_skills = suggest_skills(resume_skills, github_languages)

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
        forks=fork_count,
        contribution_counts=contribution_counts,
        total_contributions=total_contributions,
        suggested_skills=suggested_skills
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
