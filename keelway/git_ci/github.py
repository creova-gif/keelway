"""Keelway GitHub App and Webhook Integration.
Implements secure webhook signature verification, event normalization,
and staging status reconciliation into the Keelway audit chain.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Dict, Optional, Tuple

from keelway.security.source_defaults import is_source_default


class WebhookVerificationError(Exception):
    pass


class GitHubAppWebhookHandler:
    """Handles and cryptographically verifies GitHub App webhook events."""

    def __init__(self, webhook_secret: str = "keelway_github_webhook_secret_v1"):
        self.webhook_secret = webhook_secret.encode("utf-8")

    def verify_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Verifies X-Hub-Signature-256 HMAC digest."""
        if is_source_default(self.webhook_secret) or not signature_header or not signature_header.startswith("sha256="):
            return False

        received_sig = signature_header[7:]
        expected_sig = hmac.new(self.webhook_secret, payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(received_sig, expected_sig)

    def process_event(
        self, event_type: str, payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Processes normalized GitHub webhook events.
        
        Returns:
            (success, audit_event_kind, normalized_event_data)
        """
        if is_source_default(self.webhook_secret):
            return False, None, {"reason": "source-default webhook secret is refused"}
        if event_type == "pull_request":
            action = payload.get("action", "")
            pr_data = payload.get("pull_request", {})
            pr_number = pr_data.get("number")
            head_sha = pr_data.get("head", {}).get("sha")
            merged = pr_data.get("merged", False)

            if action == "closed":
                kind = "PR_MERGED" if merged else "PR_CLOSED_UNMERGED"
                return True, kind, {
                    "pr_number": pr_number,
                    "head_sha": head_sha,
                    "merged": merged,
                    "merged_at": pr_data.get("merged_at"),
                }
            return True, f"PR_{action.upper()}", {"pr_number": pr_number, "head_sha": head_sha}

        elif event_type == "check_run":
            check_run = payload.get("check_run", {})
            status = check_run.get("status")
            conclusion = check_run.get("conclusion")
            head_sha = check_run.get("head_sha")
            check_name = check_run.get("name")

            return True, "CI_STATUS_RECONCILED", {
                "check_name": check_name,
                "status": status,
                "conclusion": conclusion,
                "head_sha": head_sha,
                "passed": conclusion == "success",
            }

        return False, None, {"reason": f"Unhandled event type: {event_type}"}


def handler_from_environment() -> "GitHubAppWebhookHandler":
    """Use an operator secret when one is configured. A source default stays refused."""
    raw = os.environ.get("KEELWAY_GITHUB_WEBHOOK_SECRET", "")
    if raw and not is_source_default(raw):
        return GitHubAppWebhookHandler(webhook_secret=raw)
    return GitHubAppWebhookHandler()
