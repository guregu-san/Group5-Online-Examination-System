# Test Cases — Use Case 5 (Exam Taking)

## Pre-Requisite — Student Login
```bash
# Login as student (saves session cookie)
curl -L -X POST http://127.0.0.1:5001/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'email=student1@example.com&password=student123' \
  -c cookies.txt
```

## Test Case 1 — Search for Exam (U5-TC1)
```bash
# Search for exam by valid ID (stores exam_id in session cookie)
curl -L -X POST http://127.0.0.1:5001/take_exam \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'examID=1' \
  -b cookies.txt \
  -c cookies.txt
```

## Test Case 2 — Search for Invalid Exam (U5-TC2)
```bash
# Search for non-existent exam
curl -L -X POST http://127.0.0.1:5001/take_exam \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'examID=999' \
  -b cookies.txt \
  -c cookies.txt
```

## Test Case 3 — Accept Exam Conditions (U5-TC3)
```bash
# POST to accept exam instructions and start exam
curl -L -X POST http://127.0.0.1:5001/take_exam/initialization \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'exam_id=1&continue_submission=1&csrf_token=<token>'
```

## Test Case 4 — Decline Exam Conditions (U5-TC4)
```bash
# POST to decline exam instructions
curl -L -X POST http://127.0.0.1:5001/take_exam/initialization \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'exam_id=1&cancel=1&csrf_token=<token>'
```

## Test Case 6 — Save & Exit Mid-Exam (U5-TC6)
```bash
# POST to save and exit mid-exam
curl -L -X POST http://127.0.0.1:5001/take_exam/start \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'questions-0-question_id=1&questions-0-single_or_multi=single&questions-0-answer_single=11&save_exit=1&csrf_token=<token>'
```

## Test Case 7 — Resume Saved Exam (U5-TC7)
```bash
# GET to continue an in-progress exam
curl -L -X GET http://127.0.0.1:5001/take_exam/initialization \
  -b cookies.txt
```

## Test Case 8 — Autosave Trigger (U5-TC8)
```bash
# POST to autosave endpoint after changing an answer
curl -L -X POST http://127.0.0.1:5001/take_exam/autosave \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'questions-0-question_id=1&questions-0-single_or_multi=single&questions-0-answer_single=12&csrf_token=<token>'
```

## Test Case 9 — Exam Not Yet Open (U5-TC9)
```bash
# Attempt to start exam before opens_at
curl -L -X POST http://127.0.0.1:5001/take_exam/start \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'exam_id=2&csrf_token=<token>'
```

## Test Case 10 — Prevent Double Submission (U5-TC10)
```bash
# Attempt to start exam after already submitted
curl -L -X POST http://127.0.0.1:5001/take_exam/start \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'exam_id=1&csrf_token=<token>'
```

## Test Case 11 — Submit Exam (U5-TC11)
```bash
# POST to submit completed exam
curl -L -X POST http://127.0.0.1:5001/take_exam/start \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'questions-0-question_id=1&questions-0-single_or_multi=single&questions-0-answer_single=11&submit=1&csrf_token=<token>'
```

## Test Case 12 — Modify After Submission (U5-TC12)
```bash
# Attempt to change answers after submission
curl -L -X POST http://127.0.0.1:5001/take_exam/start \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b cookies.txt \
  -d 'questions-0-question_id=1&questions-0-single_or_multi=single&questions-0-answer_single=12&csrf_token=<token>'
```
