# Keelway Record v1 (`keelway.record/v1`)

The Record is the audit log in a portable form that anyone can verify, with or without Keelway.

Implementation: `core/security/record_format.py` (standard library only, copy it anywhere) and
`core/security/record_export.py`. CLI: `keelway record export [--out FILE]` and `keelway record verify FILE`.
Standalone: `python record_format.py verify FILE`.

## Format

JSON Lines, UTF-8. Line 1 is the header; every other line is one entry.

```json
{"format": "keelway.record/v1", "genesis": "0000...0000", "count": 2, "head": "<last entry_hash>"}
{"seq": 1, "timestamp": "2026-11-01T18:43:07+00:00", "actor": "justin", "role": "owner", "action": "execute_agent", "resource": "POST /v1/agent/run", "allowed": true, "prev_hash": "0000...0000", "entry_hash": "..."}
```

`entry_hash = sha256_hex(prev_hash + canonical_json({actor, role, action, resource, allowed, timestamp}))`

`canonical_json` is `json.dumps(fields, sort_keys=True, separators=(",", ":"))`. `genesis` is 64 zeros for a
full log. A partial export may set `genesis` to the `prev_hash` of its first entry. `seq` is informational and
may have gaps (it is not hashed).

## What verification proves

- No entry was edited, reordered, or removed from the middle (any change breaks the next `prev_hash`).
- With a header, the entry count and final hash match what the header claims.

## What it does not prove

- **Tail truncation or full regeneration.** Someone with database access can delete the newest entries, or
  rebuild the whole chain with a new header. The header is self-asserted. To detect this, publish the `head`
  hash somewhere you control (a git note, a ticket, a signed message, a transparency log) and compare later.
  Anchoring is not built yet.
- That the recorded actions were authorised, only that the record of them is intact.
- Who wrote an entry. Entries are not individually signed.

## Why open

If other agents (Claude Code hooks, Cursor, Codex through MCP or ACP) write entries in this format, Keelway can be
the system of record for agent actions whichever agent is used. The format is intentionally tiny so that is easy.

## Results

`verify` exits 0 when valid, 1 when broken (with the reason: `entry_hash_mismatch`, `prev_hash_mismatch`,
`missing_field`, `wrong_type`, `header_count_mismatch`, `header_head_mismatch`, `unsupported_format`), and 2 when
the file cannot be read.

## Next steps (not built)

1. `GET /v1/audit/export` route (the CLI export exists; a route lets Studio's Record screen offer "Export").
2. Head anchoring (git note or external timestamp) and signed heads.
3. An `append` API and a documented event schema for tool calls and approvals, so third-party agents can write.
4. Per-entry signatures, so entries are attributable.
