"""
Generate SYNTHETIC sample data for EventOps.
============================================

Writes fake CSVs into ./sample_data with the exact same schema as the real
Humanitix exports, so the project runs for anyone who clones the repo WITHOUT
ever exposing real attendee PII. The real files live in ./data (git-ignored).

    python gen_sample_data.py
"""

import os
import random

import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample_data")
os.makedirs(OUT, exist_ok=True)

COLUMNS = [
    "Order id", "Event", "Event date", "Event time", "First name", "Last name",
    "Email", "Mobile", "Order date", "Type", "Financial status", "Valid tickets",
    "Cancelled tickets", "Ticket sales", "Add-on sales", "Donations", "Fee rebate",
    "Humanitix passed-on fee", "Amex surcharge", "Refund protection", "Custom tax",
    "Paid", "Humanitix absorbed fees", "Zip fee", "Afterpay fee", "Refunds",
    "Your earnings", "Your payout", "Refunded fees", "Giftcard used", "Voucher used",
    "Discount code used", "Discount redeemed", "Tax on sales", "Tax on rebates",
    "Tax on booking fees", "Gateway", "Marketing opt-in", "Notes", "Status",
    "Sales channel", "Tickets delivered", "Long order id",
]

# (event name, file stem, event date, n orders, price, free?)
EVENTS = [
    ("Ganeshotsav",           "Ganesh",          "2026-08-30", 700, 0,   True),
    ("UTSAV Garba 2025",      "Garba2025",       "2025-09-26", 370, 40,  False),
    ("Gulaal Holi",           "Gulaal",          "2026-03-14", 620, 25,  False),
    ("Raaz Mid-Sem Cruise",   "Raaz",            "2025-04-11", 375, 35,  False),
    ("Saazish Mid-Sem Cruise","Saazish",         "2026-04-09", 275, 38,  False),
    ("Shaandaar Diwali Cruise","Shaandaar",      "2024-10-26", 275, 45,  False),
    ("MQIS Membership 2025",  "Memberships 2025","2025-02-24", 630, 5,   False),
    ("MQIS Membership",       "Memberships",     "2024-02-20", 410, 5,   False),
]

# a shared pool of people so the same person recurs across events (loyalty)
POOL = [(fake.first_name(), fake.last_name()) for _ in range(1500)]
POOL_EMAILS = {p: f"{p[0].lower()}.{p[1].lower()}{random.randint(1,99)}@example.com" for p in POOL}


def money(x):
    return f"${x:,.2f}"


def gen_event(name, stem, date, n, price, free):
    rows = []
    for i in range(n):
        person = random.choice(POOL)
        first, last = person
        email = POOL_EMAILS[person]
        tickets = 1 if "Member" in name else random.choices([1, 2, 3, 4], [50, 30, 15, 5])[0]
        channel = random.choices(["Online", "Manual"], [88, 12])[0]
        status = "Free" if free else random.choices(["Paid", "Refunded"], [97, 3])[0]
        gross = 0 if free or status == "Refunded" else price * tickets
        fee = round(gross * 0.04, 2) if gross else 0
        paid = round(gross + fee, 2)
        order_dt = fake.date_time_between(start_date="-40d", end_date="-1d")
        rows.append({
            "Order id": f"{stem[:3].upper()}{1000+i}",
            "Event": name,
            "Event date": pd.to_datetime(date).strftime("%d/%m/%Y"),
            "Event time": "7:00 pm",
            "First name": first, "Last name": last,
            "Email": email, "Mobile": fake.msisdn()[:10],
            "Order date": order_dt.strftime("%d/%m/%Y %I:%M %p").lower(),
            "Type": channel, "Financial status": status,
            "Valid tickets": 0 if status == "Refunded" else tickets,
            "Cancelled tickets": tickets if status == "Refunded" else 0,
            "Ticket sales": money(gross), "Add-on sales": money(0), "Donations": money(0),
            "Fee rebate": money(0), "Humanitix passed-on fee": money(fee),
            "Amex surcharge": money(0), "Refund protection": money(0), "Custom tax": money(0),
            "Paid": money(paid), "Humanitix absorbed fees": money(0), "Zip fee": money(0),
            "Afterpay fee": money(0), "Refunds": money(paid if status == "Refunded" else 0),
            "Your earnings": money(gross), "Your payout": money(gross), "Refunded fees": money(0),
            "Giftcard used": "", "Voucher used": "", "Discount code used": "",
            "Discount redeemed": money(0), "Tax on sales": money(0), "Tax on rebates": money(0),
            "Tax on booking fees": money(0), "Gateway": "Stripe",
            "Marketing opt-in": random.choices(["Yes", "No"], [35, 65])[0],
            "Notes": "", "Status": "Completed", "Sales channel": channel,
            "Tickets delivered": tickets, "Long order id": fake.uuid4(),
        })
    return pd.DataFrame(rows, columns=COLUMNS)


if __name__ == "__main__":
    for name, stem, date, n, price, free in EVENTS:
        df = gen_event(name, stem, date, n, price, free)
        df.to_csv(os.path.join(OUT, f"{stem}.csv"), index=False)
        print(f"wrote sample_data/{stem}.csv  ({n} rows)")
    print("\nSynthetic sample data ready. Safe to commit. Real data stays in ./data (git-ignored).")
