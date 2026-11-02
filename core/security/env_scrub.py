"""Keep secrets out of the environment of commands that an agent (or code an agent wrote) will run.

Why: a command run on an agent's behalf can be steered by whatever the agent has read (a web page, an issue, a
file). If the command inherits the parent's environment, `env` or any program it starts hands over API keys,
tokens and database passwords. This module removes the secret-looking variables and keeps everything a program
needs to work (PATH, HOME, locale, virtualenv, PYTHONPATH, non-secret settings).

This is a filter on NAMES and a few well-known VALUE shapes. It is not a guarantee: a secret stored under an
innocent name in an innocent-looking value will pass. For real confinement use `core.agents.sandbox`.

To let a specific variable through on purpose (a test suite that needs a token), the person who starts Keelway
sets `KEELWAY_COMMAND_ENV_PASSTHROUGH=NAME1,NAME2` in the process environment. An agent cannot do that: it can
only change the environment of its own children.
"""
from __future__ import annotations

import re
from typing import Dict, List, Mapping, Tuple

PASSTHROUGH_VAR = "KEELWAY_COMMAND_ENV_PASSTHROUGH"

# Name contains one of these words delimited by "_" or the ends: OPENAI_API_KEY, GITHUB_TOKEN, SSH_AUTH_SOCK, DB_PASSWORD.
# Word boundaries keep AUTHOR and TOKENIZERS_PARALLELISM.
_SECRET_NAME = re.compile(
    r"(^|_)(API_?KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|PASSPHRASE|CREDENTIALS?|PRIVATE_?KEY|ACCESS_?KEY|AUTH|AUTHTOKEN|COOKIE)(_|$)",
    re.IGNORECASE,
)
# Whole families that belong to Keelway or to model/cloud providers, whatever the suffix.
_SECRET_PREFIXES = ("KEELWAY_", "ANTHROPIC_", "OPENAI_", "NVIDIA_", "GEMINI_", "AWS_", "AZURE_", "OIDC_")
_SECRET_NAMES = frozenset({"GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"})
# Values that are credentials no matter what the variable is called.
_SECRET_VALUE = re.compile(
    r"(://[^/\s:@]*:[^/\s@]+@)"            # user:password@host in any URL (DATABASE_URL, REDIS_URL, ...)
    r"|\bsk-[A-Za-z0-9_-]{20,}"            # OpenAI / Anthropic style keys
    r"|\bgh[pousr]_[A-Za-z0-9]{30,}"       # GitHub tokens
    r"|\bAKIA[0-9A-Z]{16}\b"               # AWS access key ids
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"     # Slack tokens
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


def _passthrough(parent: Mapping[str, str]) -> frozenset:
    raw = parent.get(PASSTHROUGH_VAR, "")
    return frozenset(n.strip() for n in raw.split(",") if n.strip())


def is_secret(name: str, value: str) -> bool:
    upper = name.upper()
    return (
        upper in _SECRET_NAMES
        or upper.startswith(_SECRET_PREFIXES)
        or bool(_SECRET_NAME.search(name))
        or bool(_SECRET_VALUE.search(value or ""))
    )


def scrub_env(parent: Mapping[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """Return (clean environment, sorted names that were removed). Values are never returned for removed names."""
    allowed = _passthrough(parent)
    clean: Dict[str, str] = {}
    dropped: List[str] = []
    for name, value in parent.items():
        if name == PASSTHROUGH_VAR:
            dropped.append(name)  # the setting itself is not for children
        elif name in allowed or not is_secret(name, value):
            clean[name] = value
        else:
            dropped.append(name)
    return clean, sorted(dropped)
