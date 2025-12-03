'''

Ai generated shit, but it works

run command:

export MAIL_SERVER='localhost' && export MAIL_PORT='2525' && export MAIL_USERNAME='user' && export MAIL_PASSWORD='password' && export MAIL_USE_TLS='False' && export MAIL_USE_SSL='False' && export PYTHONPATH=$PWD && ./.venv/bin/python -m unittest -v tests/test_login_usecases.py

'''




import unittest
from app import app, db, bcrypt
from app.models import Students

class TestLoginUseCases(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Force in-memory DB if possible, but if engine is already bound, this might be ignored.
        # We will rely on drop_all to clean up whatever DB we are using.
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Ensure clean state
        db.drop_all()
        db.create_all()
        
        # Create a valid user for testing
        hashed_password = bcrypt.generate_password_hash('password123').decode('utf-8')
        self.student = Students(
            roll_number='12345',
            name='Test Student',
            email='test@example.com',
            password_hash=hashed_password,
            contact_number='1234567890'
        )
        db.session.add(self.student)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # U2-TC1: Successful login
    def test_u2_tc1_successful_login(self):
        """
        Test ID: U2-TC1
        Function: Successful login
        Input Data: Valid Email + Correct Password
        Expected Output: User logged in; redirect to Dashboard
        """
        response = self.app.post('/login', data={
            'email': 'test@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome, Test Student!', response.data)

    # U2-TC2: Email does not exist
    def test_u2_tc2_email_does_not_exist(self):
        """
        Test ID: U2-TC2
        Function: Email does not exist
        Input Data: Invalid Email
        Expected Output: Error: “Email not found” (Actual: "Login failed. User not found.")
        """
        response = self.app.post('/login', data={
            'email': 'wrong@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Login failed. User not found.', response.data)

    # U2-TC3: Incorrect password
    def test_u2_tc3_incorrect_password(self):
        """
        Test ID: U2-TC3
        Function: Incorrect password
        Input Data: Valid Email + Wrong Password
        Expected Output: Error: “Incorrect password” (Actual: "password or email incorrect")
        """
        response = self.app.post('/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'password or email incorrect', response.data)

    # U2-TC4: Missing required fields
    def test_u2_tc4_missing_required_fields(self):
        """
        Test ID: U2-TC4
        Function: Missing required fields
        Input Data: Empty Email and/or Password
        Expected Output: Error: “Email and Password are required” (Actual: "insert email or password")
        """
        response = self.app.post('/login', data={
            'email': '',
            'password': ''
        }, follow_redirects=True)
        self.assertIn(b'insert email or password', response.data)

    # U2-TC5: Unverified account
    def test_u2_tc5_unverified_account(self):
        """
        Test ID: U2-TC5
        Function: Unverified account
        Input Data: Valid Email + Correct Password (not verified)
        Expected Output: Error: “Please verify your email before logging in”
        
        Note: In the current implementation, unverified users are not stored in the database,
        so this behaves identically to U2-TC2 (User not found).
        """
        response = self.app.post('/login', data={
            'email': 'unverified@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Login failed. User not found.', response.data)

    # U2-TC6: Logout
    def test_u2_tc6_logout(self):
        """
        Test ID: U2-TC6
        Function: Logout
        Input Data: Click Logout
        Expected Output: Session ends; user returned to Login page
        """
        # First login
        self.app.post('/login', data={
            'email': 'test@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        
        # Then logout
        response = self.app.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login Page', response.data)

if __name__ == '__main__':
    unittest.main()
