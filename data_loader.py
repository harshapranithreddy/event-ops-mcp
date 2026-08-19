"""
EventOps :: data layer
======================

Loads MQIS Humanitix ticketing/membership exports, cleans them, and exposes
deterministic analytics. All numbers returned here come straight from pandas,
never from a language model, so figures are always exact and reproducible.

The MCP server (server.py) and the AI CLI (cli.py) both call into the single
`EventData` object defined here. That separation is deliberate: the tools stay
factual, and the LLM is only ever used to phrase those facts, never to invent
them.
"""

from __future__ import annotations

import os
import glob
import re
from dataclasses import dataclass, field

import pandas as pd


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Where the CSVs live. Real attendee data goes in ./data (git-ignored).
# If ./data is empty, we fall back to ./sample_data (synthetic, safe to commit)
# so the project runs for anyone who clones it.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENV_DIR = os.environ.get("EVENTOPS_DATA_DIR")

# Human-friendly event labels keyed by file stem. Anything not listed here
# falls back to the raw file name, so new exports still load without edits.
EVENT_LABELS = {
    "Ganesh": "Ganeshotsav",
    "Garba2025": "UTSAV Garba 2025",
    "Gulaal": "Gulaal (Holi)",
    "Raaz": "Raaz Mid-Sem Cruise",
    "Saazish": "Saazish Mid-Sem Cruise",
    "Shaandaar": "Shaandaar Diwali Cruise",
    "Memberships 2025": "MQIS Memberships (2025)",
    "Memberships": "MQIS Memberships",
}

# File stems treated as membership rosters rather than ticketed events.
MEMBERSHIP_STEMS = {"Memberships", "Memberships 2025"}


def _resolve_data_dir() -> str:
    if _ENV_DIR and _has_csvs(_ENV_DIR):
        return _ENV_DIR
    real = os.path.join(_HERE, "data")
    if _has_csvs(real):
        return real
    return os.path.join(_HERE, "sample_data")


def _has_csvs(path: str) -> bool:
    return os.path.isdir(path) and bool(glob.glob(os.path.join(path, "*.csv")))


# --------------------------------------------------------------------------
# Cleaning helpers
# --------------------------------------------------------------------------

def clean_money(series: pd.Series) -> pd.Series:
    """'$14,669.16' -> 14669.16 (float). Blanks/garbage -> 0.0."""
    cleaned = (
        series.astype(str)
        .str.replace(r"[,$]", "", regex=True)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def clean_email(series: pd.Series) -> pd.Series:
    """Lower-case and strip so the same person joins across files."""
    return series.astype(str).str.lower().str.strip().replace({"nan": ""})


def parse_dt(series: pd.Series) -> pd.Series:
    """Humanitix uses day-first timestamps like '11/04/2025 12:43 am'."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(series, dayfirst=True, errors="coerce")


# Money columns and what they actually mean (documented for honesty):
#   Ticket sales  -> gross face value of tickets
#   Paid          -> what the customer paid, incl. Humanitix fees
#   Your earnings -> what MQIS actually received  (this is "revenue to MQIS")
MONEY_COLS = ["Ticket sales", "Paid", "Your earnings", "Your payout", "Refunds"]


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class EventData:
    data_dir: str = field(default_factory=_resolve_data_dir)
    frames: dict = field(default_factory=dict)   # stem -> cleaned DataFrame
    all_rows: pd.DataFrame = field(default=None)

    def __post_init__(self):
        self.load()

    # ---- loading ---------------------------------------------------------

    def load(self) -> None:
        paths = sorted(glob.glob(os.path.join(self.data_dir, "*.csv")))
        if not paths:
            raise FileNotFoundError(
                f"No CSV files found in {self.data_dir!r}. "
                "Put your Humanitix exports in ./data (or set EVENTOPS_DATA_DIR)."
            )
        frames = {}
        for p in paths:
            stem = os.path.splitext(os.path.basename(p))[0]
            df = pd.read_csv(p)
            df = self._clean_frame(df, stem)
            frames[stem] = df
        self.frames = frames
        self.all_rows = pd.concat(frames.values(), ignore_index=True)

    def _clean_frame(self, df: pd.DataFrame, stem: str) -> pd.DataFrame:
        df = df.copy()
        for col in MONEY_COLS:
            if col in df.columns:
                df[col] = clean_money(df[col])
        if "Email" in df.columns:
            df["Email"] = clean_email(df["Email"])
        if "Order date" in df.columns:
            df["Order dt"] = parse_dt(df["Order date"])
        if "Event date" in df.columns:
            df["Event dt"] = parse_dt(df["Event date"])
        if "Valid tickets" in df.columns:
            df["Valid tickets"] = pd.to_numeric(df["Valid tickets"], errors="coerce").fillna(0).astype(int)
        # provenance + friendly label
        df["source_file"] = stem
        df["event_label"] = EVENT_LABELS.get(stem, stem)
        df["is_membership"] = stem in MEMBERSHIP_STEMS
        return df

    # ---- name resolution -------------------------------------------------

    def resolve_event(self, query: str) -> str | None:
        """Fuzzy-match a user string to a file stem. 'saazish' -> 'Saazish'."""
        if not query:
            return None
        q = query.lower().strip()
        # exact stem
        for stem in self.frames:
            if stem.lower() == q:
                return stem
        # label or substring match
        for stem in self.frames:
            label = EVENT_LABELS.get(stem, stem).lower()
            if q in stem.lower() or q in label:
                return stem
        return None

    def event_names(self) -> list[str]:
        return [
            {"key": stem, "label": EVENT_LABELS.get(stem, stem),
             "is_membership": stem in MEMBERSHIP_STEMS}
            for stem in self.frames
        ]

    # ---- tool: event metrics --------------------------------------------

    def event_metrics(self, event_name: str) -> dict:
        stem = self.resolve_event(event_name)
        if not stem:
            return {"error": f"No event matching {event_name!r}.",
                    "available": [e["key"] for e in self.event_names()]}
        df = self.frames[stem]

        status = df.get("Financial status", pd.Series(dtype=str)).astype(str)
        channel = df.get("Sales channel", pd.Series(dtype=str)).astype(str)

        metrics = {
            "event": EVENT_LABELS.get(stem, stem),
            "file": stem,
            "orders": int(len(df)),
            "valid_tickets": int(df["Valid tickets"].sum()) if "Valid tickets" in df else int(len(df)),
            "revenue_to_mqis_aud": round(float(df.get("Your earnings", pd.Series([0])).sum()), 2),
            "gross_ticket_sales_aud": round(float(df.get("Ticket sales", pd.Series([0])).sum()), 2),
            "customer_paid_aud": round(float(df.get("Paid", pd.Series([0])).sum()), 2),
            "financial_status": {k: int(v) for k, v in status.value_counts().items()},
            "sales_channel": {k: int(v) for k, v in channel.value_counts().items()},
        }
        if "Event dt" in df and df["Event dt"].notna().any():
            metrics["event_date"] = df["Event dt"].dropna().iloc[0].strftime("%d %b %Y")
        return metrics

    # ---- tool: sales curve ----------------------------------------------

    def sales_curve(self, event_name: str) -> dict:
        stem = self.resolve_event(event_name)
        if not stem:
            return {"error": f"No event matching {event_name!r}."}
        df = self.frames[stem]
        if "Order dt" not in df or df["Order dt"].notna().sum() == 0:
            return {"error": "No order timestamps available for this event."}

        d = df.dropna(subset=["Order dt"]).sort_values("Order dt").copy()
        d["tickets"] = d["Valid tickets"] if "Valid tickets" in d else 1
        total = int(d["tickets"].sum())

        # daily sales
        daily = (
            d.set_index("Order dt")["tickets"]
            .resample("D").sum()
        )
        daily_out = [{"date": ts.strftime("%Y-%m-%d"), "tickets": int(v)}
                     for ts, v in daily.items() if v > 0]

        out = {
            "event": EVENT_LABELS.get(stem, stem),
            "total_tickets": total,
            "first_sale": d["Order dt"].min().strftime("%Y-%m-%d %H:%M"),
            "last_sale": d["Order dt"].max().strftime("%Y-%m-%d %H:%M"),
            "daily_sales": daily_out,
        }

        # time-to-sellout relative to the event date
        if "Event dt" in d and d["Event dt"].notna().any():
            event_dt = d["Event dt"].dropna().iloc[0]
            out["event_date"] = event_dt.strftime("%Y-%m-%d")
            d["days_before"] = (event_dt.normalize() - d["Order dt"].dt.normalize()).dt.days
            cum = d.sort_values("Order dt")["tickets"].cumsum()
            for window, label in [(2, "final_48h"), (7, "final_7d")]:
                sold = int(d.loc[d["days_before"] <= window, "tickets"].sum())
                out[f"{label}_tickets"] = sold
                out[f"{label}_pct"] = round(100 * sold / total, 1) if total else 0.0
        return out

    # ---- tool: attendee lookup ------------------------------------------

    def lookup_attendee(self, query: str) -> dict:
        q = (query or "").lower().strip()
        if not q:
            return {"error": "Empty query."}
        rows = self.all_rows
        name = (rows["First name"].astype(str) + " " + rows["Last name"].astype(str)).str.lower()
        mask = rows["Email"].str.contains(re.escape(q), na=False) | name.str.contains(re.escape(q), na=False)
        hits = rows[mask]
        if hits.empty:
            return {"query": query, "matches": 0, "history": []}

        # pick the dominant identity (most common email among hits)
        emails = [e for e in hits["Email"].tolist() if e]
        primary_email = max(set(emails), key=emails.count) if emails else None
        person = hits[hits["Email"] == primary_email] if primary_email else hits

        history = []
        for _, r in person.sort_values("Order dt").iterrows():
            history.append({
                "event": r.get("event_label"),
                "order_date": r["Order dt"].strftime("%Y-%m-%d") if pd.notna(r.get("Order dt")) else None,
                "tickets": int(r.get("Valid tickets", 0)),
                "paid_aud": round(float(r.get("Paid", 0)), 2),
                "is_membership": bool(r.get("is_membership")),
            })
        events_attended = person.loc[~person["is_membership"], "source_file"].nunique()
        return {
            "name": f"{person.iloc[0]['First name']} {person.iloc[0]['Last name']}",
            "email": primary_email,
            "mobile": str(person.iloc[0].get("Mobile", "")),
            "is_member": bool(person["is_membership"].any()),
            "distinct_events_attended": int(events_attended),
            "total_spend_aud": round(float(person.get("Paid", pd.Series([0])).sum()), 2),
            "history": history,
        }

    # ---- tool: loyal members --------------------------------------------

    def loyal_members(self, min_events: int = 2) -> dict:
        rows = self.all_rows
        events = rows[~rows["is_membership"]]
        members = set(rows.loc[rows["is_membership"], "Email"]) - {""}

        # distinct events per email
        by_email = events[events["Email"] != ""].groupby("Email")
        counts = by_email["source_file"].nunique()
        loyal = counts[counts >= min_events].sort_values(ascending=False)

        people = []
        for email, n in loyal.items():
            sub = events[events["Email"] == email]
            people.append({
                "name": f"{sub.iloc[0]['First name']} {sub.iloc[0]['Last name']}",
                "email": email,
                "events_attended": int(n),
                "is_member": email in members,
                "total_spend_aud": round(float(sub.get("Paid", pd.Series([0])).sum()), 2),
            })
        return {
            "min_events": min_events,
            "count": len(people),
            "members_among_them": sum(1 for p in people if p["is_member"]),
            "people": people[:200],
        }

    # ---- tool/helper: marketing segment (consent-aware) -----------------

    def marketing_segment(self, target: str = "non-members", event_name: str | None = None) -> dict:
        """
        Build a contactable list that RESPECTS marketing opt-in.
        target: 'non-members' | 'members' | 'all'
        """
        rows = self.all_rows.copy()
        if event_name:
            stem = self.resolve_event(event_name)
            if stem:
                rows = self.frames[stem].copy()

        opt = rows.get("Marketing opt-in", pd.Series(dtype=str)).astype(str).str.lower()
        consented = rows[opt == "yes"].copy()

        members = set(self.all_rows.loc[self.all_rows["is_membership"], "Email"]) - {""}
        consented["is_member"] = consented["Email"].isin(members)

        if target == "members":
            seg = consented[consented["is_member"]]
        elif target == "all":
            seg = consented
        else:
            seg = consented[~consented["is_member"]]

        seg = seg[seg["Email"] != ""].drop_duplicates("Email")
        contacts = [
            {"name": f"{r['First name']} {r['Last name']}", "email": r["Email"]}
            for _, r in seg.iterrows()
        ]
        return {
            "target": target,
            "event": EVENT_LABELS.get(self.resolve_event(event_name), event_name) if event_name else "all events",
            "consented_contacts": len(contacts),
            "note": "Only includes people with Marketing opt-in = Yes.",
            "contacts": contacts[:500],
        }

    # ---- portfolio-wide summary -----------------------------------------

    def portfolio_summary(self) -> dict:
        events = self.all_rows[~self.all_rows["is_membership"]]
        return {
            "files": len(self.frames),
            "total_orders": int(len(self.all_rows)),
            "total_valid_tickets": int(self.all_rows["Valid tickets"].sum()),
            "event_revenue_to_mqis_aud": round(float(events.get("Your earnings", pd.Series([0])).sum()), 2),
            "event_gross_sales_aud": round(float(events.get("Ticket sales", pd.Series([0])).sum()), 2),
            "unique_people": int(self.all_rows.loc[self.all_rows["Email"] != "", "Email"].nunique()),
        }


# convenience singleton for the server/CLI
_DATA: EventData | None = None


def get_data() -> EventData:
    global _DATA
    if _DATA is None:
        _DATA = EventData()
    return _DATA


if __name__ == "__main__":
    d = get_data()
    import json
    print("Data dir:", d.data_dir)
    print(json.dumps(d.portfolio_summary(), indent=2))
