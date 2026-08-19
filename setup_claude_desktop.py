"""
One-time helper: registers the EventOps MCP server with Claude Desktop.
Run it with your Anaconda Python:
    /opt/anaconda3/bin/python3 setup_claude_desktop.py
It safely merges into any existing Claude Desktop config (won't wipe other servers).
"""
import json, os, sys

server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
python_cmd = sys.executable  # the exact Python you run this with

cfg_dir = os.path.expanduser("~/Library/Application Support/Claude")
cfg_path = os.path.join(cfg_dir, "claude_desktop_config.json")
os.makedirs(cfg_dir, exist_ok=True)

config = {}
if os.path.exists(cfg_path):
    try:
        with open(cfg_path) as f:
            config = json.load(f)
    except Exception:
        config = {}

config.setdefault("mcpServers", {})
config["mcpServers"]["eventops"] = {"command": python_cmd, "args": [server_path]}

with open(cfg_path, "w") as f:
    json.dump(config, f, indent=2)

print("Registered EventOps with Claude Desktop.")
print("  config file :", cfg_path)
print("  python      :", python_cmd)
print("  server      :", server_path)
print("  MCP servers now configured:", ", ".join(config["mcpServers"].keys()))
print("\nNow FULLY QUIT Claude Desktop (Cmd+Q) and reopen it.")
