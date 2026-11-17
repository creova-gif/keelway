#!/usr/bin/env python3
"""Fixture ACP agent: NDJSON JSON-RPC 2.0 over stdio.

Handles: initialize, session/new, session/prompt.
On session/prompt it emits session/update notifications, sends
session/request_permission (id=999), reads the client's answer, then
returns stopReason "end_turn" (allowed) or "refusal" (rejected/cancelled).
"""

import json
import sys


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def notify(method, params):
    send({"jsonrpc": "2.0", "method": method, "params": params})


def respond(rid, result):
    send({"jsonrpc": "2.0", "id": rid, "result": result})


def main():
    session_id = "fixture-session-1"
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "method" not in msg:
            continue  # a response to our request_permission — handled inline below
        method = msg["method"]
        rid = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            respond(rid, {"protocolVersion": 1,
                          "agentCapabilities": {"loadSession": False},
                          "agentInfo": {"name": "fake-acp", "version": "0.0.1"}})
        elif method == "session/new":
            respond(rid, {"sessionId": session_id})
        elif method == "session/prompt":
            sid = params.get("sessionId", session_id)
            notify("session/update", {"sessionId": sid, "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "working on it"}}})
            notify("session/update", {"sessionId": sid, "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "tc-1", "title": "bash: rm -rf /tmp/x",
                "kind": "execute", "status": "pending",
                "rawInput": {"command": "rm -rf /tmp/x"}}})
            # Ask client permission; block until response arrives on stdin.
            send({"jsonrpc": "2.0", "id": 999, "method": "session/request_permission",
                  "params": {"sessionId": sid,
                             "toolCall": {"toolCallId": "tc-1",
                                          "title": "bash: rm -rf /tmp/x",
                                          "kind": "execute",
                                          "rawInput": {"command": "rm -rf /tmp/x"}},
                             "options": [
                                 {"optionId": "allow-once", "name": "Allow once", "kind": "allow_once"},
                                 {"optionId": "allow-always", "name": "Always", "kind": "allow_always"},
                                 {"optionId": "reject-once", "name": "Reject", "kind": "reject_once"},
                             ]}})
            decision = None
            for line2 in sys.stdin:
                line2 = line2.strip()
                if not line2:
                    continue
                try:
                    resp = json.loads(line2)
                except json.JSONDecodeError:
                    continue
                if resp.get("id") == 999:
                    decision = resp.get("result", {}).get("outcome", {})
                    break
            allowed = (decision or {}).get("outcome") == "selected" and \
                      (decision or {}).get("optionId", "").startswith("allow")
            notify("session/update", {"sessionId": sid, "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "done" if allowed else "refused"}}})
            respond(rid, {"stopReason": "end_turn" if allowed else "refusal"})
        else:
            if rid is not None:
                respond(rid, {})


if __name__ == "__main__":
    main()
