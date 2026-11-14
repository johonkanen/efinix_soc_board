#!/usr/bin/env python3
"""Drive the KiCad MCP server (github.com/mixelpixx/KiCAD-MCP-Server) from the shell.

    python3 tools/kicad_mcp.py --list [WORD]             tool names (containing WORD)
    python3 tools/kicad_mcp.py --schema TOOL [TOOL ...]   input schema of tools
    python3 tools/kicad_mcp.py CALLS.json [--full]        run a list of calls in ONE server session

CALLS.json is a list of {"tool": NAME, "args": {...}}. The server keeps the board in memory only for
the life of one run, so a run that edits must start with open_project and end with save_project:

    [{"tool": "open_project", "args": {"filename": "/abs/path/kicad/ti135_card.kicad_pro"}},
     {"tool": "move_component", "args": {"reference": "R623", "position": {"x": 171, "y": 90, "unit": "mm"}, "rotation": 90}},
     {"tool": "save_project", "args": {}}]

Each result is printed on one line, cut to 600 characters unless --full. A failed call stops the run
(nothing after it is executed, so a later save_project is skipped) and the exit status is 1.

The server is expected in ~/dev/KiCAD-MCP-Server (branch stable, `npm install && npm run build`), with
kicad10_python.sh there pointing it at the KiCad 10 AppImage python. Override with KICAD_MCP_HOME.
"""
import json
import os
import subprocess
import sys

HOME = os.environ.get("KICAD_MCP_HOME", os.path.expanduser("~/dev/KiCAD-MCP-Server"))
env = dict(os.environ, KICAD_PYTHON=os.path.join(HOME, "kicad10_python.sh"), KICAD_AUTO_LAUNCH="false",
           NODE_ENV="production", LOG_LEVEL="error")
p = subprocess.Popen(["node", os.path.join(HOME, "dist", "index.js")], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, text=True)
_id = 0


def rpc(method, params=None, note=False):
    global _id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not note:
        _id += 1
        msg["id"] = _id
    p.stdin.write(json.dumps(msg) + "\n")
    p.stdin.flush()
    while not note:
        line = p.stdout.readline()
        if not line:
            sys.exit("kicad_mcp: the server closed the connection")
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("id") == _id:
            return o


rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "kicad_mcp.py", "version": "1"}})
rpc("notifications/initialized", note=True)
a = sys.argv[1:]
rc = 0
try:
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] in ("--list", "--schema"):
        tools = rpc("tools/list", {})["result"]["tools"]
        if a[0] == "--list":
            print("\n".join(f"{t['name']:36s} {(t.get('description') or '').splitlines()[0][:110]}"
                            for t in tools if len(a) < 2 or a[1] in t["name"]))
        else:
            for t in tools:
                if t["name"] in a[1:]:
                    print(t["name"], "-", t.get("description", ""))
                    print(json.dumps(t["inputSchema"].get("properties", {}), indent=1))
                    print("required:", t["inputSchema"].get("required", []))
    else:
        full = "--full" in a
        for c in json.load(open(a[0])):
            r = rpc("tools/call", {"name": c["tool"], "arguments": c.get("args", {})})
            res = r.get("result", {})
            text = " ".join(x.get("text", "") for x in res.get("content", []) if x.get("type") == "text") or json.dumps(r)
            text = " ".join(text.split())
            bad = "error" in r or res.get("isError") or '"success": false' in text or '"success":false' in text
            print(("FAIL " if bad else "ok   ") + c["tool"] + ": " + (text if full else text[:600]))
            if bad:
                rc = 1
                break
finally:
    p.terminate()
sys.exit(rc)
