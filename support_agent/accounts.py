"""
Customer log-in for the web page: mobile number + a 4-digit PIN.

The first time a number is used, the customer chooses a PIN. After that, the same
number only opens with the same PIN, so nobody can see another customer's tickets
just by typing their number.

PINs are never saved as they are. We save a scrambled version (a "hash") with a
random "salt", in customers.csv in the project folder.
"""

import csv
import hashlib
import hmac
import os
from pathlib import Path

CUSTOMERS_FILE = Path(__file__).resolve().parent.parent / "customers.csv"


def clean_phone(text: str) -> str:
    """Turns '+91 98765 43210' into '9876543210'. Returns '' if it isn't a 10-digit Indian mobile number."""
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]  # drop the +91
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return ""


def _scramble(pin: str, salt: str) -> str:
    """Makes the hash of a PIN. The same PIN and salt always give the same hash."""
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 200_000).hex()


def _read_customers() -> dict:
    """Returns {phone: (salt, pin_hash)} for every saved customer."""
    if not CUSTOMERS_FILE.exists():
        return {}
    with open(CUSTOMERS_FILE, newline="", encoding="utf-8") as f:
        return {row["phone"]: (row["salt"], row["pin_hash"]) for row in csv.DictReader(f)}


def is_registered(phone: str) -> bool:
    """True if this number has already chosen a PIN."""
    return phone in _read_customers()


def register(phone: str, pin: str):
    """Saves a new customer with their chosen PIN (scrambled)."""
    is_new_file = not CUSTOMERS_FILE.exists()
    salt = os.urandom(16).hex()
    with open(CUSTOMERS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(["phone", "salt", "pin_hash"])
        writer.writerow([phone, salt, _scramble(pin, salt)])


def check_pin(phone: str, pin: str) -> bool:
    """True only if this number exists and the PIN matches."""
    saved = _read_customers().get(phone)
    if not saved:
        return False
    salt, pin_hash = saved
    return hmac.compare_digest(_scramble(pin, salt), pin_hash)
