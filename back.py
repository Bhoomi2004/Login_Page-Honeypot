# Email credentials
SENDER_EMAIL = "bhoomimehta2004@gmail.com"
SENDER_PASSWORD = "ckkf cyjx qqjv mlzc"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage
import threading
import time
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import bcrypt

app = Flask(__name__, template_folder='.')
app.secret_key = 'your_secret_key'

# Database connection
conn = psycopg2.connect(
    dbname="Minor",
    user="postgres",
    password="postgre@2025",
    host="localhost",
    port="5432"
)
cursor = conn.cursor()
global_blocked = False


def cleanup_and_reset_block():
    global global_blocked
    while True:
        cursor.execute("DELETE FROM blocked_emails WHERE blocked_until <= NOW()")
        conn.commit()

        deleted_rows = cursor.rowcount  # Get the number of deleted rows
        print(f"✅ Expired entries cleaned up. {deleted_rows} entries removed.")

        # Check if no blocked entries remain
        cursor.execute("SELECT COUNT(*) FROM blocked_emails WHERE blocked_until > NOW()")
        if cursor.fetchone()[0] == 0:
            if global_blocked:
                print("✅ Resetting global block state.")
                global_blocked = False  # Reset the block if no active blocked entries
        
        time.sleep(420)  # Run every 7 minutes

# Email sending function

def send_email(recipient, subject, body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient

        # Set HTML content instead of plain text
        msg.add_alternative(body, subtype='html')

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            print(f"Email sent to {recipient}")
    except Exception as e:
        print(f"Error sending email: {e}")


# Helper function to check IP and email blocks
def is_blocked(email, ip):
    cursor.execute("DELETE FROM blocked_emails WHERE blocked_until <= NOW()")
    conn.commit()
    print("✅ Expired entries deleted.")

    # Check if the provided email is still blocked
    cursor.execute("SELECT * FROM blocked_emails WHERE email = %s AND blocked_until > NOW()", (email,))
    if cursor.fetchone():
        print(f"\033[91m🚑🚫 Blocked Email Attempt: {email}\033[0m")
        return True, 'email'

    # Check if the IP is still blocked
    cursor.execute("SELECT * FROM failed_ips WHERE ip_address = %s AND last_attempt > NOW() - INTERVAL '5 minutes'", (ip,))
    if cursor.fetchone():
        print(f"\033[91m🚑🚫 Blocked IP Attempt: {ip}\033[0m")
        return True, 'ip'

    return False, None


@app.route("/login", methods=["POST"])
def login():
    global global_blocked  # Track overall block status
    
    email = request.form.get('email')
    password = request.form.get('password')
    honeypot = request.form.get('honeypot')
    ip = request.remote_addr

    if honeypot:
        cursor.execute("INSERT INTO failed_ips (ip_address, failed_attempts, last_attempt) VALUES (%s, 100, NOW()) "
                       "ON CONFLICT (ip_address) DO UPDATE SET failed_attempts = 100, last_attempt = NOW()", (ip,))
        conn.commit()
        print(f"[DEBUG] IP Blocked: {ip}")
        flash("Your IP has been permanently blocked.", "danger")
        return redirect(url_for("login_page"))

    # Check if the system is already in a blocked state
    if global_blocked:
        flash("Invalid password.", "danger")
        return redirect(url_for("login_page"))

    cursor.execute("SELECT COUNT(*) FROM failed_ips WHERE ip_address = %s AND failed_attempts >= 100", (ip,))
    ip_blocked = cursor.fetchone()[0]

    if ip_blocked:
        flash("Your IP has been permanently blocked.", "danger")
        return redirect(url_for("login_page"))
    blocked, reason = is_blocked(email, ip)

    # Display "Your email is blocked" if the CURRENT email is blocked
    if blocked and reason == 'email':
        flash("Login failed. Your email is blocked.", "danger")
        return redirect(url_for("login_page"))

    # Check if ANY email is currently blocked and show "Invalid password" for other attempts
    cursor.execute("SELECT COUNT(*) FROM blocked_emails WHERE blocked_until > NOW()")
    active_blocks = cursor.fetchone()[0]

    if active_blocks > 0 and not (blocked and reason == 'email'):
        flash("Invalid password.", "danger")
        return redirect(url_for("login_page"))

    # Continue with normal login logic
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
        cursor.execute("UPDATE users SET failed_attempts = 0 WHERE email = %s", (email,))
        cursor.execute("INSERT INTO users_logins (user_id, login_time, ip_address, failed_attempts) "
                       "VALUES (%s, NOW(), %s, 0)", (user[0], ip))
        conn.commit()
        return "Login Successful!"

    # Update failed attempts
    cursor.execute("SELECT failed_attempts FROM users WHERE email = %s", (email,))
    failed_attempts = cursor.fetchone()[0] + 1
    cursor.execute("UPDATE users SET failed_attempts = %s WHERE email = %s", (failed_attempts, email))

    # Block logic
    if failed_attempts % 5 == 0:
        cursor.execute(
            "INSERT INTO blocked_emails (email, blocked_until) VALUES (%s, NOW() + INTERVAL '5 minutes') "
            "ON CONFLICT (email) DO UPDATE SET blocked_until = NOW() + INTERVAL '5 minutes'", (email,))
        cursor.execute(
            "INSERT INTO failed_ips (ip_address, failed_attempts, last_attempt) VALUES (%s, 5, NOW()) "
            "ON CONFLICT (ip_address) DO UPDATE SET failed_attempts = 5, last_attempt = NOW()", (ip,))
        
        global_blocked = True  # Enable global block state
        
        send_email(
            email, 
            "Account Security Alert", 
            f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #d9534f;">Notice: Temporary Account Lock</h2>
                <p>
                    Dear User,<br><br>
                    We detected multiple unsuccessful login attempts on your account, and as a precaution, 
                    your email has been temporarily blocked for <strong>5 minutes</strong>.
                </p>
                
                <p>
                    If you believe this was an error or wish to review your account activity, 
                    please click the button below to request a detailed report:
                </p>
                
                <div style="text-align: center; margin: 20px 0;">
                    <a href='https://example.com/account-report' 
                    style="display: inline-block; padding: 10px 20px; background-color: #5bc0de; 
                            color: #fff; text-decoration: none; border-radius: 4px;">
                    Request Account Report
                    </a>
                </div>

                <p>
                    If you did not attempt to log in, we strongly recommend changing your password immediately 
                    for your account’s security.
                </p>

                <p style="margin-top: 20px;">Best regards, <br> Your Security Team</p>
            </body>
            </html>
            """
        )

        conn.commit()
        flash("Login failed. Your email is blocked.", "danger")
        return redirect(url_for("fake_login"))

    if failed_attempts >= 25:
        cursor.execute("INSERT INTO blocked_emails (email, blocked_until) VALUES (%s, '9999-12-31')", (email,))
        conn.commit()
        send_email(
            email, 
            "Urgent: Permanent Account Block Notification", 
            f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #d9534f;">Urgent: Permanent Account Block Notification</h2>
                
                <p>
                    Dear User,<br><br>
                    We regret to inform you that your account has been <strong>permanently blocked</strong> due to multiple 
                    unsuccessful login attempts or suspicious activity.
                </p>
                
                <p>
                    For your security, access to this account has been restricted indefinitely. 
                    If you believe this was a mistake or require further assistance, please contact our support team immediately.
                </p>

                <div style="text-align: center; margin: 20px 0;">
                    <a href='https://example.com/contact-support' 
                    style="display: inline-block; padding: 10px 20px; background-color: #d9534f; 
                            color: #fff; text-decoration: none; border-radius: 4px;">
                    Contact Support
                    </a>
                </div>

                <p>
                    Please avoid sharing your account credentials and ensure your devices are secure to prevent such incidents in the future.
                </p>

                <p style="margin-top: 20px;">Sincerely,<br> Your Security Team</p>
            </body>
            </html>
            """
        )

        flash("Your email has been permanently blocked.", "danger")
        return redirect(url_for("login_page"))

    conn.commit()
    flash("Invalid password.", "danger")
    return redirect(url_for("login_page"))

@app.route("/fake_login")
def fake_login():
    return render_template("fake.html")

@app.route("/", methods=["GET", "POST"])
def login_page():
    return render_template("login.html")

@app.route("/check_blocked_email")
def check_blocked_email():
    email = request.args.get("email")

    cursor.execute("SELECT * FROM blocked_emails WHERE email = %s AND blocked_until > NOW()", (email,))
    is_blocked = cursor.fetchone() is not None

    return {"isBlocked": is_blocked}


if __name__ == "__main__":
    threading.Thread(target=cleanup_and_reset_block, daemon=True).start()
    app.run(debug=True) 