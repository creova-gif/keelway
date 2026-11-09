"""Public keys that may sign Keelway licences, by key id.

Licences are Ed25519-signed by Sorvex Labs. Only public keys live here, so a machine that checks a licence
offline cannot create one. Empty until Sorvex Labs runs `keelway entitlements keygen` on its own signing
machine and adds the printed public key; until then every licence check is refused (fail closed).
"""

from typing import Dict

TRUSTED_LICENCE_KEYS: Dict[str, str] = {}
