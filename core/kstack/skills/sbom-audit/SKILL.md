---
name: kstack/sbom-audit
version: 1.0.0
role: supply_chain_auditor
description: Generate and inspect the CycloneDX SBOM for dependency inventory, license posture, and supply-chain evidence.
permissions:
  - read
inputs:
  format: SBOM serialization (cyclonedx JSON)
  include_dev: Include development dependencies
outputs:
  sbom: CycloneDX document payload
  component_count: Enumerated dependency count
  licenses: License distribution across components
---

# KStack SBOM Audit Skill (Supply-Chain Auditor Role)

## Overview
Reads `/v1/sbom` — the CycloneDX software bill of materials — to enumerate runtime dependencies, license posture, and supply-chain evidence for release qualification and compliance review.

## Execution Rules
1. The SBOM is generated from the live environment; a stale export is not evidence of current posture.
2. Report `component_count` and license distribution verbatim — a dependency omitted from the count is a finding, not noise.
3. An unknown or unmapped license is flagged, never guessed.
4. SBOM inspection is read-only evidence gathering; vulnerability verdicts belong to the scanner skill, not this one.
