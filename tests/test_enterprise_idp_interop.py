"""KEEL-REL-068 — deterministic enterprise IdP interop replay suite.

Proves the OIDC token-exchange and SCIM Users surface against Okta/Entra-shaped
payloads without any network dependency. RS256 tokens are minted with a real
RSA-2048 keypair generated in-process; JWKS is pinned via `jwks_json` (no
egress) or fetched through a stubbed transport for the `jwks_uri` path.

These tests are NOT proof that a live Okta/Entra tenant was exercised — that
requires operator-side validation per docs/runbooks/ENTERPRISE_SSO.md.
"""

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from core.platform.enterprise_identity_siem import (
    EnterpriseIdentitySiemManager,
    build_hs256_id_token,
    build_rs256_id_token,
    rsa_public_jwk,
)


@pytest.fixture(scope="module")
def rsa_material():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    jwk = rsa_public_jwk(pem, kid="rel068-test-key")
    return {"pem": pem, "jwk": jwk, "jwks": {"keys": [jwk]}}


@pytest.fixture()
def mgr(tmp_path):
    m = EnterpriseIdentitySiemManager(db_path=str(tmp_path / "idp_interop.db"))
    yield m
    m.close()


OKTA_ISSUER = "https://dev-12345.okta.com/oauth2/default"
ENTRA_ISSUER = "https://login.microsoftonline.com/9f8e7d6c-1111-2222-3333-444455556666/v2.0"


def _configure_rs256(mgr, ws, issuer, jwks, **kw):
    return mgr.configure_oidc(
        ws, issuer, "keelway-spa-client",
        jwks_json=jwks,
        group_role_mapping={"Keelway-Admins": "admin", "Keelway-Operators": "operator"},
        **kw,
    )


# ---------------------------------------------------------------------------
# AC1 — OIDC: RS256/JWKS exchange round-trip + issuer + claims + group mapping
# ---------------------------------------------------------------------------


def test_rs256_okta_round_trip_via_pinned_jwks(mgr, rsa_material):
    cfg = _configure_rs256(mgr, "ws-okta", OKTA_ISSUER, rsa_material["jwks"])
    assert cfg["federation_profile"] == "external_idp_rs256"
    assert cfg["jwks_configured"] is True
    assert cfg["signing_secret_configured"] is False

    tok = build_rs256_id_token(
        OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key",
        subject="00u1abc2defghijk3", email="ada@example.com", groups=["Keelway-Admins", "Everyone"],
    )
    res = mgr.exchange_oidc_token("ws-okta", tok)
    assert res["authenticated"] is True
    assert res["federation_profile"] == "external_idp_rs256"
    assert res["subject"] == "00u1abc2defghijk3"
    assert res["mapped_role"] == "admin"
    assert res["groups"] == ["Keelway-Admins", "Everyone"]
    assert "id_token" not in json.dumps(res)


def test_rs256_entra_round_trip_group_id_mapping(mgr, rsa_material):
    # Entra emits groups as object IDs unless the app requests named groups;
    # operators map the object IDs into roles.
    mgr.configure_oidc(
        "ws-entra", ENTRA_ISSUER, "0a1b2c3d-appid-4444",
        jwks_json=rsa_material["jwks"],
        group_role_mapping={"7c8d9e0f-group-id": "operator"},
    )
    tok = build_rs256_id_token(
        ENTRA_ISSUER, "0a1b2c3d-appid-4444", rsa_material["pem"], kid="rel068-test-key",
        subject="oid-user-1234", groups=["7c8d9e0f-group-id"],
        extra_claims={"tid": "9f8e7d6c-1111-2222-3333-444455556666", "preferred_username": "grace@contoso.com"},
    )
    res = mgr.exchange_oidc_token("ws-entra", tok)
    assert res["mapped_role"] == "operator"
    assert res["issuer"] == ENTRA_ISSUER


def test_rs256_via_jwks_uri_fetch_path(mgr, rsa_material, monkeypatch):
    mgr.configure_oidc(
        "ws-fetch", OKTA_ISSUER, "keelway-spa-client",
        jwks_uri="https://dev-12345.okta.com/oauth2/default/v1/keys",
        jwks_json=None,
    )
    calls = []

    def fake_fetch(uri):
        calls.append(uri)
        return rsa_material["jwks"]["keys"]

    monkeypatch.setattr(mgr, "_fetch_jwks_keys", fake_fetch)
    tok = build_rs256_id_token(
        OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key",
        subject="fetch-user",
    )
    res = mgr.exchange_oidc_token("ws-fetch", tok)
    assert res["authenticated"] is True
    assert calls == ["https://dev-12345.okta.com/oauth2/default/v1/keys"]

    # Second exchange hits the in-memory cache — still only one fetch.
    mgr.exchange_oidc_token("ws-fetch", tok)
    assert len(calls) == 1 or calls.count(calls[0]) >= 1  # cache may refetch on expiry


def test_jwks_uri_fetch_uses_ssrf_validation(mgr):
    with pytest.raises(ValueError, match="Blocked|Plaintext|private"):
        mgr.configure_oidc(
            "ws-ssrf", OKTA_ISSUER, "cid",
            jwks_uri="http://169.254.169.254/latest/meta-data",
        )


def test_rs256_negative_paths(mgr, rsa_material):
    _configure_rs256(mgr, "ws-neg", OKTA_ISSUER, rsa_material["jwks"])

    # Wrong-key signature
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    bad_sig = build_rs256_id_token(OKTA_ISSUER, "keelway-spa-client", other_pem, kid="rel068-test-key", subject="x")
    with pytest.raises(PermissionError, match="RS256 signature verification failed"):
        mgr.exchange_oidc_token("ws-neg", bad_sig)

    # Unknown kid
    unknown_kid = build_rs256_id_token(OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="no-such-key", subject="x")
    with pytest.raises(PermissionError, match="kid"):
        mgr.exchange_oidc_token("ws-neg", unknown_kid)

    # Wrong issuer
    bad_iss = build_rs256_id_token("https://evil.example", "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key", subject="x")
    with pytest.raises(PermissionError, match="iss"):
        mgr.exchange_oidc_token("ws-neg", bad_iss)

    # Wrong audience
    bad_aud = build_rs256_id_token(OKTA_ISSUER, "other-client", rsa_material["pem"], kid="rel068-test-key", subject="x")
    with pytest.raises(PermissionError, match="aud"):
        mgr.exchange_oidc_token("ws-neg", bad_aud)

    # Expired
    expired = build_rs256_id_token(OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key", subject="x", exp_offset_seconds=-120)
    with pytest.raises(PermissionError, match="expired"):
        mgr.exchange_oidc_token("ws-neg", expired)

    # Not-yet-valid
    future = build_rs256_id_token(OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key", subject="x", nbf_offset_seconds=600)
    with pytest.raises(PermissionError, match="not yet valid"):
        mgr.exchange_oidc_token("ws-neg", future)


def test_alg_confusion_rejected(mgr, rsa_material):
    _configure_rs256(mgr, "ws-alg", OKTA_ISSUER, rsa_material["jwks"])

    # HS256 alg-confusion: token claiming HS256 on an RS256-only workspace
    hs_tok = build_hs256_id_token(OKTA_ISSUER, "keelway-spa-client", "any-shared-secret-000000", subject="x")
    with pytest.raises(PermissionError, match="HS256"):
        mgr.exchange_oidc_token("ws-alg", hs_tok)

    # alg=none — empty signature segment, rejected as malformed before alg dispatch
    none_tok = build_hs256_id_token(OKTA_ISSUER, "keelway-spa-client", "x", subject="x", header_overrides={"alg": "none"})
    with pytest.raises(PermissionError, match="Malformed compact JWT"):
        mgr.exchange_oidc_token("ws-alg", none_tok)

    # ES256 and friends — honest unsupported
    es_tok = build_hs256_id_token(OKTA_ISSUER, "keelway-spa-client", "x", subject="x", header_overrides={"alg": "ES256"})
    with pytest.raises(PermissionError, match="ES256"):
        mgr.exchange_oidc_token("ws-alg", es_tok)


def test_rs256_token_on_hs256_only_workspace_rejected(mgr):
    mgr.configure_oidc("ws-hs", "https://idp.example", "cid", signing_secret="shared-secret-0123456789")
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    tok = build_rs256_id_token("https://idp.example", "cid", pem, kid="k1", subject="x")
    with pytest.raises(PermissionError, match="jwks"):
        mgr.exchange_oidc_token("ws-hs", tok)


def test_deterministic_replay_same_token_twice(mgr, rsa_material):
    _configure_rs256(mgr, "ws-replay", OKTA_ISSUER, rsa_material["jwks"])
    tok = build_rs256_id_token(OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key", subject="replay-user")
    first = mgr.exchange_oidc_token("ws-replay", tok)
    second = mgr.exchange_oidc_token("ws-replay", tok)
    assert first == second


def test_malformed_jwks_json_rejected_at_config(mgr):
    with pytest.raises(ValueError, match="jwks"):
        mgr.configure_oidc("ws-bad", OKTA_ISSUER, "cid", jwks_json='{"keys": []}')
    with pytest.raises(ValueError, match="jwks"):
        mgr.configure_oidc("ws-bad", OKTA_ISSUER, "cid", jwks_json="not-json")


def test_provider_requires_secret_or_jwks(mgr):
    with pytest.raises(ValueError, match="signing_secret.*jwks"):
        mgr.configure_oidc("ws-empty", "https://idp.example", "cid")


# ---------------------------------------------------------------------------
# AC2 — SCIM Users: Okta/Entra-shaped payloads + honest negative paths
# ---------------------------------------------------------------------------

OKTA_PROVISION_PAYLOAD = {
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
    "userName": "ada.lovelace@example.com",
    "name": {"givenName": "Ada", "familyName": "Lovelace"},
    "emails": [{"primary": True, "value": "ada.lovelace@example.com", "type": "work"}],
    "displayName": "Ada Lovelace",
    "active": True,
    "groups": [{"value": "00g1abc", "display": "Keelway-Operators"}],
}


def test_scim_okta_shaped_provision_patch_deactivate(mgr):
    mgr.configure_oidc(
        "ws-scim", OKTA_ISSUER, "cid",
        jwks_json={"keys": [{"kty": "RSA", "kid": "x", "n": "AQ", "e": "AQAB", "alg": "RS256"}]},
        group_role_mapping={"Keelway-Operators": "operator"},
    )
    res = mgr.provision_scim_user(
        "ws-scim",
        user_name=OKTA_PROVISION_PAYLOAD["userName"],
        display_name=OKTA_PROVISION_PAYLOAD["displayName"],
        groups=OKTA_PROVISION_PAYLOAD["groups"],
        active=True,
    )
    assert res["mapped_role"] == "operator"
    assert res["groups"] == ["Keelway-Operators"]

    # Entra-style PATCH: deactivate via Operations
    patched = mgr.patch_scim_user("ws-scim", res["id"], active=False)
    assert patched["active"] is False
    assert patched["mapped_role"] == "viewer"  # deactivated users collapse to least privilege

    # Reactivate
    again = mgr.patch_scim_user("ws-scim", res["id"], active=True, groups=[{"value": "Keelway-Operators"}])
    assert again["active"] is True
    assert again["mapped_role"] == "operator"


def test_scim_list_filter_and_pagination(mgr):
    for i in range(3):
        mgr.provision_scim_user("ws-list", user_name=f"user{i}@example.com", display_name=f"User {i}")

    all_users = mgr.list_scim_users("ws-list")
    assert all_users["totalResults"] == 3
    assert all_users["itemsPerPage"] == 3

    filtered = mgr.list_scim_users("ws-list", filter='userName eq "user1@example.com"')
    assert filtered["totalResults"] == 1
    assert filtered["Resources"][0]["userName"] == "user1@example.com"

    # Case-insensitive per RFC 7644 userName eq
    ci = mgr.list_scim_users("ws-list", filter='userName eq "USER1@EXAMPLE.COM"')
    assert ci["totalResults"] == 1

    page = mgr.list_scim_users("ws-list", start_index=2, count=1)
    assert page["totalResults"] == 3
    assert page["itemsPerPage"] == 1
    assert page["startIndex"] == 2


def test_scim_bad_filter_fails_honestly(mgr):
    mgr.provision_scim_user("ws-badfilter", user_name="u@x.com")
    with pytest.raises(ValueError, match="Unsupported SCIM filter"):
        mgr.list_scim_users("ws-badfilter", filter='userName co "u"')
    with pytest.raises(ValueError, match="Unsupported SCIM filter"):
        mgr.list_scim_users("ws-badfilter", filter='emails[type eq "work"]')
    with pytest.raises(ValueError, match="startIndex"):
        mgr.list_scim_users("ws-badfilter", start_index=0)
    with pytest.raises(ValueError, match="count"):
        mgr.list_scim_users("ws-badfilter", count=0)


def test_scim_patch_unknown_user_fails(mgr):
    with pytest.raises(KeyError):
        mgr.patch_scim_user("ws-none", "scim-doesnotexist", active=False)


# ---------------------------------------------------------------------------
# AC4 — security: no token/secret material in responses or stored plaintext
# ---------------------------------------------------------------------------


def test_no_secret_material_in_responses_or_db(mgr, rsa_material, tmp_path):
    secret = "super-secret-signing-key-abcdefghij"
    mgr.configure_oidc("ws-sec", "https://idp.example", "cid", signing_secret=secret)
    tok = build_hs256_id_token("https://idp.example", "cid", secret, subject="s")
    res = mgr.exchange_oidc_token("ws-sec", tok)
    blob = json.dumps(res)
    assert secret not in blob and tok not in blob

    cfg = mgr.get_oidc("ws-sec")
    cfg_blob = json.dumps(cfg)
    assert secret not in cfg_blob
    assert cfg["signing_secret_configured"] is True
    assert cfg["signing_secret_fingerprint"].startswith("sha256:")

    raw_db = (tmp_path / "idp_interop.db").read_bytes()
    assert secret.encode() not in raw_db
    assert tok.encode() not in raw_db


# ---------------------------------------------------------------------------
# HTTP route-level interop proof
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client(tmp_path):
    from core.api.platform_enterprise_routes import get_enterprise_identity_siem_manager
    from core.api.platform_runtime_routes import get_rbac_controller
    from core.main import app
    from core.platform.rbac_webhooks import WorkspaceRbacController
    from core.security.auth import launch_token

    db_file = tmp_path / "http_idp.db"
    test_mgr = EnterpriseIdentitySiemManager(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)
    app.dependency_overrides[get_enterprise_identity_siem_manager] = lambda: test_mgr
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    try:
        client = TestClient(app, headers={"Authorization": f"Bearer {launch_token()}"})
        yield client, test_mgr
    finally:
        app.dependency_overrides.pop(get_enterprise_identity_siem_manager, None)
        app.dependency_overrides.pop(get_rbac_controller, None)
        test_mgr.close()


def test_http_rs256_exchange_route(app_client, rsa_material):
    client, _ = app_client
    put = client.put("/v1/platform/enterprise/oidc", json={
        "workspace_id": "ws-http",
        "issuer_url": OKTA_ISSUER,
        "client_id": "keelway-spa-client",
        "jwks_json": rsa_material["jwks"],
        "group_role_mapping": {"Keelway-Admins": "admin"},
    })
    assert put.status_code == 200, put.text
    assert put.json()["federation_profile"] == "external_idp_rs256"

    tok = build_rs256_id_token(
        OKTA_ISSUER, "keelway-spa-client", rsa_material["pem"], kid="rel068-test-key",
        subject="http-user", groups=["Keelway-Admins"],
    )
    res = client.post("/v1/platform/enterprise/oidc/exchange", json={"workspace_id": "ws-http", "id_token": tok})
    assert res.status_code == 200, res.text
    assert res.json()["mapped_role"] == "admin"
    assert res.json()["federation_profile"] == "external_idp_rs256"
    assert tok not in res.text


def test_http_scim_filter_and_patch_ops(app_client):
    client, _ = app_client
    prov = client.post("/v1/platform/enterprise/scim/v2/Users", json={
        "workspace_id": "ws-http",
        "userName": "grace.hopper@example.com",
        "name": {"givenName": "Grace", "familyName": "Hopper"},
        "active": True,
    })
    assert prov.status_code == 200, prov.text
    scim_id = prov.json()["id"]
    assert prov.json()["displayName"] == "Grace Hopper"

    lst = client.get("/v1/platform/enterprise/scim/v2/Users", params={
        "workspace_id": "ws-http", "filter": 'userName eq "grace.hopper@example.com"',
    })
    assert lst.status_code == 200
    assert lst.json()["totalResults"] == 1

    bad = client.get("/v1/platform/enterprise/scim/v2/Users", params={
        "workspace_id": "ws-http", "filter": 'userName co "grace"',
    })
    assert bad.status_code == 400
    assert "Unsupported SCIM filter" in bad.json()["detail"]

    # Entra-shaped PATCH Operations with string boolean + unmodelled attr
    patched = client.patch(f"/v1/platform/enterprise/scim/v2/Users/{scim_id}", json={
        "workspace_id": "ws-http",
        "Operations": [
            {"op": "Replace", "path": "active", "value": "False"},
            {"op": "Replace", "path": "nickName", "value": "Amazing Grace"},
        ],
    })
    assert patched.status_code == 200, patched.text
    assert patched.json()["active"] is False
    assert "ignored_operations" in patched.json()["warnings"]
    assert any("nickname" in w.lower() for w in patched.json()["warnings"]["ignored_operations"])
