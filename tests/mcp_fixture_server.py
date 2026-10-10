"""A minimal, correct MCP server used to test core/mcp_manager.py end to end.

Speaks newline-delimited JSON-RPC 2.0 on stdio and implements just enough of
the protocol: initialize, tools/list, tools/call, ping, roots/list.

This is a TEST FIXTURE, not part of the assistant.
"""
import json
import sys
import time

TOOLS = [
    {
        "name": "add",
        "description": "Add two numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "echo",
        "description": "Echo the text back.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "flood_stderr",
        "description": "Writes a lot to stderr. Used to prove the stderr drain works.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue

        method = msg.get("method")
        mid = msg.get("id")

        if method == "initialize":
            send({
                "jsonrpc": "2.0", "id": mid,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "jarvis-test-mcp", "version": "1.0.0"},
                },
            })
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if name == "add":
                out = str(args.get("a", 0) + args.get("b", 0))
            elif name == "echo":
                out = str(args.get("text", ""))
            elif name == "flood_stderr":
                # >64KB to stderr. If the client does not drain this pipe, it
                # blocks forever and every later call times out.
                for _ in range(2000):
                    print("x" * 100, file=sys.stderr)
                sys.stderr.flush()
                out = "flooded"
            else:
                send({"jsonrpc": "2.0", "id": mid,
                      "error": {"code": -32601, "message": f"unknown tool {name}"}})
                continue
            send({"jsonrpc": "2.0", "id": mid,
                  "result": {"content": [{"type": "text", "text": out}]}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "roots/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"roots": []}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid,
                  "error": {"code": -32601, "message": f"unknown method {method}"}})
        # A stray banner on stdout that is NOT valid JSON, to prove the reader
        # loop does not die on a malformed line.
        if method == "tools/list":
            sys.stdout.write("this is not json at all\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()