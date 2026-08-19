# EventOps: an MCP server + AI CLI for event operations

EventOps turns years of messy event ticketing exports into something an AI tool
can actually reason about. It exposes MQIS event and membership data (Humanitix
exports) to any Model Context Protocol client (Claude Desktop, Claude Code,
Cursor) as a set of deterministic tools, and ships a small AI-enabled command
line tool that writes ops reports and consent-aware emails on top of those same
tools.

I built it to give my AI tools *project-specific context* instead of generic
answers. That is the whole idea: the AI can call `get_event_metrics("Saazish")`
and get the exact figure, rather than guessing.

## Design principle: deterministic tools, AI for narrative

Every number comes from pandas, never from a language model. The MCP tools and
the CLI both call into one `EventData` object (`data_loader.py`) that does the
counting. The AI only decides *which* tool to call and how to phrase the result.
It cannot invent a revenue figure, because it never computes one. This is the
single most important property of the project.

## What it does (real numbers from my own events)

Across 8 datasets: 3,690 orders, 4,690 valid tickets, ~2,770 unique people, and
about A$61.4k in revenue to MQIS (net of platform fees; ~A$62.1k gross ticket
sales). 238 people attended 2 or more distinct events, 69 of whom also held a
membership.

Three money columns exist in the source data and they are not the same thing:
`Ticket sales` (gross face value), `Paid` (what the customer paid including
Humanitix fees), and `Your earnings` (what MQIS actually received). EventOps
reports `Your earnings` as "revenue to MQIS" so the headline number is honest.

## Tools exposed over MCP (`server.py`)

| Tool | What it returns |
|---|---|
| `list_events` | Every dataset with its key and label |
| `get_event_metrics(event_name)` | Orders, tickets, net + gross revenue, paid/free/refunded split, online vs manual channel |
| `get_sales_curve(event_name)` | Sales over time, plus % of tickets sold in the final 48h / 7 days |
| `lookup_attendee(query)` | One person's full history across all files, by email or name |
| `find_loyal_members(min_events=2)` | Cross-event regulars, and how many are members |
| `build_marketing_segment(target)` | A consent-aware contact list (opt-in = Yes only) |
| `portfolio_summary` | Totals across everything |

## AI CLI (`cli.py`)

```bash
python cli.py summary
python cli.py report      --event "Saazish"
python cli.py compare     --e1 "Raaz" --e2 "Saazish"
python cli.py draft-email --type promo --target non-members --event "Gulaal"
python cli.py attendee    --query "someone@example.com"
```

Add `--raw` to any command to print the underlying JSON facts instead of the
AI-written version. This is a good way to prove the tools are exact: the AI
output only ever restates the `--raw` numbers.

The `draft-email` command only ever includes people whose `Marketing opt-in` is
`Yes`, so it will not draft to anyone who did not consent.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Sample data (safe, synthetic) so it runs out of the box:
python gen_sample_data.py

# 2. Or use real data: drop your Humanitix CSV exports into ./data/
#    (that folder is git-ignored and never committed)

# 3. For the CLI, set your key:
cp .env.example .env   # then edit, or just:
export ANTHROPIC_API_KEY=sk-ant-...
```

If `./data` is empty, EventOps automatically falls back to `./sample_data`, so a
fresh clone works immediately.

## Registering the MCP server with a client

**Claude Desktop / Claude Code** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "eventops": {
      "command": "python",
      "args": ["/absolute/path/to/event-ops-mcp/server.py"]
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`): same shape. Restart the client, then ask it
things like "Using eventops, compare Raaz and Saazish" or "Who are our most loyal
attendees?" and it will call the tools.

## Data privacy

Real exports contain personal information (names, emails, phone numbers). They
live in `./data/`, which is git-ignored. Only the synthetic `./sample_data/` is
ever committed. Do not commit real attendee data.

## Files

```
event-ops-mcp/
├── data/                # real Humanitix CSVs (git-ignored, you provide)
├── sample_data/         # synthetic CSVs, safe to commit
├── data_loader.py       # cleaning + all deterministic analytics
├── server.py            # FastMCP server exposing the tools
├── cli.py               # AI-enabled CLI (Anthropic API)
├── gen_sample_data.py   # builds the synthetic dataset
├── requirements.txt
├── .env.example
└── .gitignore
```
