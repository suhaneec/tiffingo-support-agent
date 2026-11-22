"""
Customer log-in for the web page: email + a one-time code (OTP).

The customer types their email, we email them a 6-digit code from a Gmail account,
and they type the code back. Only someone who can open that inbox can log in, so
nobody can see another customer's tickets.

The Gmail address and its "app password" come from the settings
(OTP_EMAIL_ADDRESS and OTP_EMAIL_APP_PASSWORD in .env, or Streamlit secrets online).
They are never written in code.
"""

import hashlib
import hmac
import os
import re
import secrets
import smtplib
from email.message import EmailMessage

CODE_MINUTES = 10  # a code works for this many minutes


def clean_email(text: str) -> str:
    """Returns the email in small letters, or '' if it doesn't look like an email address."""
    email = str(text).strip().lower()
    return email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email) else ""


def new_code() -> str:
    """Makes a random 6-digit code, like 048213."""
    return f"{secrets.randbelow(1_000_000):06d}"


def scramble(code: str) -> str:
    """The code's hash. We keep only this, never the code itself."""
    return hashlib.sha256(code.encode()).hexdigest()


def code_matches(typed: str, saved_hash: str) -> bool:
    """True if the typed code is the one we sent."""
    return hmac.compare_digest(scramble(typed.strip()), saved_hash)


def send_code(to_email: str, code: str):
    """Emails the code to the customer from the TiffinGo Gmail account. Raises an error if sending fails."""
    sender = os.environ["OTP_EMAIL_ADDRESS"]
    message = EmailMessage()
    message["Subject"] = f"{code} is your TiffinGo login code"
    message["From"] = f"TiffinGo Support <{sender}>"
    message["To"] = to_email
    message.set_content(
        f"Hi!\n\nYour TiffinGo login code is: {code}\n\n"
        f"It works for {CODE_MINUTES} minutes. If you didn't ask for it, you can ignore this email.\n\n"
        "TiffinGo Support (a practice project, not a real company)"
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(sender, os.environ["OTP_EMAIL_APP_PASSWORD"])
        server.send_message(message)
