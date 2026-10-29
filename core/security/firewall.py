"""
Kora AI Security Firewall & Guardrails.
Defends against:
1. Data Loss / Secret Leakage (DLP Scanner)
2. Direct and Indirect Prompt Injection
3. Dangerous Shell Commands & Unauthorized File System Traversals
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional


@dataclass
class SecurityCheckResult:
    is_safe: bool
    risk_score: float = 0.0  # 0.0 to 1.0
    sanitized_text: str = ""
    findings: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None


class DLPScanner:
    """Detects and redacts sensitive credentials, private keys, and connection strings."""

    SECRET_PATTERNS = [
        ("ANTHROPIC_KEY", re.compile(r"sk-ant-[a-zA-Z0-9_\-]{20,}")),
        ("OPENAI_KEY", re.compile(r"sk-(?:proj-)?[a-zA-Z0-9_\-]{30,}")),
        ("GOOGLE_KEY", re.compile(r"AIza[0-9A-Za-z-_]{35}|AQ\.[0-9A-Za-z-_]{20,}")),
        ("AWS_KEY_ID", re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}")),
        ("GENERIC_BEARER", re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{25,})")),
        ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("DB_PASSWORD", re.compile(r"(?:postgres|postgresql|mysql|mongodb)://[^:\s]+:([^@\s]+)@")),
        ("GENERIC_SECRET_ASSIGNMENT", re.compile(r'(?:api_key|secret|password|token)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']', re.IGNORECASE)),
    ]

    @classmethod
    def redact(cls, text: str) -> Tuple[str, List[str]]:
        """Replaces detected credentials with safe redacted placeholders."""
        sanitized = text
        findings = []

        for name, pattern in cls.SECRET_PATTERNS:
            matches = list(pattern.finditer(sanitized))
            if matches:
                findings.append(f"Detected {name} ({len(matches)} occurrences)")
                for m in reversed(matches):
                    # If regex has capture group (e.g. db password or bearer token), redact group 1
                    if pattern.groups > 0 and m.lastindex:
                        start, end = m.span(1)
                        sanitized = sanitized[:start] + f"[REDACTED_{name}]" + sanitized[end:]
                    else:
                        start, end = m.span()
                        sanitized = sanitized[:start] + f"[REDACTED_{name}]" + sanitized[end:]

        return sanitized, findings


class PromptInjectionDetector:
    """Detects potential direct and indirect prompt injection attempts."""

    INJECTION_PATTERNS = [
        (re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE), 0.9, "Instruction override directive"),
        (re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+rules?", re.IGNORECASE), 0.9, "Rule override directive"),
        (re.compile(r"you\s+are\s+now\s+(?:in\s+developer\s+mode|dan|unfiltered|jailbroken)", re.IGNORECASE), 0.95, "Jailbreak persona adoption"),
        (re.compile(r"reveal\s+(?:your\s+)?(?:system\s+prompt|internal\s+instructions|master\s+prompt)", re.IGNORECASE), 0.85, "System prompt extraction probe"),
        (re.compile(r"(?:print|output|display|show)\s+(?:all\s+)?(?:api\s+keys?|passwords?|secrets?|environment\s+variables?)", re.IGNORECASE), 0.95, "Credential exfiltration request"),
        (re.compile(r"<\s*script[\s\S]*?>[\s\S]*?<\s*/\s*script\s*>", re.IGNORECASE), 0.75, "HTML/script injection tag"),
        (re.compile(r"base64\s+(?:decode|payload)\s*:", re.IGNORECASE), 0.7, "Obfuscated payload indicator"),
        (re.compile(r"\[SYSTEM(?:\s+OVERRIDE)?\]", re.IGNORECASE), 0.85, "Fake system delimiter spoofing"),
    ]

    @classmethod
    def analyze(cls, text: str) -> Tuple[bool, Optional[str], float]:
        """
        Analyzes text for injection vectors.
        Returns: (is_suspicious, reason, max_risk_score)
        """
        max_score = 0.0
        reasons = []

        # Check for zero-width unicode characters (often used for stealth evasion)
        zero_width_chars = len(re.findall(r"[\u200B-\u200D\uFEFF]", text))
        if zero_width_chars > 3:
            max_score = max(max_score, 0.7)
            reasons.append(f"High density of zero-width evasion characters ({zero_width_chars})")

        for pattern, score, label in cls.INJECTION_PATTERNS:
            if pattern.search(text):
                max_score = max(max_score, score)
                reasons.append(label)

        is_suspicious = max_score >= 0.75
        combined_reason = "; ".join(reasons) if reasons else None
        return is_suspicious, combined_reason, max_score


class ToolPolicyGuard:
    """Enforces least-privilege boundaries on agent shell commands and filesystem access."""

    DANGEROUS_COMMANDS = [
        re.compile(r"\brm\s+-[rR]f\s+/(?:\s|$|\*)"),  # rm -rf /
        re.compile(r"\brm\s+-[rR]f\s+~(?:\s|$)"),     # rm -rf ~
        re.compile(r"\bmkfs\b"),
        re.compile(r"\bdd\s+if=/dev"),
        re.compile(r":\(\)\s*{\s*:\s*\|\s*:\s*&\s*}\s*;\s*:"),  # fork bomb
        re.compile(r">\s*/dev/sd[a-z]"),
        re.compile(r"\bshutdown\s+-[rh]\b"),
        re.compile(r"\bchmod\s+-[rR]\s+777\s+/"),
    ]

    SENSITIVE_PATHS = [
        "/etc/shadow",
        "/etc/passwd",
        "/etc/sudoers",
        "~/.ssh",
        "~/.aws/credentials",
        "~/.gnupg",
    ]

    @classmethod
    def validate_command(cls, command: str) -> Tuple[bool, Optional[str]]:
        """Verifies that a shell command does not violate safety boundaries."""
        for pattern in cls.DANGEROUS_COMMANDS:
            if pattern.search(command):
                return False, f"Prohibited destructive command pattern detected: {pattern.pattern}"

        # Check for access to sensitive paths in command
        for s_path in cls.SENSITIVE_PATHS:
            expanded = str(Path(s_path).expanduser())
            if s_path in command or expanded in command:
                return False, f"Unauthorized access to sensitive system path: {s_path}"

        return True, None

    @classmethod
    def validate_path(cls, path_str: str, allowed_root: Optional[Path] = None) -> Tuple[bool, Optional[str]]:
        """Ensures path stays strictly within allowed sandbox root without directory traversal."""
        try:
            target = Path(path_str).resolve()
            if allowed_root:
                root_res = allowed_root.resolve()
                if not target.is_relative_to(root_res):
                    return False, f"Path traversal outside sandbox root: {target} is not in {root_res}"
            return True, None
        except Exception as e:
            return False, f"Invalid path syntax: {e}"


class SecurityGateway:
    """Unified entrypoint for validating and sanitizing text before execution or LLM routing."""

    def __init__(self, block_on_injection: bool = True, redact_secrets: bool = True):
        self.block_on_injection = block_on_injection
        self.redact_secrets = redact_secrets

    def inspect_and_sanitize(self, content: str) -> SecurityCheckResult:
        """
        Runs DLP scanning and prompt injection detection.
        Returns a SecurityCheckResult with sanitized text and status.
        """
        sanitized_text = content
        findings = []

        # 1. DLP Redaction
        if self.redact_secrets:
            sanitized_text, dlp_findings = DLPScanner.redact(content)
            findings.extend(dlp_findings)

        # 2. Prompt Injection Analysis
        is_suspicious, reason, risk_score = PromptInjectionDetector.analyze(content)
        if reason:
            findings.append(f"Prompt Security Alert: {reason} (Score: {risk_score:.2f})")

        is_safe = not (is_suspicious and self.block_on_injection)
        blocked_reason = reason if (is_suspicious and self.block_on_injection) else None

        return SecurityCheckResult(
            is_safe=is_safe,
            risk_score=risk_score,
            sanitized_text=sanitized_text,
            findings=findings,
            blocked_reason=blocked_reason,
        )
