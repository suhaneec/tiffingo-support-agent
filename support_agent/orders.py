"""
Order status lookup (optional extra).

get_order_status() reads data/orders.csv. It shows an order only when BOTH the
order ID and the last 4 digits of the phone number match the same row, so one
customer can never see another customer's order.
"""

import csv
from pathlib import Path

ORDERS_FILE = Path(__file__).resolve().parent.parent / "data" / "orders.csv"


def get_order_status(order_id: str, phone_last4: str) -> dict:
    """Looks up one TiffinGo order. Needs BOTH the order ID and the last 4 digits of the phone number.

    Ask the customer for both before calling this. Never guess them.

    Args:
        order_id: The order ID, like TG1001.
        phone_last4: The last 4 digits of the phone number on the order.

    Returns:
        A dict with "status": "found" and the order details, or "status": "not found" with no details.
    """
    order_id = str(order_id).strip().upper()
    phone_last4 = "".join(ch for ch in str(phone_last4) if ch.isdigit())[-4:]

    with open(ORDERS_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["order_id"].upper() == order_id and row["phone_last4"] == phone_last4:
                # Only this one row is returned. The phone digits are not sent back.
                return {
                    "status": "found",
                    "order_id": row["order_id"],
                    "customer_name": row["customer_name"],
                    "items": row["items"],
                    "order_status": row["status"],
                    "order_time": row["order_time"],
                    "amount_inr": row["amount_inr"],
                }

    return {"status": "not found"}
