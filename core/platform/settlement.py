"""
Keelway Marketplace Commercial Settlement Ledger (`MarketplaceSettlementLedger`).

Records commercial and free Marketplace package acquisitions with integer-cent precision
(`gross_cents`, `creator_payout_cents`, `platform_fee_cents`), zero rounding drift
(`creator_payout_cents + platform_fee_cents == gross_cents`), SPDX license attribution,
cryptographic SHA-256 entitlement/receipt digests, SQLite WAL durability, and automatic
workspace installation in `MarketplaceRegistry`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import threading
from typing import Any, Dict, List, Optional, Union
import uuid

from core.platform.marketplace import MarketplaceRegistry, marketplace_registry
from core.platform.persistence import SQLitePlatformStore

SETTLEMENT_SPLIT_LABELS: Dict[str, str] = {
    "verified_third_party": "85/15 (85% Creator / 15% Platform)",
    "enterprise_partner": "80/20 (80% Partner / 20% Platform)",
    "first_party": "0/100 (100% First-Party)",
}


def _usd_to_cents(price_usd: Union[int, float, str, Decimal]) -> int:
    dec = Decimal(str(price_usd or 0))
    if dec < 0:
        raise ValueError("Package price_usd must be non-negative.")
    return int((dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cents_to_usd(cents: int) -> float:
    return round(int(cents) / 100.0, 2)


def calculate_settlement_split(
    publisher_tier: str,
    price_usd: Optional[Union[int, float, str, Decimal]] = None,
    *,
    gross_cents: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute zero-drift integer-cent revenue split across publisher tiers."""
    tier = str(publisher_tier or "").strip().lower()
    if tier not in SETTLEMENT_SPLIT_LABELS:
        raise ValueError(
            f"Unsupported publisher_tier '{publisher_tier}'. "
            f"Expected one of {sorted(SETTLEMENT_SPLIT_LABELS.keys())}."
        )
    if gross_cents is None:
        total_cents = _usd_to_cents(0 if price_usd is None else price_usd)
    else:
        total_cents = int(gross_cents)
        if total_cents < 0:
            raise ValueError("gross_cents must be non-negative.")

    if tier == "verified_third_party":
        creator_cents = int(round(total_cents * 85 / 100))
        platform_cents = total_cents - creator_cents
    elif tier == "enterprise_partner":
        creator_cents = int(round(total_cents * 80 / 100))
        platform_cents = total_cents - creator_cents
    else:  # first_party
        creator_cents = 0
        platform_cents = total_cents

    return {
        "publisher_tier": tier,
        "split_label": SETTLEMENT_SPLIT_LABELS[tier],
        "gross_cents": total_cents,
        "creator_payout_cents": creator_cents,
        "platform_fee_cents": platform_cents,
        "gross_usd": _cents_to_usd(total_cents),
        "creator_payout_usd": _cents_to_usd(creator_cents),
        "platform_fee_usd": _cents_to_usd(platform_cents),
    }


def _sha256_canonical(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SettlementRecord:
    """Immutable cryptographic receipt for a Marketplace acquisition."""

    settlement_id: str
    package_id: str
    package_version: str
    buyer_tenant_id: str
    publisher_tier: str
    gross_cents: int
    creator_payout_cents: int
    platform_fee_cents: int
    gross_usd: float
    creator_payout_usd: float
    platform_fee_usd: float
    split_label: str
    license_spdx: str
    entitlement_sha256: str
    receipt_sha256: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SettlementRecord:
        gross_cents = (
            int(data["gross_cents"])
            if "gross_cents" in data
            else _usd_to_cents(data.get("gross_usd", 0.0))
        )
        creator_cents = (
            int(data["creator_payout_cents"])
            if "creator_payout_cents" in data
            else _usd_to_cents(data.get("creator_payout_usd", 0.0))
        )
        platform_cents = (
            int(data["platform_fee_cents"])
            if "platform_fee_cents" in data
            else (gross_cents - creator_cents)
        )
        return cls(
            settlement_id=str(data["settlement_id"]),
            package_id=str(data["package_id"]),
            package_version=str(data.get("package_version") or "1.0.0"),
            buyer_tenant_id=str(data.get("buyer_tenant_id") or "default"),
            publisher_tier=str(data["publisher_tier"]),
            gross_cents=gross_cents,
            creator_payout_cents=creator_cents,
            platform_fee_cents=platform_cents,
            gross_usd=_cents_to_usd(gross_cents),
            creator_payout_usd=_cents_to_usd(creator_cents),
            platform_fee_usd=_cents_to_usd(platform_cents),
            split_label=str(data["split_label"]),
            license_spdx=str(data.get("license_spdx") or "Apache-2.0"),
            entitlement_sha256=str(data["entitlement_sha256"]),
            receipt_sha256=str(data["receipt_sha256"]),
            created_at=str(data["created_at"]),
        )


class MarketplaceSettlementLedger:
    """Durable commercial settlement ledger backed by `SQLitePlatformStore` and `MarketplaceRegistry`."""

    def __init__(
        self,
        registry: Optional[MarketplaceRegistry] = None,
        store: Optional[SQLitePlatformStore] = None,
    ) -> None:
        self._lock = threading.RLock()
        self.registry: MarketplaceRegistry = registry if registry is not None else marketplace_registry
        self.store: Optional[SQLitePlatformStore] = (
            store if store is not None else getattr(self.registry, "store", None)
        )
        self._records: Dict[str, SettlementRecord] = {}

        if self.store is not None:
            for row in self.store.list_settlements():
                rec = SettlementRecord.from_dict(row)
                self._records[rec.settlement_id] = rec

    @staticmethod
    def _resolve_license_spdx(pkg: Dict[str, Any], gross_cents: int) -> str:
        explicit = str(pkg.get("license_spdx") or pkg.get("license") or "").strip()
        if explicit:
            return explicit
        if gross_cents == 0:
            return "Apache-2.0"
        if str(pkg.get("publisher_tier") or "") == "enterprise_partner":
            return "LicenseRef-Keelway-Enterprise-Commercial"
        return "LicenseRef-Keelway-Marketplace-Commercial"

    def purchase_package(
        self,
        package_id: str,
        buyer_tenant_id: str = "default",
        workspace_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        registry: Optional[MarketplaceRegistry] = None,
    ) -> SettlementRecord:
        clean_pkg_id = str(package_id or "").strip()
        if not clean_pkg_id:
            raise ValueError("package_id must be non-empty.")
        clean_tenant = str(buyer_tenant_id or "default").strip() or "default"

        active_registry = registry if registry is not None else self.registry
        pkg = active_registry.get_package(clean_pkg_id)
        if pkg is None:
            raise KeyError(f"Marketplace package '{clean_pkg_id}' not found.")

        split = calculate_settlement_split(
            publisher_tier=str(pkg.get("publisher_tier") or "verified_third_party"),
            price_usd=pkg.get("price_usd", 0.0),
        )
        pkg_version = str(pkg.get("version") or "1.0.0")
        manifest_sha = str(pkg.get("manifest_sha256") or "")
        license_spdx = self._resolve_license_spdx(pkg, split["gross_cents"])
        created_at = datetime.now(timezone.utc).isoformat()
        settlement_id = f"stl_{uuid.uuid4().hex[:12]}"

        entitlement_sha256 = _sha256_canonical(
            {
                "buyer_tenant_id": clean_tenant,
                "license_spdx": license_spdx,
                "manifest_sha256": manifest_sha,
                "package_id": clean_pkg_id,
                "package_version": pkg_version,
            }
        )
        receipt_sha256 = _sha256_canonical(
            {
                "buyer_tenant_id": clean_tenant,
                "created_at": created_at,
                "creator_payout_cents": split["creator_payout_cents"],
                "entitlement_sha256": entitlement_sha256,
                "gross_cents": split["gross_cents"],
                "license_spdx": license_spdx,
                "package_id": clean_pkg_id,
                "package_version": pkg_version,
                "platform_fee_cents": split["platform_fee_cents"],
                "publisher_tier": split["publisher_tier"],
                "settlement_id": settlement_id,
                "split_label": split["split_label"],
            }
        )

        record = SettlementRecord(
            settlement_id=settlement_id,
            package_id=clean_pkg_id,
            package_version=pkg_version,
            buyer_tenant_id=clean_tenant,
            publisher_tier=split["publisher_tier"],
            gross_cents=split["gross_cents"],
            creator_payout_cents=split["creator_payout_cents"],
            platform_fee_cents=split["platform_fee_cents"],
            gross_usd=split["gross_usd"],
            creator_payout_usd=split["creator_payout_usd"],
            platform_fee_usd=split["platform_fee_usd"],
            split_label=split["split_label"],
            license_spdx=license_spdx,
            entitlement_sha256=entitlement_sha256,
            receipt_sha256=receipt_sha256,
            created_at=created_at,
        )

        target_ws = str(workspace_id or clean_tenant).strip() or "default"
        install_cfg = {
            **dict(config or {}),
            "settlement_id": settlement_id,
            "buyer_tenant_id": clean_tenant,
            "entitlement_sha256": entitlement_sha256,
        }
        active_registry.install_package(
            package_id=clean_pkg_id,
            workspace_id=target_ws,
            config=install_cfg,
        )

        active_store = self.store if self.store is not None else getattr(active_registry, "store", None)
        with self._lock:
            self._records[settlement_id] = record
            if active_store is not None:
                active_store.upsert_settlement(
                    settlement_id=settlement_id,
                    package_id=clean_pkg_id,
                    buyer_tenant_id=clean_tenant,
                    payload=record.to_dict(),
                    created_at=created_at,
                )
        return record

    record_purchase = purchase_package

    def list_settlements(self, tenant_id: Optional[str] = None) -> List[SettlementRecord]:
        clean_tid = str(tenant_id).strip() if tenant_id is not None and str(tenant_id).strip() else None
        with self._lock:
            items = list(self._records.values())
        if clean_tid is not None:
            items = [r for r in items if r.buyer_tenant_id == clean_tid]
        return items

    def summarize_settlements(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        items = self.list_settlements(tenant_id=tenant_id)
        gross_cents = sum(r.gross_cents for r in items)
        creator_cents = sum(r.creator_payout_cents for r in items)
        platform_cents = sum(r.platform_fee_cents for r in items)
        return {
            "settlements": [r.to_dict() for r in items],
            "totals": {
                "count": len(items),
                "gross_cents": gross_cents,
                "creator_payout_cents": creator_cents,
                "platform_fee_cents": platform_cents,
                "gross_usd": _cents_to_usd(gross_cents),
                "creator_payout_usd": _cents_to_usd(creator_cents),
                "platform_fee_usd": _cents_to_usd(platform_cents),
            },
        }

    @staticmethod
    def verify_receipt(record: Union[SettlementRecord, Dict[str, Any]]) -> bool:
        rec = record if isinstance(record, SettlementRecord) else SettlementRecord.from_dict(record)
        if rec.creator_payout_cents + rec.platform_fee_cents != rec.gross_cents:
            return False
        expected = _sha256_canonical(
            {
                "buyer_tenant_id": rec.buyer_tenant_id,
                "created_at": rec.created_at,
                "creator_payout_cents": rec.creator_payout_cents,
                "entitlement_sha256": rec.entitlement_sha256,
                "gross_cents": rec.gross_cents,
                "license_spdx": rec.license_spdx,
                "package_id": rec.package_id,
                "package_version": rec.package_version,
                "platform_fee_cents": rec.platform_fee_cents,
                "publisher_tier": rec.publisher_tier,
                "settlement_id": rec.settlement_id,
                "split_label": rec.split_label,
            }
        )
        return expected == rec.receipt_sha256


marketplace_settlement_ledger = MarketplaceSettlementLedger()
