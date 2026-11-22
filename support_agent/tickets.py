"""
Support tickets (hand-off to a person).

When Tiffy hands a customer over to a person, it saves a ticket as a row in
tickets.csv in the project folder. Ticket IDs are made here by the code
(TKT-1001, TKT-1002, ...), never by the model, so they never repeat.
"""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

# tickets.csv sits in the project folder (one level above this support_agent folder).
TICKETS_FILE = Path(__file__).resolve().parent.parent / "tickets.csv"

# The columns of the file, in order.
# Ticket times are shown in Indian time (IST), also on Streamlit Cloud.
IST = timezone(timedelta(hours=5, minutes=30))

HEADER = ["ticket_id", "time", "message", "reason", "priority", "status"]


def _next_ticket_id() -> str:
    """Find the biggest ticket number so far and return the next ID (TKT-1001 for the first one)."""
    biggest = 1000
    if TICKETS_FILE.exists():
        with open(TICKETS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    biggest = max(biggest, int(row["ticket_id"].split("-")[1]))
                except (KeyError, ValueError, IndexError, AttributeError):
                    pass  # skip a row we can't read
    return f"TKT-{biggest + 1}"


def create_ticket(message: str, reason: str, priority: str = "normal") -> dict:
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
    priority = "high" if str(priority).strip().lower() == "high" else "normal"
    ticket_id = _next_ticket_id()
    is_new_file = not TICKETS_FILE.exists()

    with open(TICKETS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(HEADER)  # header row only when the file is new
        writer.writerow([
            ticket_id,
            datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
            message,
            reason,
            priority,
            "open",
        ])

    return {"status": "success", "ticket_id": ticket_id}


def open_tickets() -> list:
    """Returns all tickets with status "open", newest first (used by the web page's sidebar)."""
    if not TICKETS_FILE.exists():
        return []
    with open(TICKETS_FILE, newline="", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row.get("status") == "open"]
    return list(reversed(rows))
