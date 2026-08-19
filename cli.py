"""
EventOps :: AI operations CLI
=============================

A terminal tool that turns the deterministic analytics in data_loader.py into
written, ready-to-use output using the Anthropic API. The numbers are computed
in Python and passed to the model as grounded context; the model only writes
the prose, so it cannot invent figures.

Commands
--------
    python cli.py summary
    python cli.py report      --event "Saazish"
    python cli.py compare     --e1 "Raaz" --e2 "Saazish"
    python cli.py draft-email --type promo --target non-members [--event "Gulaal"]
    python cli.py attendee    --query "john@example.com"

Setup
-----
    export ANTHROPIC_API_KEY=sk-ant-...
    # optional: pin the model (defaults to a current Sonnet)
    export ANTHROPIC_MODEL=claude-sonnet-4-5

Add --raw to any command to print the underlying JSON facts instead of the
AI-written version (useful for debugging and for showing the tools are exact).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from data_loader import get_data

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")


# --------------------------------------------------------------------------
# LLM helper
# --------------------------------------------------------------------------

def write_with_claude(system: str, facts: dict, instruction: str) -> str:
    """Send grounded facts to Claude and return written prose."""
    try:
        import anthropic
    except ImportError:
        sys.exit("The 'anthropic' package is not installed. Run: pip install anthropic")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first:  export ANTHROPIC_API_KEY=sk-ant-...")

    client = anthropic.Anthropic()
    prompt = (
        f"{instruction}\n\n"
        "Use ONLY the figures in the JSON below. Do not invent numbers. "
        "If a figure is not present, do not guess it.\n\n"
        f"DATA:\n{json.dumps(facts, indent=2)}"
    )
    msg = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")


SYSTEM_ANALYST = (
    "You are the operations analyst for MQIS, a university student society that "
    "runs cultural events and cruise parties. You write concise, factual internal "
    "summaries for the committee. Plain, direct language. No hype, no em dashes."
)
SYSTEM_MARKETER = (
    "You write short, warm marketing and check-in emails for MQIS, a university "
    "Indian student society. Friendly and student-appropriate. No hype, no em dashes. "
    "Keep it under 150 words and leave clear [PLACEHOLDERS] for links and dates."
)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_summary(args):
    facts = get_data().portfolio_summary()
    if args.raw:
        return print(json.dumps(facts, indent=2))
    out = write_with_claude(
        SYSTEM_ANALYST, facts,
        "Write a 4-5 sentence portfolio summary of MQIS event operations for the committee.",
    )
    print(out)


def cmd_report(args):
    data = get_data()
    facts = {
        "metrics": data.event_metrics(args.event),
        "sales_curve": data.sales_curve(args.event),
    }
    if args.raw:
        return print(json.dumps(facts, indent=2))
    if "error" in facts["metrics"]:
        sys.exit(facts["metrics"]["error"])
    out = write_with_claude(
        SYSTEM_ANALYST, facts,
        f"Write an executive performance breakdown for the event '{args.event}'. "
        "Cover turnout, revenue to MQIS, sales channels, and how late demand skewed "
        "(use the sales-curve figures). End with one practical takeaway for next time.",
    )
    print(out)


def cmd_compare(args):
    data = get_data()
    facts = {
        "event_1": {"metrics": data.event_metrics(args.e1), "sales_curve": data.sales_curve(args.e1)},
        "event_2": {"metrics": data.event_metrics(args.e2), "sales_curve": data.sales_curve(args.e2)},
    }
    if args.raw:
        return print(json.dumps(facts, indent=2))
    out = write_with_claude(
        SYSTEM_ANALYST, facts,
        f"Compare '{args.e1}' and '{args.e2}' across turnout, revenue to MQIS, sales "
        "channel mix, and sales timing. Be specific with the numbers and say which "
        "performed better and why.",
    )
    print(out)


def cmd_draft_email(args):
    data = get_data()
    segment = data.marketing_segment(args.target, args.event or None)
    facts = {"email_type": args.type, "segment": {k: v for k, v in segment.items() if k != "contacts"},
             "sample_recipients": segment.get("contacts", [])[:5]}
    if args.raw:
        return print(json.dumps(facts, indent=2))
    kind = {"promo": "a promotional email inviting them to the next event",
            "checkin": "a friendly check-in / thank-you email",
            "renewal": "a membership renewal reminder"}.get(args.type, "an email")
    out = write_with_claude(
        SYSTEM_MARKETER, facts,
        f"Draft {kind} for the '{args.target}' segment "
        f"({segment.get('consented_contacts', 0)} consenting recipients). "
        "Note at the top that this list already respects marketing opt-in.",
    )
    print(out)
    print(f"\n---\nSegment: {segment.get('consented_contacts', 0)} opted-in contacts "
          f"({segment.get('note')})")


def cmd_attendee(args):
    facts = get_data().lookup_attendee(args.query)
    if args.raw:
        return print(json.dumps(facts, indent=2))
    print(json.dumps(facts, indent=2))  # lookup is already human-readable


# --------------------------------------------------------------------------
# Arg parsing
# --------------------------------------------------------------------------

def build_parser():
    # shared parent so --raw works before OR after the subcommand
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--raw", action="store_true", help="print underlying JSON facts, no AI")

    p = argparse.ArgumentParser(prog="eventops", parents=[common],
                                description="AI ops CLI for MQIS event data.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", parents=[common], help="portfolio-wide summary").set_defaults(func=cmd_summary)

    r = sub.add_parser("report", parents=[common], help="executive breakdown for one event")
    r.add_argument("--event", required=True)
    r.set_defaults(func=cmd_report)

    c = sub.add_parser("compare", parents=[common], help="compare two events")
    c.add_argument("--e1", required=True)
    c.add_argument("--e2", required=True)
    c.set_defaults(func=cmd_compare)

    e = sub.add_parser("draft-email", parents=[common], help="draft a consent-aware email")
    e.add_argument("--type", default="promo", choices=["promo", "checkin", "renewal"])
    e.add_argument("--target", default="non-members", choices=["non-members", "members", "all"])
    e.add_argument("--event", default="")
    e.set_defaults(func=cmd_draft_email)

    a = sub.add_parser("attendee", parents=[common], help="look up one attendee across all events")
    a.add_argument("--query", required=True)
    a.set_defaults(func=cmd_attendee)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
