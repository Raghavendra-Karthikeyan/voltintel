"""
email_alert.py - Sends peak-consumption alert emails
---------------------------------------------------------
Uses Gmail's SMTP server. Requires a Gmail "App Password" (not your
regular Gmail password) - generate one at:
https://myaccount.google.com/apppasswords
(Requires 2-Step Verification to be enabled on the Gmail account first.)

Fill in SENDER_EMAIL and SENDER_APP_PASSWORD below before use.
"""

import smtplib
from email.mime.text import MIMEText

SENDER_EMAIL = "harish14141407@gmail.com"       # <-- fill this in
SENDER_APP_PASSWORD = "qvrt ezye kthz ekge"    # <-- fill this in


def send_peak_alert(to_emails, predicted_power, predicted_time, reason, tip):
    if not to_emails:
        return  # no registered users to notify

    if SENDER_EMAIL.startswith("YOUR_"):
        print("[email_alert] Skipped: SENDER_EMAIL/APP_PASSWORD not configured yet.")
        return

    subject = "⚡ Peak Power Consumption Alert"
    body = f"""Your Smart Meter has detected an upcoming peak consumption event.

Predicted Power: {predicted_power} W
Predicted Time:  {predicted_time}
Likely Cause:    {reason}
Recommendation:  {tip}

This is an automated alert from your Smart Energy Meter dashboard.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(to_emails)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_emails, msg.as_string())
        print(f"[email_alert] Sent peak alert to {len(to_emails)} user(s).")
    except Exception as e:
        print(f"[email_alert] Failed to send: {e}")
