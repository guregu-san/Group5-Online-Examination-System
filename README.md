# Online-Examination-System
## Key Features
content

## how to use virtual environment for python

### 1) create venv (use .venv or venv as you prefer)
```
python3 -m venv .venv
```

### 2) activate venv
**On Windows (PowerShell):**
```
.\.venv\Scripts\Activate.ps1
```
**On macOS/Linux:**
```
source .venv/bin/activate
```
### 3) upgrade pip, setuptools, wheel
```
python -m pip install --upgrade pip setuptools wheel
```
### 4) install the packages
Packages:
```
pip install flask flask_sqlalchemy flask_login flask_bcrypt flask_wtf wtforms email_validator Flask-Mail Flask-Bootstrap dotenv
```

### 5) quick verification (optional)
```
pip list
python -c "import flask, flask_sqlalchemy, flask_login; print('flask', flask.__version__)"
```
### 6) run project
```
python3 run.py
```

alesy note:
all user hashed passwords is "dupa12345"
