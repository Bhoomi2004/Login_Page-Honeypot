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
import traceback
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import bcrypt
from PIL import Image, ImageDraw, ImageFont
import io
import base64

app = Flask(__name__, template_folder='.')
app.secret_key = 'your_secret_key'

# Database connection
conn = psycopg2.connect("postgresql://postgres:SupaDb%401305@db.zgoxbenfdplceawwmjpx.supabase.co:5432/postgres")
cursor = conn.cursor()
global_blocked = False


def cleanup_and_reset_block():
    global global_blocked
    while True:
        try:
            # Delete expired blocked emails
            cursor.execute("DELETE FROM blocked_emails WHERE blocked_until <= NOW()")
            conn.commit()  # Commit after delete
            
            deleted_rows = cursor.rowcount
            print(f"✅ Expired entries cleaned up. {deleted_rows} entries removed.")

            # Check if any active blocked entries remain
            cursor.execute("SELECT COUNT(*) FROM blocked_emails WHERE blocked_until > NOW()")
            active_count = cursor.fetchone()[0]
            
            if active_count == 0 and global_blocked:
                print("✅ Resetting global block state.")
                global_blocked = False

        except Exception as e:
            print("❌ Error occurred during cleanup:", e)
            traceback.print_exc()
            conn.rollback()  # Reset the failed transaction state before next iteration

        time.sleep(420)  # Run every 7 minutes (420 seconds)


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

    # Call check_email_breach and send an email if the user email is part of a known breach
    check_email_breach(email)
    

    if honeypot:
        cursor.execute("INSERT INTO failed_ips (ip_address, failed_attempts, last_attempt) VALUES (%s, 100, NOW()) "
                       "ON CONFLICT (ip_address) DO UPDATE SET failed_attempts = 100, last_attempt = NOW()", (ip,))
        conn.commit()
        print(f"[DEBUG] IP Blocked: {ip}")
        flash("Your IP has been permanently blocked.", "danger")
        return redirect(url_for("captcha_page"))

    # Check if the system is already in a blocked state
    if global_blocked:
        flash("Invalid password.", "danger")
        return redirect(url_for("captcha_page"))

    cursor.execute("SELECT COUNT(*) FROM failed_ips WHERE ip_address = %s AND failed_attempts >= 100", (ip,))
    ip_blocked = cursor.fetchone()[0]

    if ip_blocked:
        flash("Your IP has been permanently blocked.", "danger")
        return redirect(url_for("captcha_page"))
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
        cursor.execute("INSERT INTO users_logins (user_id, login_time, ip_address) "
                   "VALUES (%s, NOW(), %s)", (user[0], ip))
        conn.commit()
        return redirect(url_for('index'))

    # Update failed attempts
    cursor.execute("SELECT failed_attempts FROM users WHERE email = %s", (email,))
    failed_attempts = cursor.fetchone()[0] + 1
    cursor.execute("UPDATE users SET failed_attempts = %s WHERE email = %s", (failed_attempts, email))

    # Block logic
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
    
    elif failed_attempts % 5 == 0:
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


#---------------------------------------------------------------------------------
# Check if the email is part of a known breach
def check_email_breach(email):
    # Simulate a 15% chance of breach, or check if the email is in known breaches
    known_breaches = [
        "charlie03@example.com",
        "eric05@example.com",
        "george07@example.com"
    ]
    
    # Convert email to lowercase for case-insensitive comparison
    if email.lower() in known_breaches:
        subject = "Urgent: Security Alert - Data Breach Notification"
        body = """
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #d9534f;">Urgent: Security Alert - Data Breach Notification</h2>
            
            <p>
                Dear User,<br><br>
                We want to inform you that your email address has been involved in a known data breach. 
                For your security, it is highly recommended that you change your password as soon as possible.
            </p>
            
            <p>
                Please take immediate action to update your credentials and secure your account. 
                If you need assistance or have any questions, don't hesitate to contact our support team.
            </p>

            <div style="text-align: center; margin: 20px 0;">
                <a href='https://example.com/change-password' 
                style="display: inline-block; padding: 10px 20px; background-color: #d9534f; 
                        color: #fff; text-decoration: none; border-radius: 4px;">
                Change Password
                </a>
            </div>

            <p>
                Please ensure that your devices are secure and be cautious of any suspicious activities.
            </p>

            <p style="margin-top: 20px;">Sincerely,<br> Your Security Team</p>
        </body>
        </html>
        """
        
        # Debugging message
        print(f"🚨 Email {email} found in breach list.")
        
        try:
            send_email(email, subject, body)
            print(f"Email sent to {email} regarding the data breach.")  # Log to console
        except Exception as e:
            print(f"Error sending email to {email}: {e}")  # Log any exception during email sending

        return True
    else:
        # If the email is not part of the known breaches, we return False
        print(f"Email {email} is not in the breach list.")  # Log that no breach was found
    return False


#--------------------------------------------------------------------------------------
from flask import session
# Generate a random string of 5 characters (digits or letters)
def generate_captcha_text():
    characters = string.ascii_letters + string.digits
    captcha_text = ''.join(random.choices(characters, k=5))
    return captcha_text

def generate_captcha_image(captcha_text):
    # Create an image with the captcha text
    width, height = 160, 60
    image = Image.new('RGB', (width, height), (255, 255, 255))  # White background
    draw = ImageDraw.Draw(image)

    # Use a TrueType font (make sure to include a valid font path)
    try:
        font = ImageFont.truetype("arial.ttf", 36)  # You can replace this with any TTF file available
    except IOError:
        font = ImageFont.load_default()  # Fallback to default if the TTF font is not available
    
    bbox = draw.textbbox((0, 0), captcha_text, font)  # Get the bounding box of the text
    text_width = bbox[2] - bbox[0]  # Width of the text
    text_height = bbox[3] - bbox[1]  # Height of the text

    # Position text in the center of the image
    text_position = ((width - text_width) / 2, (height - text_height) / 2)

    # Draw the text on the image with dark color for visibility
    draw.text(text_position, captcha_text, fill=(0, 0, 0), font=font)

    # Add noise to the image (random lines and dots to make it harder to read)
    for _ in range(10):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line([x1, y1, x2, y2], fill=(0, 0, 0), width=1)

    # Convert the image to a format that can be embedded in HTML (base64)
    img_io = io.BytesIO()
    image.save(img_io, 'PNG')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

    return img_base64

@app.route("/captcha", methods=["GET", "POST"])
def captcha_page():
    if request.method == "POST":
        user_input = request.form.get("captcha_answer")
        correct_answer = request.form.get("captcha_text")
        ip = request.remote_addr  # Get the user's IP address
        
        if user_input == correct_answer:
            cursor.execute("""
                UPDATE failed_ips 
                SET failed_attempts = 0, last_attempt = NOW() 
                WHERE ip_address = %s
            """, (ip,))
            conn.commit()
            flash("CAPTCHA verified. You can now log in.", "success")
            return redirect(url_for("login_page"))
        else:
            flash("Incorrect CAPTCHA. Try again.", "danger")
    
    # Generate a new CAPTCHA
    captcha_text = generate_captcha_text()
    captcha_image = generate_captcha_image(captcha_text)
    
    return render_template("captcha.html", captcha_image=captcha_image, captcha_text=captcha_text)

#---------------------------------------------------------------------
@app.route("/index")
def index():
    return render_template("index.html")

#---------------------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=cleanup_and_reset_block, daemon=True).start()
    app.run(debug=True) 