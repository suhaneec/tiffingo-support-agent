"""
Support tickets (hand-off to a person) and chat ratings.

When Tiffy hands a customer over to a person, it saves a ticket as a row in
tickets.csv in the project folder. Ticket IDs are made here by the code
(TKT-1001, TKT-1002, ...), never by the model, so they never repeat.

Every ticket remembers which customer (phone number) it belongs to, so a
customer only ever sees their own tickets.
"""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.adk.tools import ToolContext

# tickets.csv and ratings.csv sit in the project folder (one level above this folder).
PROJECT_DIR = Path(__file__).resolve().parent.parent
TICKETS_FILE = PROJECT_DIR / "tickets.csv"
RATINGS_FILE = PROJECT_DIR / "ratings.csv"

# Ticket times are shown in Indian time (IST), also on Streamlit Cloud.
IST = timezone(timedelta(hours=5, minutes=30))

# The columns of each file, in order.
HEADER = ["ticket_id", "customer", "time", "message", "reason", "priority", "status"]
RATINGS_HEADER = ["time", "customer", "chat_stars", "solved_stars", "comment"]


def _now():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")


def _read_tickets() -> list:
    """Reads every ticket in the file (oldest first)."""
    if not TICKETS_FILE.exists():
        return []
    with open(TICKETS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_tickets(rows: list):
    """Writes all tickets back to the file (the file is small, so this is quick)."""
    with open(TICKETS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) or "" for name in HEADER})


def save_ticket(customer: str, message: str, reason: str, priority: str = "normal") -> str:
    """Saves a new open ticket for this customer and returns its ID (used by Tiffy and by the web page)."""
    rows = _read_tickets()

    # The next ID is one more than the biggest ticket number so far (TKT-1001 for the first one).
    biggest = 1000
    for row in rows:
        try:
            biggest = max(biggest, int(row["ticket_id"].split("-")[1]))
        except (KeyError, ValueError, IndexError, AttributeError):
            pass  # skip a row we can't read
    ticket_id = f"TKT-{biggest + 1}"

    rows.append({
        "ticket_id": ticket_id,
        "customer": customer,
        "time": _now(),
        "message": message,
        "reason": reason,
        "priority": "high" if str(priority).strip().lower() == "high" else "normal",
        "status": "open",
    })
    _write_tickets(rows)
    return ticket_id


def create_ticket(message: str, reason: str, priority: str = "normal", tool_context: ToolContext = None) -> dict:
    """Saves a support ticket so a person from the TiffinGo team can follow up.

    Call this when: the customer feels unwell after a meal (priority "high"); asks for a
    refund above ₹1,000; complains about a rider; is angry or upset; asks for a person;
    or the help docs don't answer their question.

    Args:
        message: The customer's message, or a one-line summary of their problem.
        reason: Why we are handing over, for example "unwell after meal", "refund above 1000",
            "rider complaint", "angry customer", "not in help docs" or "asked for a person".
        priority: "high" if the customer feels unwell after a meal, otherwise "normal".

    Returns:
        A dict with the new "ticket_id".
    """
    # The customer is the logged-in person chatting (ADK fills tool_context in, not the model).
    customer = tool_context.user_id if tool_context else "unknown"
    return {"status": "success", "ticket_id": save_ticket(customer, message, reason, priority)}


def customer_tickets(customer: str) -> list:
    """Returns only this customer's tickets, newest first (used by the web page)."""
    return [row for row in reversed(_read_tickets()) if row.get("customer") == customer]


def close_ticket(ticket_id: str, customer: str):
    """Marks a ticket as closed, but only if it belongs to this customer."""
    rows = _read_tickets()
    for row in rows:
        if row.get("ticket_id") == ticket_id and row.get("customer") == customer:
            row["status"] = "closed"
    _write_tickets(rows)


def save_rating(customer: str, chat_stars: int, solved_stars: int, comment: str):
    """Saves the customer's ratings for a finished chat in ratings.csv."""
    is_new_file = not RATINGS_FILE.exists()
    with open(RATINGS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(RATINGS_HEADER)
        writer.writerow([_now(), customer, chat_stars, solved_stars, comment])
