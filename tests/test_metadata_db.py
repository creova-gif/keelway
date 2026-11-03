"""Tests for Keelway Metadata Database (04_API_AND_DATA_CONTRACTS.md).
Validates multi-tenant isolation, organization/project management, and environments.
"""
import os
import tempfile
from keelway.core.database import MetadataDatabase


def test_metadata_database_tenant_isolation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "meta_test.db")
        db = MetadataDatabase(db_path=db_path)

        # Create two separate orgs
        org1 = db.create_organization("org_alpha", region="us-east-1")
        org2 = db.create_organization("org_beta", region="eu-west-1")

        # Create projects in Org 1
        db.create_project("proj_a1", "org_alpha", "github.com/alpha/repo1")
        db.create_project("proj_a2", "org_alpha", "github.com/alpha/repo2")

        # Create projects in Org 2
        db.create_project("proj_b1", "org_beta", "github.com/beta/repo1")

        # Verify strict isolation
        alpha_projects = db.list_projects_for_org("org_alpha")
        assert len(alpha_projects) == 2
        assert {p.id for p in alpha_projects} == {"proj_a1", "proj_a2"}

        beta_projects = db.list_projects_for_org("org_beta")
        assert len(beta_projects) == 1
        assert beta_projects[0].id == "proj_b1"


def test_metadata_database_environments_with_quorum_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "env_test.db")
        db = MetadataDatabase(db_path=db_path)

        db.create_organization("org_corp")
        db.create_project("proj_api", "org_corp", "github.com/corp/api")

        env_prod = db.create_environment(
            env_id="env_prod_01",
            project_id="proj_api",
            name="production",
            classification="production",
            requires_two_human_quorum=True,
        )
        assert env_prod.requires_two_human_quorum is True

        fetched = db.get_environment("env_prod_01")
        assert fetched is not None
        assert fetched.name == "production"
        assert fetched.requires_two_human_quorum is True
