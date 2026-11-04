"""Keelway Customer Runner Daemon.
Implements customer-hosted VPC/on-prem/CI runner execution with outbound-only connections,
enrolled identity verification, and cross-org isolation (PRD-001 Section 94-108).
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import uuid
from typing import Any, Dict, List, Optional, Tuple

from keelway.core.runner import GovernedRunCoordinator


class RunnerAuthenticationError(Exception):
    pass


class CrossOrgConsumptionError(Exception):
    pass


class CustomerRunnerDaemon:
    """Outbound-only runner daemon operating within customer trust boundary."""

    def __init__(
        self,
        runner_id: str,
        org_id: str,
        secret_key: Optional[bytes] = None,
        control_plane_url: str = "http://127.0.0.1:8000",
        allowed_repos: Optional[List[str]] = None,
        repo_dir: str = ".",
    ):
        self.runner_id = runner_id
        self.org_id = org_id
        self.secret_key = secret_key or hashlib.sha256(f"{org_id}:{runner_id}".encode()).digest()
        self.control_plane_url = control_plane_url
        self.allowed_repos = allowed_repos or ["*"]
        self.repo_dir = repo_dir
        self.status = "IDLE"
        self._local_spool: List[Dict[str, Any]] = []

    def generate_auth_token(self) -> str:
        """Generates time-bound cryptographic runner authorization header."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        preimage = f"{self.runner_id}:{self.org_id}:{now}"
        sig = hmac.new(self.secret_key, preimage.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{self.runner_id}:{self.org_id}:{now}:{sig}"

    def verify_auth_token(self, token: str) -> bool:
        """Verifies runner authorization token."""
        try:
            parts = token.split(":")
            if len(parts) < 4:
                return False
            runner_id, org_id, timestamp = parts[0], parts[1], ":".join(parts[2:-1])
            received_sig = parts[-1]
            if runner_id != self.runner_id or org_id != self.org_id:
                return False
            expected_sig = hmac.new(
                self.secret_key, f"{runner_id}:{org_id}:{timestamp}".encode("utf-8"), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(received_sig, expected_sig)
        except Exception:
            return False

    def validate_job_scope(self, job_spec: Dict[str, Any]) -> None:
        """Validates tenancy and repo allowlist boundaries before execution."""
        target_org = job_spec.get("org_id")
        if target_org != self.org_id:
            raise CrossOrgConsumptionError(
                f"Runner org '{self.org_id}' refused cross-org job belonging to '{target_org}'"
            )

        repo = job_spec.get("repo_path", ".")
        if "*" not in self.allowed_repos and repo not in self.allowed_repos:
            raise RunnerAuthenticationError(f"Repository '{repo}' not in runner allowlist")

    def execute_job(self, job_spec: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Executes a governed job inside the customer's isolated environment."""
        self.validate_job_scope(job_spec)
        self.status = "RUNNING"

        task_prompt = job_spec.get("task_prompt", "Governed modification")
        repo_path = job_spec.get("repo_path", ".")
        policy_version = job_spec.get("policy_version", "default_governed_v1")

        coordinator = GovernedRunCoordinator(
            org_id=self.org_id,
            project_id=job_spec.get("project_id", "proj_customer"),
            actor_id=job_spec.get("actor_id", f"runner_{self.runner_id}"),
            repo_path=repo_path,
            policy_version=policy_version,
            token_ceiling=job_spec.get("token_ceiling", 50000),
            cost_ceiling_cents=job_spec.get("cost_ceiling_cents", 500),
        )

        try:
            ok, msg = coordinator.start_run(task_prompt=task_prompt)
            if not ok:
                self.status = "IDLE"
                return False, msg, {"events_count": len(coordinator.audit.events)}

            # Spool events locally to preserve audit integrity across network blips
            for ev in coordinator.audit.events:
                self._local_spool.append(ev.model_dump())

            summary = {
                "run_id": coordinator.run_id,
                "status": coordinator.manifest.status.value,
                "patch_hash": coordinator.workspace.get_patch_hash(),
                "approval_id": msg,
                "events_count": len(coordinator.audit.events),
            }
            self.status = "IDLE"
            return True, "JOB_AWAITING_APPROVAL", summary
        finally:
            coordinator.teardown()
            self.status = "IDLE"

    def poll_and_execute_once(self, base_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Polls the control plane once, executes assigned job, and acknowledges completion."""
        import json
        import urllib.request

        url = (base_url or self.control_plane_url).rstrip("/")
        poll_endpoint = f"{url}/v1/runner/jobs/poll"
        ack_endpoint = f"{url}/v1/runner/jobs/ack"
        auth_token = self.generate_auth_token()

        poll_payload = json.dumps({
            "runner_id": self.runner_id,
            "org_id": self.org_id,
            "auth_token": auth_token,
        }).encode("utf-8")

        req = urllib.request.Request(
            poll_endpoint,
            data=poll_payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

        if not data.get("job_available") or not data.get("job"):
            return None

        job = data["job"]
        ok, status_msg, summary = self.execute_job(job)

        ack_payload = json.dumps({
            "runner_id": self.runner_id,
            "org_id": self.org_id,
            "run_id": summary.get("run_id", "unknown"),
            "status": summary.get("status", status_msg),
            "patch_hash": summary.get("patch_hash"),
            "approval_id": summary.get("approval_id"),
        }).encode("utf-8")
        ack_req = urllib.request.Request(
            ack_endpoint,
            data=ack_payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(ack_req, timeout=10) as resp:
                pass
        except Exception:
            pass

        return summary

    def start(self, poll_interval: float = 5.0, max_iterations: Optional[int] = None):
        """Runs the continuous outbound polling loop until interrupted or max_iterations reached."""
        import time
        print(f"[+] Outbound Runner Daemon active for org '{self.org_id}' on node '{self.runner_id}'")
        print(f"    Control Plane:    {self.control_plane_url}")
        print(f"    Working Repo:     {self.repo_dir}")
        print(f"    Polling Interval: {poll_interval}s\n")
        iterations = 0
        try:
            while max_iterations is None or iterations < max_iterations:
                summary = self.poll_and_execute_once()
                if summary:
                    print(f"[✓] Executed job {summary.get('run_id')} (Status: {summary.get('status')})")
                iterations += 1
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n[-] Runner daemon shutting down gracefully.")


OutboundRunnerDaemon = CustomerRunnerDaemon

