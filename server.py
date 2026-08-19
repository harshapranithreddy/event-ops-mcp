"""
EventOps :: MCP server
======================

Exposes MQIS event-ops analytics as Model Context Protocol tools, so an AI
client (Claude Desktop, Claude Code, Cursor) can answer questions grounded in
the real data instead of guessing.

Every tool here is a thin wrapper over deterministic pandas logic in
data_loader.py. The AI decides *which* tool to call and how to phrase the
result; the numbers themselves are always exact.

Run:
    python server.py
or register with an MCP client (see README.md).
"""

from mcp.server.fastmcp import FastMCP

from data_loader import get_data

mcp = FastMCP("EventOps")


@mcp.tool()
def list_events() -> list[dict]:
    """List every event and membership dataset available, with its key and label."""
    return get_data().event_names()


@mcp.tool()
def get_event_metrics(event_name: str) -> dict:
    """
    Headline numbers for one event: orders, valid tickets, revenue to MQIS
    (net of Humanitix fees), gross ticket sales, customer-paid total, the
    paid/free/refunded split, and the online-vs-manual sales-channel split.

    event_name accepts a loose match, e.g. "saazish" or "Diwali".
    """
    return get_data().event_metrics(event_name)


@mcp.tool()
def get_sales_curve(event_name: str) -> dict:
    """
    How ticket sales built up over time for an event: first/last sale,
    day-by-day sales, and how many tickets (and what %) sold in the final
    48 hours and final 7 days before the event. Useful for spotting how
    late-skewed demand was.
    """
    return get_data().sales_curve(event_name)


@mcp.tool()
def lookup_attendee(query: str) -> dict:
    """
    Find a person across ALL events and membership rosters by email or name.
    Returns their full ticket history, membership status, distinct events
    attended, total spend, and contact details.
    """
    return get_data().lookup_attendee(query)


@mcp.tool()
def find_loyal_members(min_events: int = 2) -> dict:
    """
    Regulars who attended at least `min_events` distinct events (default 2),
    ranked by attendance, with how many of them also hold a membership.
    """
    return get_data().loyal_members(min_events)


@mcp.tool()
def build_marketing_segment(target: str = "non-members", event_name: str = "") -> dict:
    """
    Build a CONSENT-AWARE contact list (only people with Marketing opt-in = Yes).
    target: 'non-members' (default), 'members', or 'all'.
    event_name: optional; limit to one event, else all events.
    """
    return get_data().marketing_segment(target, event_name or None)


@mcp.tool()
def portfolio_summary() -> dict:
    """Totals across every dataset: orders, tickets, revenue, and unique people."""
    return get_data().portfolio_summary()


if __name__ == "__main__":
    # Default transport is stdio, which is what MCP clients launch.
    mcp.run()
