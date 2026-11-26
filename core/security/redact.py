"""Remove credentials from data that is saved to disk, such as flight tapes.

An agent can read any file in its workspace, including `.env`, and run commands that print secrets. Whatever it
sees ends up in the tape, and tapes get exported, forked, shared and used to build fine-tuning datasets. So the
recorder redacts before it stores.

This is best effort and pattern based, and it errs towards removing too much (a line like `token = x` in source code
loses its value). It will miss a secret that has no recognisable shape and sits under an innocent name. It is
applied to what is SAVED, not to what a live agent sees or to what Studio shows on this machine.

It reuses `DLPScanner` (the scanner that sanitises model prompts) and adds what that one misses: GitHub and Slack
tokens, any `user:password@host` URL (including an empty user), `.env`/YAML style `NAME=value` lines for
secret-named variables, and private-key blocks that are cut off before their END marker. `DLPScanner` itself is
unchanged on purpose: loosening it would alter what is redacted from model prompts.
"""
from __future__ import annotations

import re
from typing import Any, List, Pattern, Tuple

from core.security.firewall import DLPScanner

_SECRET_WORD = r"(?:secret|token|passwd|password|api[_-]?key|apikey|private[_-]?key|credentials?)"

# (name, pattern). A pattern with a capture group redacts only group 1; otherwise the whole match.
_EXTRA: List[Tuple[str, Pattern[str]]] = [
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("SLACK_TOKEN", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("PRIVATE_KEY_BLOCK", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)")),
    ("URL_PASSWORD", re.compile(r"(?<=://)[^/\s:@]*:([^/\s@\[][^/\s@]*)(?=@)")),
    (
        "ENV_SECRET",
        re.compile(
            r"(?im)^[ \t]*(?:export[ \t]+)?(?:[A-Za-z0-9]+[_.-])*" + _SECRET_WORD + r"(?:[_.-][A-Za-z0-9]+)*[ \t]*[=:][ \t]*(?!\[REDACTED)([^\s#][^\s]*)"
        ),
    ),
]

# Dict keys whose value is a credential no matter what it looks like.
_SECRET_KEY = re.compile(r"(?i)(^|[_.-])" + _SECRET_WORD + r"($|[_.-])|(^|[_.-])(authorization|cookie)($|[_.-])")


def redact_text(text: str) -> Tuple[str, int]:
    """Return (clean text, number of replacements). Re-redacting clean text changes nothing and counts nothing."""
    clean, findings = DLPScanner.redact(text)
    count = 0 if clean == text else sum(int(re.search(r"\((\d+) occurrences\)", f).group(1)) for f in findings)
    for name, pattern in _EXTRA:
        placeholder = f"[REDACTED_{name}]"
        for m in reversed(list(pattern.finditer(clean))):
            start, end = m.span(1) if pattern.groups else m.span()
            if clean[start:end] == placeholder:
                continue
            clean = clean[:start] + placeholder + clean[end:]
            count += 1
    return clean, count


def redact_payload(obj: Any) -> Tuple[Any, int]:
    """Deep-copy `obj` with credentials removed. Returns (clean copy, number of redactions). Never mutates the input."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        out, total = {}, 0
        for key, value in obj.items():
            if isinstance(key, str) and _SECRET_KEY.search(key) and isinstance(value, str) and value and not value.startswith("[REDACTED"):
                out[key], total = "[REDACTED_FIELD]", total + 1
            else:
                out[key], n = redact_payload(value)
                total += n
        return out, total
    if isinstance(obj, (list, tuple)):
        items, total = [], 0
        for value in obj:
            clean, n = redact_payload(value)
            items.append(clean)
            total += n
        return (items if isinstance(obj, list) else tuple(items)), total
    return obj, 0
