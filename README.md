# Online-Examination-System
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

### Note: All test user passwords are "dupa12345"
