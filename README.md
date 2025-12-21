# Online Examination System (OES)

A web-based Online Examination System built with Flask and SQLite.  
The system supports exam creation, exam taking, automatic grading, manual grading, and result viewing for students and instructors.

---

## Features

### Authentication
- Student and Instructor registration
- Email verification
- Secure password hashing
- Role-based access control

### Exams (Instructor)
- Create and manage exams
- Configure availability windows
- Add, edit, delete, and reorder questions
- Preview exams before publishing

### Exam Taking (Student)
- Search exams by exam ID
- Resume unfinished exams
- Autosave during exams
- Timer with automatic submission on expiration
- Manual submit and save-and-exit support

### Grading
- Automatic grading for objective questions
- Manual grading by instructors
- Partial credit support
- Submission locking to prevent concurrent grading
- Audit logging for grading actions

### Results
- View completed and graded exams
- Per-question breakdown of answers and scores
- Instructor feedback visibility
- Client-side filtering by course code

---

## Getting Started

### Prerequisites
- Python 3.10+

---

## Application Download
### Method A – Using Git
```
git clone https://github.com/guregu-san/Group5-Online-Examination-System.git
```

### Method B – Downloading a ZIP File
- Open the project’s GitHub page.
- Select Code → Download ZIP.
- Extract the ZIP file locally.
- Open the project folder.


## Python Virtual Environment Setup

### 1) Create venv (use .venv or venv as you prefer)
```
python3 -m venv .venv
```

### 2) Activate venv
**On Windows (PowerShell):**
```
.\.venv\Scripts\Activate.ps1
```
**On macOS/Linux:**
```
source .venv/bin/activate
```

### 3) Upgrade pip, setuptools, wheel
```
python -m pip install --upgrade pip setuptools wheel
```

### 4) Install dependencies
Packages:
```
pip install flask flask_sqlalchemy flask_login flask_bcrypt flask_wtf wtforms email_validator Flask-Mail Flask-Bootstrap Flask-APScheduler dotenv
```

### 5) Quick verification (optional)
```
pip list
python -c "import flask, flask_sqlalchemy, flask_login; print('flask', flask.__version__)"
```

### 6) Run project
```
python3 run.py
```

**(Optional)** 
- Install Cloudflared using the the guide on their github page: https://github.com/cloudflare/cloudflared
- Then to host the application on a Cloudflared server with a temporary domain name run:
```
cloudflared tunnel --url http://localhost:5001
```

### 7) Deactivate venv when done using the app
```
deactivate
```

### Note:
## Test users: 
## All test user passwords are "dupa12345"
