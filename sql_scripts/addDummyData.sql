PRAGMA foreign_keys = ON;

-- Instructors
INSERT INTO instructors (name, email, password_hash)
VALUES
    ('Teacher One', 'teacher@uni.com', 'pass'),
    ('Dr. Alice Johnson', 'alice.johnson@univ.edu', 'hash_pw_alice'),
    ('joe',	'joe@example.com', '$2b$12$t5JIooA4DuwOP1oAZHLygOVmXy0dJhjRA9nC9PPA21990W/VABpxa'),
    ('Joe Doe', 'joe1@uni.com', '$2b$12$cJHNFHQMzyuPE2XksYXBE.a3lp5mKHsZ.ZZBKeIMy4mNE0SP6JIie'),
    ('alex2', 'alex2@example.com\', '$2b$12$apCWKCwGOYX2Vzqg4OENfu7o.ti2KREAG4QEy0BbR24tMLvj.hhx6'),
    ('Prof. Bob Smith', 'bob.smith@univ.edu', 'hash_pw_bob');

-- Students
INSERT INTO students (roll_number, name, email, password_hash, contact_number)
VALUES
    (1, 'Student One', 'student@uni.com', 'pass', '1234567890'),
    (101, 'John Doe', 'john.doe@student.edu', 'hash_pw_john', 9876543210),
    (102, 'Jane Miller', 'jane.miller@student.edu', 'hash_pw_jane', 9876543211),
    (103, 'Samuel Green', 'sam.green@student.edu', 'hash_pw_sam', 9876543212),
    (104, 'Alex' ,'studentTest@uni.com', '$2b$12$cyv7vXQ1ZCIpDFZYWyNFeOjx/epMWSEOKHz/MZRSAb2jTRhws2MEG', 9876543213),
    (105, 'jakob', 'jakob@uni.com', '$2b$12$Ped50fSVQC/FQ88.doxsUO1BP1pTIQnq4iB0Af7Dt/Ag2bPcL0tRu', 9876543214);

-- Courses
INSERT INTO courses (course_code, course_name, instructor_email)
VALUES
    ('CS101', 'Example Course', 'teacher@uni.com'),
    ('CS102', 'Introduction to Programming', 'alice.johnson@univ.edu'),
    ('CS103', 'Data Structures', 'bob.smith@univ.edu');

-- Exams
INSERT INTO exams (instructor_email, course_code, title, time_limit, security_settings, created_at, updated_at)
VALUES
    ('teacher@uni.com', 'CS101', 'Midterm Exam v2', 100, '{"password":'', "shuffle":true, "single_session":false, "no_tab_switching":false}', '2025-01-01 10:00:00', '2025-01-01 10:05:00'),
    ('joe@example.com', NULL, 'Sample Exam', 30, '{"password":"111", "shuffle":false, , "single_session":true, "no_tab_switching":false}}', '2025-01-01 12:00:00', NULL),
    ('alice.johnson@univ.edu', 'CS102', 'Midterm Exam', 60, '{"password":"1234", "shuffle":true, , "single_session":true, "no_tab_switching":true}}', '2025-01-01 11:00:00', NULL),
    ('bob.smith@univ.edu', 'CS103', 'Final Exam', 90, '{"password":"121212", "shuffle":false, , "single_session":false, "no_tab_switching":true}', '2025-01-01 10:11:00', '2025-01-01 10:12:00');

-- Questions
INSERT INTO questions (exam_id, question_text, is_multiple_correct, points, order_index)
VALUES
    (1, 'What is 4+4?', 0, 8, 1),
    (1, 'What is 3+3?',	0, 10, 2),

    (2, 'What is 2 + 2?', 0, 5, 1),
    (2, 'Select prime numbers',	1, 10, 2),

    (3, 'What is a variable?', 0, 5, 1),
    (3, 'Select all valid Python data types.', 1, 10, 2),

    (4, 'What is the time complexity of binary search?', 0, 5, 1),
    (4, 'Select all tree traversal algorithms.', 1, 10, 2);

-- Options
INSERT INTO options (question_id, option_text, is_correct)
VALUES
    (1, '7', 0),
    (1, '8', 1),
    (1, '9', 0),

    (2, '5', 0),
    (2, '6', 1),
    (2, '7', 0),

    (3, '10', 0),
    (3, '4', 1),
    (3, '1', 0),

    (4, '2', 0),
    (4, '3', 1),
    (4, '4', 0),
    (4, '6', 0),

    (5, 'A named storage location for data.', 1),
    (5, 'A mathematical equation.', 0),

    (6, 'int', 1),
    (6, 'float', 1),
    (6, 'banana', 0),

    (7, 'O(log n)', 1),
    (7, 'O(n^2)', 0),

    (8, 'Inorder', 1),
    (8, 'Postorder', 1),
    (8, 'Linear search', 0);

-- Submissions
INSERT INTO submissions (exam_id, roll_number, started_at, submitted_at, updated_at, feedback, status, answers, total_score)
VALUES
    (1, 101, '2025-01-02 10:00:00', '2025-01-01 10:40:00', '2025-01-01 10:50:00', 'Good job!', 'REVIEWED', '{"1":2,"2":5}', 18),
    (1, 102, '2025-01-02 10:05:00', '2025-01-01 10:50:00', NULL, NULL, 'SUBMITTED', '{"1":1,"2":5}', 10),

    (3, 103, '2025-01-10 09:00:00', NULL, NULL, NULL, 'IN_PROGRESS', '{"5":14}', NULL);
