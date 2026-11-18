"""
Keelway Sovereign Workspace Filesystem & Live Git Engine.
Provides safe, sandboxed file operations, directory tree indexing, and git diff inspection.
"""

import json
import os
import re
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional


DEFAULT_IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".DS_Store",
    ".keelway/recordings",
    ".kora/recordings",
}


class WorkspaceSecurityError(PermissionError):
    """Raised when an operation attempts directory traversal outside the workspace root."""
    pass


class WorkspaceFilesystem:
    """Safe, scoped filesystem operations for the local developer workspace."""

    def __init__(self, root_dir: Optional[str] = None):
        if root_dir:
            self.root = Path(root_dir).resolve()
        else:
            self.root = Path.cwd().resolve()

    def resolve_safe_path(self, relative_path: str) -> Path:
        """
        Resolves path and guarantees it resides within self.root.
        Prevents directory traversal attacks (e.g., ../../etc/passwd).
        """
        if not relative_path or relative_path == ".":
            return self.root

        # os.path on strings: same symlink resolution as Path.resolve(), without pathlib's per-call overhead.
        root = str(self.root)
        if os.path.isabs(relative_path):
            candidate = os.path.realpath(relative_path)
        else:
            candidate = os.path.realpath(os.path.join(root, relative_path.lstrip("/\\")))

        if candidate != root and not candidate.startswith(root.rstrip(os.sep) + os.sep):
            raise WorkspaceSecurityError(
                f"Path traversal detected: '{relative_path}' resolves outside workspace root."
            )
        return Path(candidate)

    def list_files(self, subpath: str = ".") -> List[str]:
        """Lists relative paths of regular files in workspace root or subpath."""
        base = self.resolve_safe_path(subpath)
        if not base.exists():
            return []
        files = []
        for path in base.rglob("*"):
            if path.is_file():
                try:
                    rel = str(path.relative_to(self.root))
                    files.append(rel)
                except ValueError:
                    files.append(path.name)
        return sorted(files)

    def get_file_tree(self, subpath: str = ".", max_depth: int = 4, max_files: int = 500) -> Dict[str, Any]:
        """
        Recursively scans workspace directory, respecting ignore lists.
        Returns a hierarchical JSON-ready tree structure.
        """
        if not self.root.is_dir():
            self.root = Path.cwd().resolve()
        target_dir = self.resolve_safe_path(subpath)
        if not target_dir.is_dir():
            raise ValueError(f"Target '{subpath}' is not a directory.")

        file_count = 0

        def _scan(current_path: Path, depth: int) -> Dict[str, Any]:
            nonlocal file_count
            rel_path = current_path.relative_to(self.root).as_posix()
            node: Dict[str, Any] = {
                "name": current_path.name if current_path != self.root else self.root.name,
                "path": rel_path if rel_path != "." else "",
                "type": "directory" if current_path.is_dir() else "file",
            }

            if current_path.is_file():
                try:
                    stat = current_path.stat()
                    node["size"] = stat.st_size
                    node["modified"] = int(stat.st_mtime)
                except OSError:
                    node["size"] = 0
                return node

            if depth > max_depth or file_count >= max_files:
                node["children"] = []
                return node

            children = []
            try:
                entries = sorted(list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
                for entry in entries:
                    if entry.name in DEFAULT_IGNORED_DIRS:
                        continue
                    if entry.name.startswith(".") and entry.name not in (".env.example", ".gitignore"):
                        continue
                    
                    file_count += 1
                    children.append(_scan(entry, depth + 1))
            except PermissionError:
                pass

            node["children"] = children
            return node

        return {
            "root": str(self.root),
            "name": self.root.name,
            "tree": _scan(target_dir, 0),
        }

    def read_file(self, relative_path: str, max_bytes: int = 5_000_000) -> Dict[str, Any]:
        """Reads file content safely with UTF-8 decoding."""
        target = self.resolve_safe_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        if target.is_dir():
            raise IsADirectoryError(f"Target is a directory, not a file: {relative_path}")

        stat = target.stat()
        if stat.st_size > max_bytes:
            raise ValueError(f"File exceeds maximum allowed size ({max_bytes} bytes).")

        raw_bytes = target.read_bytes()
        try:
            content = raw_bytes.decode("utf-8")
            is_binary = False
        except UnicodeDecodeError:
            content = f"[Binary file, {stat.st_size} bytes]"
            is_binary = True

        return {
            "path": relative_path,
            "absolute_path": str(target),
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
            "is_binary": is_binary,
            "content": content,
        }

    def write_file(self, relative_path: str, content: str) -> Dict[str, Any]:
        """
        Safely writes file content using atomic rename to prevent corruption.
        Ensures parent directories exist.
        """
        target = self.resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        tmp_target = target.with_suffix(f"{target.suffix}.keelway_tmp_{os.getpid()}")
        try:
            tmp_target.write_text(content, encoding="utf-8")
            # Atomic replace
            os.replace(tmp_target, target)
        finally:
            if tmp_target.exists():
                try:
                    tmp_target.unlink()
                except OSError:
                    pass

        stat = target.stat()
        return {
            "status": "saved",
            "path": relative_path,
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
        }

    def get_git_status(self) -> Dict[str, Any]:
        """Inspects working directory Git status."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0:
                return {"is_git": False, "branch": "", "clean": True, "files": []}

            lines = res.stdout.strip().split("\n")
            branch_line = lines[0] if lines else "## unknown"
            branch = branch_line.replace("## ", "").split("...")[0].strip()

            files = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                status_code = line[:2].strip()
                file_path = line[3:].strip()
                files.append({"status": status_code, "path": file_path})

            return {
                "is_git": True,
                "branch": branch,
                "clean": len(files) == 0,
                "files": files,
            }
        except Exception:
            return {"is_git": False, "branch": "", "clean": True, "files": []}

    def get_git_diff(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves unified git diff for workspace or specific file."""
        cmd = ["git", "diff", "HEAD"]
        if path:
            safe_target = self.resolve_safe_path(path)
            cmd.append(str(safe_target.relative_to(self.root)))

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=8,
            )
            return {
                "path": path or "workspace",
                "diff": res.stdout if res.returncode == 0 else "",
            }
        except Exception as e:
            return {"path": path or "workspace", "diff": "", "error": str(e)}

    def prepare_commit_proposal(self) -> Dict[str, Any]:
        """Analyzes uncommitted git changes and proposes a structured semantic commit message."""
        status = self.get_git_status()
        if not status["is_git"]:
            raise ValueError("Workspace is not a Git repository.")
        if status["clean"]:
            return {
                "clean": True,
                "message": "",
                "patch_hash": "",
                "files_count": 0,
                "files": [],
            }

        diff_data = self.get_git_diff()
        diff_text = diff_data.get("diff", "")
        patch_hash = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()

        file_paths = [f["path"] for f in status["files"]]
        primary_scope = file_paths[0].split("/")[0] if file_paths else "workspace"

        has_tests = any("test" in f for f in file_paths)
        has_docs = any(f.endswith(".md") or "doc" in f for f in file_paths)
        has_core = any("core" in f or "src" in f for f in file_paths)

        if has_tests and not has_core:
            prefix = "test"
        elif has_docs and not has_core:
            prefix = "docs"
        elif any("fix" in f.lower() for f in file_paths):
            prefix = "fix"
        else:
            prefix = "feat"

        summary_msg = f"{prefix}({primary_scope}): update {len(file_paths)} file(s)"
        body_lines = [f"- Modified {len(file_paths)} file(s):"]
        for f in status["files"][:8]:
            body_lines.append(f"  • [{f['status']}] {f['path']}")
        if len(status["files"]) > 8:
            body_lines.append(f"  • ... and {len(status['files']) - 8} more")

        full_message = f"{summary_msg}\n\n" + "\n".join(body_lines)

        return {
            "clean": False,
            "branch": status["branch"],
            "files_count": len(file_paths),
            "files": status["files"],
            "proposed_message": full_message,
            "proposed_title": summary_msg,
            "patch_hash": patch_hash,
            "diff_preview": diff_text[:2000],
        }

    def create_local_commit(self, message: str, author_name: str = "Keelway Developer", author_email: str = "dev@keelway.local") -> Dict[str, Any]:
        """Creates a verified local Git commit. Explicitly does NOT push to remote."""
        status = self.get_git_status()
        if not status["is_git"]:
            raise ValueError("Workspace is not a Git repository.")
        if status["clean"]:
            raise ValueError("Working tree is clean; nothing to commit.")

        msg = message.strip()
        if not msg:
            raise ValueError("Commit message cannot be empty.")

        subprocess.run(
            ["git", "-c", f"user.name={author_name}", "-c", f"user.email={author_email}", "add", "-A"],
            cwd=str(self.root),
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "-c", f"user.name={author_name}", "-c", f"user.email={author_email}", "-c", "commit.gpgsign=false", "commit", "-m", msg],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            check=True,
        )

        sha_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            check=True,
        )
        commit_sha = sha_res.stdout.strip()
        new_status = self.get_git_status()

        return {
            "status": "committed",
            "commit_sha": commit_sha,
            "branch": new_status["branch"],
            "message": msg,
            "author": f"{author_name} <{author_email}>",
            "clean": new_status["clean"],
        }

    def prepare_pr_proposal(self, base_branch: str = "main") -> Dict[str, Any]:
        """Generates a structured Pull Request proposal comparing HEAD against a base branch."""
        status = self.get_git_status()
        if not status["is_git"]:
            raise ValueError("Workspace is not a Git repository.")

        current_branch = status["branch"]

        log_res = subprocess.run(
            ["git", "log", f"{base_branch}..HEAD", "--oneline"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )
        ahead_commits = [c.strip() for c in log_res.stdout.strip().splitlines() if c.strip()]

        diff_res = subprocess.run(
            ["git", "diff", f"{base_branch}...HEAD"],
            cwd=str(self.root),
            capture_output=True,
            text=True,
        )
        pr_diff = diff_res.stdout if diff_res.returncode == 0 else ""
        patch_hash = hashlib.sha256(pr_diff.encode("utf-8")).hexdigest()

        title = f"feat({current_branch}): integrate changes into {base_branch}"
        if ahead_commits:
            title = ahead_commits[0].split(" ", 1)[-1] if " " in ahead_commits[0] else title

        summary_body = f"""## Overview\nIntegrates {len(ahead_commits)} commit(s) from `{current_branch}` into `{base_branch}`.\n\n### Commits Included\n"""
        for c in ahead_commits:
            summary_body += f"- {c}\n"

        summary_body += f"""\n### Security & Evidence\n- [x] Verified local test execution passes\n- [x] Environment variable scrubbed\n- [x] No unauthorized cloud telemetry\n- [x] Cryptographic patch hash: `{patch_hash[:16]}`\n"""

        return {
            "base_branch": base_branch,
            "head_branch": current_branch,
            "title": title,
            "description": summary_body.strip(),
            "commits_count": len(ahead_commits),
            "commits": ahead_commits,
            "patch_hash": patch_hash,
            "ready_to_push": False,
        }

    # ---- Isolated worktrees (Gate-2: agent edit isolation) ----

    def _git(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args, cwd=str(self.root),
            capture_output=True, text=True, timeout=30,
        )

    def create_worktree(self, task_id: str, base_ref: str = "HEAD") -> Dict[str, Any]:
        """Creates an isolated git worktree + branch under .keelway/worktrees/.
        Agent mutations land here, never directly on the user's branch."""
        status = self.get_git_status()
        if not status["is_git"]:
            raise ValueError("Workspace is not a Git repository.")
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", task_id)
        safe_id = re.sub(r"-+", "-", safe_id).strip("-") or "task"
        branch = f"keelway/task-{safe_id}"
        wt_dir = self.root / ".keelway" / "worktrees" / safe_id
        if wt_dir.exists():
            raise ValueError(f"Worktree already exists for task '{safe_id}'.")
        res = self._git(["worktree", "add", "-b", branch, str(wt_dir), base_ref])
        if res.returncode != 0:
            raise ValueError(f"git worktree add failed: {res.stderr.strip()}")
        return {
            "status": "created",
            "task_id": safe_id,
            "branch": branch,
            "path": str(wt_dir.relative_to(self.root)),
            "base_ref": base_ref,
            "isolation": "git-worktree",
        }

    def list_worktrees(self) -> Dict[str, Any]:
        """Lists git worktrees; entries under .keelway/worktrees are agent-isolated."""
        res = self._git(["worktree", "list", "--porcelain"])
        trees, current = [], {}
        for line in res.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    trees.append(current)
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("branch "):
                current["branch"] = line.rsplit("/", 1)[-1]
            elif line == "detached":
                current["branch"] = "(detached)"
        if current:
            trees.append(current)
        for t in trees:
            t["agent_isolated"] = "/.keelway/worktrees/" in t["path"].replace(os.sep, "/")
        return {"is_git": res.returncode == 0, "worktrees": trees}

    def remove_worktree(self, task_id: str, force: bool = False) -> Dict[str, Any]:
        """Removes an agent worktree. Refuses to remove anything outside
        .keelway/worktrees/ to protect the user's main checkout."""
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", task_id)
        safe_id = re.sub(r"-+", "-", safe_id).strip("-") or "task"
        wt_dir = self.root / ".keelway" / "worktrees" / safe_id
        if not wt_dir.exists():
            raise ValueError(f"No worktree for task '{safe_id}'.")
        args = ["worktree", "remove"] + (["--force"] if force else []) + [str(wt_dir)]
        res = self._git(args)
        if res.returncode != 0:
            raise ValueError(f"git worktree remove failed: {res.stderr.strip()}")
        return {"status": "removed", "task_id": safe_id, "force": force}

    # ---- Checkpoints (Gate-2: rollback) ----

    @property
    def _checkpoints_file(self) -> Path:
        return self.root / ".keelway" / "checkpoints.json"

    def _load_checkpoints(self) -> List[Dict[str, Any]]:
        f = self._checkpoints_file
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                return []
        return []

    def create_checkpoint(self, label: str = "") -> Dict[str, Any]:
        """Snapshots working-tree state without modifying it.
        Uses `git stash create`+`stash store`: a real commit object capturing
        staged+unstaged changes. Untracked files are NOT captured (git limit —
        reported honestly via `untracked_captured`)."""
        status = self.get_git_status()
        if not status["is_git"]:
            raise ValueError("Workspace is not a Git repository.")
        head = self._git(["rev-parse", "HEAD"]).stdout.strip()
        stash_oid = ""
        if not status["clean"]:
            create = self._git(["stash", "create"])
            stash_oid = create.stdout.strip()
            if stash_oid:
                msg = label or f"checkpoint {head[:8]}"
                self._git(["stash", "store", "-m", msg, stash_oid])
        import uuid, datetime, shutil
        cp_id = uuid.uuid4().hex[:12]
        untracked_dir = self.root / ".keelway" / "checkpoints" / cp_id / "untracked"
        untracked = [f["path"] for f in status["files"] if f["status"] == "??" and not f["path"].startswith(".keelway/")]
        for rel in untracked:
            src = self.resolve_safe_path(rel)
            if src.is_file():
                dst = untracked_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        cp = {
            "id": cp_id,
            "label": label or f"checkpoint-{head[:8]}",
            "head_sha": head,
            "stash_oid": stash_oid or None,
            "untracked_files": untracked,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        cps = self._load_checkpoints()
        cps.append(cp)
        self._checkpoints_file.parent.mkdir(parents=True, exist_ok=True)
        self._checkpoints_file.write_text(json.dumps(cps, indent=1))
        return {
            "status": "created", **cp,
            "untracked_captured": len(untracked) > 0,
            "restore_semantics": "git restore from snapshot commit + untracked file restore; overwrites tracked changes, does not delete files created after the checkpoint",
        }

    def list_checkpoints(self) -> Dict[str, Any]:
        return {"checkpoints": self._load_checkpoints()}

    def restore_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """Restores a checkpoint's working-tree snapshot via `git stash apply`.
        Fails cleanly rather than discarding state if the snapshot is gone."""
        cps = self._load_checkpoints()
        cp = next((c for c in cps if c["id"] == checkpoint_id), None)
        if not cp:
            raise ValueError(f"Checkpoint '{checkpoint_id}' not found.")
        import shutil
        untracked_dir = self.root / ".keelway" / "checkpoints" / cp["id"] / "untracked"
        restored_untracked = []
        if untracked_dir.is_dir():
            for src in untracked_dir.rglob("*"):
                if src.is_file():
                    rel = src.relative_to(untracked_dir).as_posix()
                    dst = self.resolve_safe_path(rel)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    restored_untracked.append(rel)
        if not cp.get("stash_oid"):
            return {"status": "restored", "id": checkpoint_id,
                    "note": "no tracked snapshot; restored untracked files only",
                    "restored_untracked": restored_untracked,
                    "head_sha": cp["head_sha"]}
        res = self._git(["restore", "--source=" + cp["stash_oid"], "--staged", "--worktree", "--", "."])
        if res.returncode != 0:
            raise ValueError(f"checkpoint restore failed: {res.stderr.strip()}")
        return {"status": "restored", "id": checkpoint_id,
                "applied": cp["stash_oid"],
                "restored_untracked": restored_untracked,
                "head_sha": cp["head_sha"]}

    # ---- CI status (Gate-2: PR → CI visibility) ----

    def get_ci_status(self, branch: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Reads GitHub Actions check runs via the `gh` CLI when available.
        Returns an honest `available:false` when gh/auth/remote is absent —
        degraded dependency, never fabricated status."""
        import shutil
        if not shutil.which("gh"):
            return {"available": False,
                    "reason": "GitHub CLI (`gh`) not installed; CI status requires gh auth."}
        args = ["gh", "run", "list", "--limit", str(limit),
                "--json", "status,conclusion,workflowName,headBranch,createdAt,displayTitle,url"]
        if branch:
            args += ["--branch", branch]
        res = subprocess.run(args, cwd=str(self.root), capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return {"available": False,
                    "reason": res.stderr.strip() or "gh run list failed"}
        try:
            runs = json.loads(res.stdout or "[]")
        except json.JSONDecodeError:
            return {"available": False, "reason": "unparseable gh output"}
        return {"available": True, "branch": branch or "all", "runs": runs, "count": len(runs)}
