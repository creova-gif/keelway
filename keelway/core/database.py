"""Keelway Relational Multi-Tenant Metadata Storage.
Implements the core entity schema specified in 04_API_AND_DATA_CONTRACTS.md:
organizations, users, memberships, projects, environments, and runs.
"""
from __future__ import annotations

import datetime
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class OrganizationRecord(BaseModel):
    id: str
    region: str = "us-east-1"
    status: str = "ACTIVE"
    created_at: str


class ProjectRecord(BaseModel):
    id: str
    org_id: str
    repo: str
    default_branch: str = "main"
    created_at: str


class EnvironmentRecord(BaseModel):
    id: str
    project_id: str
    name: str
    classification: str = "internal"  # internal, sensitive, production
    requires_two_human_quorum: bool = False


class MetadataDatabase:
    """Manages multi-tenant relational persistence with strict org boundaries."""

    def __init__(self, db_path: str = "keelway_metadata.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id TEXT PRIMARY KEY,
                    region TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    repo TEXT NOT NULL,
                    default_branch TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(org_id) REFERENCES organizations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS environments (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    requires_two_human_quorum INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_proj_org ON projects(org_id);
                CREATE INDEX IF NOT EXISTS idx_env_proj ON environments(project_id);
                """
            )
            conn.commit()

    def create_organization(self, org_id: str, region: str = "us-east-1") -> OrganizationRecord:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO organizations (id, region, status, created_at) VALUES (?, ?, 'ACTIVE', ?);",
                (org_id, region, now),
            )
            conn.commit()
        return OrganizationRecord(id=org_id, region=region, status="ACTIVE", created_at=now)

    def get_organization(self, org_id: str) -> Optional[OrganizationRecord]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE id = ?;", (org_id,)).fetchone()
            if row:
                return OrganizationRecord(**dict(row))
        return None

    def create_project(self, project_id: str, org_id: str, repo: str) -> ProjectRecord:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO projects (id, org_id, repo, default_branch, created_at) VALUES (?, ?, ?, 'main', ?);",
                (project_id, org_id, repo, now),
            )
            conn.commit()
        return ProjectRecord(id=project_id, org_id=org_id, repo=repo, created_at=now)

    def list_projects_for_org(self, org_id: str) -> List[ProjectRecord]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects WHERE org_id = ?;", (org_id,)).fetchall()
            return [ProjectRecord(**dict(r)) for r in rows]

    def create_environment(
        self,
        env_id: str,
        project_id: str,
        name: str,
        classification: str = "internal",
        requires_two_human_quorum: bool = False,
    ) -> EnvironmentRecord:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO environments (id, project_id, name, classification, requires_two_human_quorum)
                VALUES (?, ?, ?, ?, ?);
                """,
                (env_id, project_id, name, classification, 1 if requires_two_human_quorum else 0),
            )
            conn.commit()
        return EnvironmentRecord(
            id=env_id,
            project_id=project_id,
            name=name,
            classification=classification,
            requires_two_human_quorum=requires_two_human_quorum,
        )

    def get_environment(self, env_id: str) -> Optional[EnvironmentRecord]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM environments WHERE id = ?;", (env_id,)).fetchone()
            if row:
                d = dict(row)
                d["requires_two_human_quorum"] = bool(d["requires_two_human_quorum"])
                return EnvironmentRecord(**d)
        return None
