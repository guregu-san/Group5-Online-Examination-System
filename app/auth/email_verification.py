
from itsdangerous import URLSafeTimedSerializer
from flask import url_for, current_app
from flask_mail import Message
from app import mail

def generate_verification_token(data):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(data, salt='email-confirm-salt')

def confirm_verification_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        data = serializer.loads(
            token,
            salt='email-confirm-salt',
            max_age=expiration
        )
    except Exception:
        return False
    return data

def send_verification_email(user_data):
    token = generate_verification_token(user_data)
    confirm_url = url_for('authBp.verify_email', token=token, _external=True)
    
    html = f"""
    <p>Welcome to the Online Examination System (OES)!</p>
    <p>Thanks for signing up. Please follow this link to activate your OES account:</p>
    <p><a href="{confirm_url}">{confirm_url}</a></p>
    <br>
    <p>If you did not register for this account, please ignore this email.</p>
    <p>Best regards,<br>The OES Team</p>
    """
    
    msg = Message(
        subject="Verify your OES Account",
        sender=("OES Verification", "hello@demomailtrap.co"),
        recipients=[user_data['email']],
        html=html
    )
    
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Mailtrap Error: {e}")
        raise e



