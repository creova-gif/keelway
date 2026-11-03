"""Keelway Record v1: the portable, independently verifiable form of the audit log.

This file uses only the Python standard library and imports nothing from Keelway, so anyone can copy it and
check a log without installing the product:

    python record_format.py verify record.jsonl

A Record file is JSON Lines. The first line is a header; every later line is one audit entry:

    {"format": "keelway.record/v1", "genesis": "<64 zeros>", "count": 2, "head": "<last entry_hash>"}
    {"seq": 1, "timestamp": "...", "actor": "...", "role": "...", "action": "...", "resource": "...",
     "allowed": true, "prev_hash": "<genesis>", "entry_hash": "<sha256>"}

entry_hash = sha256(prev_hash + canonical_json({actor, role, action, resource, allowed, timestamp})), where
canonical_json uses sorted keys and separators (",", ":"). It must match core.security.auth._chain_hash.

What verification proves: no entry was edited, reordered or removed from the middle. What it cannot prove on its
own: that entries were not cut off the END of the log, or that the whole file was not regenerated. The header's
count and head are self-asserted. Publish the head hash somewhere you control (a git note, a ticket, a signed
message) to detect tail truncation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

FORMAT = "keelway.record/v1"
GENESIS_HASH = "0" * 64
HASHED_FIELDS = ("actor", "role", "action", "resource", "allowed", "timestamp")
REQUIRED_ENTRY_KEYS = HASHED_FIELDS + ("prev_hash", "entry_hash")


def canonical_json(fields: Dict[str, Any]) -> str:
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


def entry_hash(prev_hash: str, fields: Dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(fields)).encode("utf-8")).hexdigest()


def _bad(reason: str, index: int, entry: Optional[Dict[str, Any]], total: int) -> Dict[str, Any]:
    seq = entry.get("seq") if isinstance(entry, dict) else None
    return {"valid": False, "entries": total, "broken_at_index": index, "broken_at_seq": seq, "reason": reason}


def verify_entries(entries: List[Dict[str, Any]], header: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Check a list of entries (and the optional header). Returns a dict with `valid` and, if not, `reason`."""
    total = len(entries)
    prev = GENESIS_HASH
    if header is not None:
        if header.get("format") != FORMAT:
            return _bad("unsupported_format", -1, None, total)
        prev = header.get("genesis", GENESIS_HASH)
        if not isinstance(prev, str) or len(prev) != 64:
            return _bad("bad_genesis", -1, None, total)
        if "count" in header and header["count"] != total:
            return _bad("header_count_mismatch", -1, None, total)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or any(key not in entry for key in REQUIRED_ENTRY_KEYS):
            return _bad("missing_field", index, entry if isinstance(entry, dict) else None, total)
        if not isinstance(entry["allowed"], bool) or not all(isinstance(entry[k], str) for k in HASHED_FIELDS if k != "allowed"):
            return _bad("wrong_type", index, entry, total)
        if entry["prev_hash"] != prev:
            return _bad("prev_hash_mismatch", index, entry, total)
        fields = {key: entry[key] for key in HASHED_FIELDS}
        if entry["entry_hash"] != entry_hash(prev, fields):
            return _bad("entry_hash_mismatch", index, entry, total)
        prev = entry["entry_hash"]
    if header is not None and "head" in header and header["head"] != prev:
        return _bad("header_head_mismatch", total - 1, entries[-1] if entries else None, total)
    return {"valid": True, "entries": total, "head": prev}


def parse_jsonl(lines: Iterable[str]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    header: Optional[Dict[str, Any]] = None
    entries: List[Dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"line {number}: not valid JSON ({exc})") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"line {number}: expected a JSON object")
        if header is None and not entries and "format" in obj and "entry_hash" not in obj:
            header = obj
        else:
            entries.append(obj)
    return header, entries


def read_record_file(path: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as handle:
        return parse_jsonl(handle)


def make_header(entries: List[Dict[str, Any]], genesis: str = GENESIS_HASH) -> Dict[str, Any]:
    return {"format": FORMAT, "genesis": genesis, "count": len(entries), "head": entries[-1]["entry_hash"] if entries else genesis}


def dump_jsonl(entries: List[Dict[str, Any]], genesis: str = GENESIS_HASH) -> str:
    lines = [json.dumps(make_header(entries, genesis), sort_keys=True)]
    lines += [json.dumps(entry, sort_keys=True) for entry in entries]
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "verify":
        print("usage: python record_format.py verify RECORD.jsonl", file=sys.stderr)
        return 2
    try:
        header, entries = read_record_file(args[1])
    except (OSError, ValueError) as exc:
        print(f"cannot read record: {exc}", file=sys.stderr)
        return 2
    result = verify_entries(entries, header)
    if result["valid"]:
        print(f"chain valid: {result['entries']} entries, head {result['head']}")
        if header is None:
            print("note: no header line, so the entry count and head were not cross-checked")
        return 0
    where = f"entry #{result['broken_at_index'] + 1}" if result["broken_at_index"] >= 0 else "the header"
    print(f"chain BROKEN at {where} (seq {result['broken_at_seq']}): {result['reason']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
