"""
KHub Universal Skill Bundle Packaging & Synchronization.
Allows packing portable skill collections into cryptographically verified .skill.tar.gz archives.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class KHubBundlePacker:
    """Packer and unpacker for portable, verified KHub universal skill bundles."""

    @classmethod
    def pack_skill(
        cls,
        skill_path: Union[Path, str],
        output_archive: Union[Path, str],
    ) -> Dict[str, Any]:
        """
        Packs a skill directory or SKILL.md and accompanying files into a .skill.tar.gz bundle.
        Computes SHA-256 member digests, verifies directory traversal safety, and writes skill_manifest.json.
        """
        skill_path = Path(skill_path).resolve()
        output_archive = Path(output_archive).resolve()

        if not skill_path.exists():
            raise FileNotFoundError(f"Skill path '{skill_path}' does not exist.")

        output_archive.parent.mkdir(parents=True, exist_ok=True)

        file_digests: Dict[str, str] = {}
        files_to_pack: List[Tuple[str, Path]] = []

        if skill_path.is_file():
            # Packing a single skill file
            content_bytes = skill_path.read_bytes()
            digest = hashlib.sha256(content_bytes).hexdigest()
            skill_name = skill_path.stem

            # Always ensure SKILL.md is present in the archive
            if skill_path.name.lower() == "skill.md":
                rel_name = "SKILL.md"
                file_digests[rel_name] = digest
                files_to_pack.append((rel_name, skill_path))
            else:
                rel_name = skill_path.name
                file_digests[rel_name] = digest
                files_to_pack.append((rel_name, skill_path))
                # Also include as SKILL.md if not already named that
                file_digests["SKILL.md"] = digest
                files_to_pack.append(("SKILL.md", skill_path))
        else:
            # Packing a directory
            skill_name = skill_path.name
            ignored_suffixes = (".pyc", ".tar.gz", ".skill.tar.gz", ".DS_Store")
            ignored_names = {"skill_manifest.json", ".git"}

            for root, _, files in os.walk(skill_path):
                for file in sorted(files):
                    if file in ignored_names or any(file.endswith(sfx) for sfx in ignored_suffixes):
                        continue

                    fpath = Path(root) / file

                    # Skip output archive if it's placed inside source dir
                    if fpath == output_archive:
                        continue

                    rel = str(fpath.relative_to(skill_path)).replace("\\", "/")

                    # Traversal safety verification
                    if rel.startswith("/") or rel.startswith("../") or "/../" in rel:
                        raise PermissionError(f"Directory traversal detected in member path: {rel}")

                    digest = hashlib.sha256(fpath.read_bytes()).hexdigest()
                    file_digests[rel] = digest
                    files_to_pack.append((rel, fpath))

        if not file_digests:
            raise ValueError(f"No packable skill files found in '{skill_path}'.")

        # Try to infer skill name from SKILL.md if present
        for rel_name, fpath in files_to_pack:
            if rel_name == "SKILL.md":
                try:
                    first_line = fpath.read_text(encoding="utf-8").strip().splitlines()[0]
                    if first_line.startswith("#"):
                        extracted_title = first_line.lstrip("#").strip()
                        if extracted_title:
                            skill_name = extracted_title
                except Exception:
                    pass
                break

        canonical_payload = json.dumps(file_digests, sort_keys=True)
        bundle_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        total_bytes = sum(fpath.stat().st_size for _, fpath in files_to_pack)

        manifest: Dict[str, Any] = {
            "bundle_format": "khub-skill-bundle-v1",
            "skill_name": skill_name,
            "created_at_utc": time.time(),
            "files": file_digests,
            "files_count": len(file_digests),
            "total_bytes": total_bytes,
            "bundle_digest_sha256": bundle_digest,
            "version": "1.0.0",
        }

        # Write to gzip tar archive
        with tarfile.open(output_archive, "w:gz") as tar:
            # 1. Add skill_manifest.json first
            manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
            ti = tarfile.TarInfo(name="skill_manifest.json")
            ti.size = len(manifest_bytes)
            ti.mtime = int(time.time())
            tar.addfile(ti, io.BytesIO(manifest_bytes))

            # 2. Add each file
            seen_arcs = set()
            for arcname, fpath in files_to_pack:
                if arcname in seen_arcs:
                    continue
                seen_arcs.add(arcname)
                tar.add(fpath, arcname=arcname)

        archive_sha = hashlib.sha256(output_archive.read_bytes()).hexdigest()

        result = dict(manifest)
        result.update({
            "status": "packed",
            "archive_path": str(output_archive),
            "archive_sha256": archive_sha,
            "manifest": manifest,
        })
        return result

    @classmethod
    def unpack_skill(
        cls,
        archive_path: Union[Path, str],
        destination_dir: Union[Path, str],
        verify: bool = True,
    ) -> Dict[str, Any]:
        """
        Unpacks a .skill.tar.gz bundle, verifies member digests against skill_manifest.json,
        and detects tampering or path traversals.
        """
        archive_path = Path(archive_path).resolve()
        destination_dir = Path(destination_dir).resolve()

        if not archive_path.is_file():
            raise FileNotFoundError(f"Skill bundle archive '{archive_path}' does not exist.")

        destination_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(archive_path, "r:*") as tar:
            # 1. Directory traversal detection across all members
            dest_str = str(destination_dir)
            for member in tar.getmembers():
                norm_name = member.name.replace("\\", "/")
                if norm_name.startswith("/") or norm_name.startswith("../") or "/../" in norm_name or norm_name == "..":
                    raise PermissionError(f"Directory traversal attack detected in tar member: {member.name}")

                target_p = (destination_dir / member.name).resolve()
                try:
                    target_p.relative_to(destination_dir)
                except ValueError:
                    raise PermissionError(f"Directory traversal attack detected in tar member: {member.name}")

                if not (str(target_p) == dest_str or str(target_p).startswith(dest_str + os.sep)):
                    raise PermissionError(f"Directory traversal attack detected in tar member: {member.name}")

            # 2. Extract manifest
            try:
                mf_file = tar.extractfile("skill_manifest.json")
                if not mf_file:
                    raise ValueError("skill_manifest.json not found in archive.")
                manifest: Dict[str, Any] = json.loads(mf_file.read().decode("utf-8"))
            except (KeyError, AttributeError):
                raise ValueError("skill_manifest.json not found in archive.")
            except Exception as e:
                raise ValueError(f"Corrupted or invalid skill_manifest.json: {e}")

            # 3. Extract all files
            for member in tar.getmembers():
                tar.extract(member, path=destination_dir)

        # 4. Digest and tamper verification
        if verify:
            manifest_files: Dict[str, str] = manifest.get("files", {})
            for rel, expected_hash in manifest_files.items():
                fpath = destination_dir / rel
                if not fpath.is_file():
                    raise FileNotFoundError(f"Missing file declared in skill manifest: {rel}")
                actual_hash = hashlib.sha256(fpath.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"Tampered file detected: {rel} (expected {expected_hash}, got {actual_hash})")

            # Validate composite bundle digest
            canonical_payload = json.dumps(manifest_files, sort_keys=True)
            expected_bundle_digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
            if manifest.get("bundle_digest_sha256") and manifest["bundle_digest_sha256"] != expected_bundle_digest:
                raise ValueError("Tampered manifest detected: bundle digest does not match files.")

        return {
            "status": "unpacked",
            "verified": verify,
            "destination_dir": str(destination_dir),
            "unpacked_files": list(manifest.get("files", {}).keys()),
            "skill_name": manifest.get("skill_name", destination_dir.name),
            "bundle_digest_sha256": manifest.get("bundle_digest_sha256", ""),
            "manifest": manifest,
        }

    # Convenience aliases
    pack = pack_skill
    unpack = unpack_skill
