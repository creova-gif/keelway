"""Public keys trusted for Sorvex Labs first-party marketplace manifests, by key id.

Only public keys live here. The private key is held by Sorvex Labs and supplied to the process that
publishes curated seed packages via `KEELWAY_FIRST_PARTY_MANIFEST_SIGNING_KEY` (PKCS#8 PEM). Empty until
Sorvex Labs generates a key with `generate_publisher_keypair()` and adds the public half; until then
first-party packages are only verifiable where the signing key is configured (fail closed elsewhere).
"""

from typing import Dict

TRUSTED_FIRST_PARTY_MANIFEST_KEYS: Dict[str, str] = {}
