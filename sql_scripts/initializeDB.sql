CREATE TABLE IF NOT EXISTS instructors (
    instructor_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    roll_number INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    contact_number INTEGER UNIQUE
);

CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    course_name TEXT NOT NULL,
    instructor_email TEXT NOT NULL,
    FOREIGN KEY (instructor_email) REFERENCES instructors(email)
);

CREATE TABLE IF NOT EXISTS exams (
    exam_id INTEGER PRIMARY KEY,
    instructor_email TEXT NOT NULL,
    course_code TEXT,
    title TEXT NOT NULL,
    time_limit INTEGER,
    security_settings TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (instructor_email) REFERENCES instructors(email),
    FOREIGN KEY (course_code) REFERENCES courses(course_code)
);

CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    is_multiple_correct BOOLEAN NOT NULL,
    points INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    FOREIGN KEY (exam_id) REFERENCES exams(exam_id)
);

CREATE TABLE IF NOT EXISTS options (
    option_id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(question_id)
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    roll_number INT NOT NULL,
    started_at DATETIME NOT NULL,
    submitted_at DATETIME,
    updated_at DATETIME,
    feedback TEXT,
    status TEXT CHECK (status IN ('IN_PROGRESS', 'SUBMITTED', 'IN_REVIEW', 'REVIEWED')) NOT NULL,
    answers TEXT,
    total_score INTEGER,
    FOREIGN KEY (exam_id) REFERENCES exams (exam_id),
    FOREIGN KEY (roll_number) REFERENCES students (roll_number)
);
