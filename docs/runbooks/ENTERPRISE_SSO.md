# Enterprise SSO & SCIM Setup Runbook (KEEL-REL-068 / OD-5)

Configures **OIDC token exchange** and **SCIM 2.0 Users** for one organization
against **Okta** or **Microsoft Entra ID**.

## What Keelway verifies — honest boundary

`POST /v1/platform/enterprise/oidc/exchange` accepts **id_tokens** and verifies:

| Check | Behavior |
|---|---|
| Signature | `HS256` (self-issued, shared secret) **or** `RS256` against configured JWKS. `ES256`/`EdDSA`/`none` are rejected. |
| `iss` | Exact match to configured `issuer_url` |
| `aud` | Configured `client_id` present (string or list) |
| `exp`/`nbf` | Numeric; 30s clock skew |
| `sub` | Non-empty |
| `groups` | Mapped to `viewer`/`builder`/`operator`/`admin`/`owner` via `group_role_mapping` (highest precedence wins; unmapped → `viewer`) |

Not implemented: OIDC discovery document fetching, ES256/EdDSA, SAML, auth-code
redirect flow (exchange takes an already-minted `id_token`), SCIM group sync,
org-directory sync (deferred per OD-5).

Federation profiles disclosed in every response:

- `self_issued_hs256` — sovereign/air-gapped; your side mints the tokens.
- `external_idp_rs256` — real IdP RS256 verified against `jwks_json` (pinned,
  no egress) or `jwks_uri` (fetched over HTTPS, SSRF-validated, 300s cache).

## Prerequisites

- Keelway API reachable (`keelway-ops serve` or the platform service).
- An owner/operator API token with `rbac:manage` for OIDC config and SCIM
  provisioning, `workspace:read` for exchange/list.
- IdP admin access to create an OIDC app + SCIM provisioning integration.

---

## Option A — Okta

### 1. Create the OIDC application

1. **Admin Console → Applications → Create App Integration**
2. Sign-in method **OIDC — OpenID Connect**; application type **Web** (or SPA).
3. Sign-in redirect URIs — Keelway validates `id_token` claims rather than
   completing a redirect, so register the URI your front channel will use
   (e.g. `https://<your-keelway-host>/auth/callback`). Sign-out URI optional.
4. Assign the groups that should receive access.

### 2. Enable the `groups` claim

1. **Security → API → Authorization Servers → default → Claims → Add Claim**
2. Name `groups`, include in **ID token**, filter — choose the groups you
   assigned (e.g. `Keelway-Admins`, `Keelway-Operators`). Prefer a name-based
   filter so claim values match your `group_role_mapping` keys.
3. Note the **Issuer URI** (e.g.
   `https://dev-12345.okta.com/oauth2/default`) and **JWKS URI**
   (`<issuer>/v1/keys`).

### 3. Configure Keelway

```bash
curl -X PUT "$KEELWAY/v1/platform/enterprise/oidc" \
  -H "Authorization: Bearer $KEELWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "default",
    "issuer_url": "https://dev-12345.okta.com/oauth2/default",
    "client_id": "<okta-client-id>",
    "jwks_uri": "https://dev-12345.okta.com/oauth2/default/v1/keys",
    "group_role_mapping": {"Keelway-Admins": "admin", "Keelway-Operators": "operator"},
    "enabled": true
  }'
```

**Air-gapped / pinned keys:** fetch the JWKS once and pass it as `jwks_json`
instead — no egress at exchange time. `GET /v1/platform/enterprise/oidc` shows
`federation_profile: "external_idp_rs256"` and `jwks_configured: true`.

### 4. Okta SCIM provisioning (Users only)

1. Applications → your app → **Provisioning → Enable SCIM**.
2. SCIM connector base URL:
   `https://<your-keelway-host>/v1/platform/enterprise/scim/v2`
3. Supported actions: **Import** (list), **Push new users**, **Push profile
   updates**, **Push user deactivation**.
4. Auth: HTTP header `Authorization: Bearer $KEELWAY_TOKEN` with a token
   holding `rbac:manage` on the workspace.
5. Attribute mapping: `userName` (required), `name.givenName`,
   `name.familyName`, `displayName`, `active`, `groups`. Other attributes are
   ignored and reported under `warnings.ignored_operations` — they do not fail.

### 5. Validate

```bash
# Exchange an id_token obtained from Okta's token endpoint
curl -X POST "$KEELWAY/v1/platform/enterprise/oidc/exchange" \
  -H "Authorization: Bearer $KEELWAY_TOKEN" \
  -d '{"workspace_id": "default", "id_token": "<id_token>"}'
# → {"authenticated": true, "mapped_role": "...", "federation_profile": "external_idp_rs256"}

curl "$KEELWAY/v1/platform/enterprise/scim/v2/Users?workspace_id=default&filter=userName%20eq%20%22user%40corp.com%22" \
  -H "Authorization: Bearer $KEELWAY_TOKEN"
```

---

## Option B — Microsoft Entra ID

### 1. Register the application

1. **Entra admin center → App registrations → New registration**
2. Redirect URI (Web): `https://<your-keelway-host>/auth/callback`.
3. **Token configuration → Add groups claim** — for role mapping prefer
   *Groups assigned to the application*; note whether you emit **group IDs**
   (default) or **sAMAccountName** — your `group_role_mapping` keys must match
   what the token actually contains.
4. Note: **Client ID** (Application ID) and **Issuer** —
   `https://login.microsoftonline.com/<tenant-id>/v2.0`.
5. JWKS URI: `https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys`.

### 2. Configure Keelway

```bash
curl -X PUT "$KEELWAY/v1/platform/enterprise/oidc" \
  -H "Authorization: Bearer $KEELWAY_TOKEN" \
  -d '{
    "workspace_id": "default",
    "issuer_url": "https://login.microsoftonline.com/<tenant-id>/v2.0",
    "client_id": "<application-id>",
    "jwks_uri": "https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys",
    "group_role_mapping": {"<entra-group-object-id>": "operator"},
    "enabled": true
  }'
```

Entra sends group **object IDs** by default — map those IDs, or configure the
groups claim to emit names and map the names.

### 3. Entra provisioning (Users only)

1. **Enterprise applications → your app → Provisioning → Automatic**.
2. Tenant URL: `https://<your-keelway-host>/v1/platform/enterprise/scim/v2`
3. Secret token: a Keelway bearer token with `rbac:manage`.
4. Mappings — keep: `userName`, `displayName`, `active`, `name.givenName`,
   `name.familyName`, `groups` (group membership is used for role mapping).
   Keelway honors `active` string booleans (`"True"`/`"False"`) and composes
   `displayName` from `name.givenName`/`name.familyName` when not sent directly.

### 4. Validate — same exchange + list calls as the Okta section.

---

## Security notes

- `signing_secret` (HS256 mode only) is AES-256-GCM encrypted at rest; only a
  `sha256:` fingerprint is returned by `GET`. JWKS is public key material and
  is stored in plaintext by design.
- `id_token` material is never persisted, logged, exported to SIEM, or echoed
  in responses — the exchange returns only `subject`, `email`, `groups`,
  `mapped_role`, `issuer`, `federation_profile`.
- `jwks_uri` goes through the same SSRF validation as `issuer_url` (HTTPS
  required except loopback; private/link-local/metadata hosts rejected).
- SCIM list supports `filter=userName eq "<x>"` (case-insensitive),
  `startIndex`/`count`. Unsupported filters return `400` — they never degrade
  to an unfiltered dump.
- SCIM PATCH applies `active`/`displayName`/`groups` and `name.*` composition;
  unmodelled paths are applied-then-reported under `warnings.ignored_operations`,
  never silently dropped.

## Validation status

- Deterministic replay: `tests/test_enterprise_idp_interop.py` mints real
  RSA-signed tokens against pinned JWKS — covers Okta/Entra claim shapes,
  negative paths, and SCIM list/provision/patch.
- **Live Okta/Entra tenant validation is an operator step**: this runbook +
  the exchange endpoint are the contract; a real round-trip requires your
  tenant credentials and is intentionally not simulated in CI.
