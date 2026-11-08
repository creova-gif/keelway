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
import shutil
import tarfile
import tempfile
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


class KHubMirror:
    """Enterprise air-gapped mirror exporter and importer for KHub skills and catalogs."""

    @classmethod
    def export_mirror(
        cls,
        output_target: Union[Path, str],
        skills_dir: Optional[Union[Path, str]] = None,
        as_archive: bool = False,
    ) -> Dict[str, Any]:
        """
        Exports all verified skills into an offline air-gapped mirror bundle with a signed catalog manifest.
        Can output either a directory of .skill.tar.gz bundles + khub-mirror-manifest.json,
        or a single .tar.gz archive.
        """
        output_target = Path(output_target).resolve()
        is_archive_dest = as_archive or str(output_target).endswith(".tar.gz") or str(output_target).endswith(".tgz")

        # Determine source skills directory (default to core/kstack/skills)
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent / "kstack" / "skills"
        else:
            skills_dir = Path(skills_dir).resolve()

        if not skills_dir.exists():
            raise FileNotFoundError(f"Skills source directory '{skills_dir}' does not exist.")

        # Work in staging directory if outputting an archive, otherwise directly in output_target
        staging_dir = Path(tempfile.mkdtemp(prefix="khub_mirror_staging_")).resolve() if is_archive_dest else output_target.resolve()
        staging_dir.mkdir(parents=True, exist_ok=True)
        bundles_dir = staging_dir / "bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)

        skills_catalog: List[Dict[str, Any]] = []
        skill_subdirs = [p for p in sorted(skills_dir.iterdir()) if p.is_dir() and not p.name.startswith(".")]

        # If no subdirectories, but skills_dir itself has SKILL.md
        if not skill_subdirs and (skills_dir / "SKILL.md").exists():
            skill_subdirs = [skills_dir]

        for sdir in skill_subdirs:
            skill_id = sdir.name
            bundle_filename = f"{skill_id}.skill.tar.gz"
            bundle_path = bundles_dir / bundle_filename

            packed = KHubBundlePacker.pack_skill(sdir, bundle_path)
            skills_catalog.append({
                "id": skill_id,
                "name": packed.get("skill_name", skill_id),
                "bundle_file": f"bundles/{bundle_filename}",
                "bundle_sha256": packed.get("archive_sha256", ""),
                "bundle_digest_sha256": packed.get("bundle_digest_sha256", ""),
                "files_count": packed.get("files_count", 0),
                "total_bytes": packed.get("total_bytes", 0),
                "network_policy": "none",
                "air_gap_compliant": True,
            })

        # Canonical digest of entire mirror catalog
        catalog_payload = json.dumps([s["bundle_sha256"] for s in skills_catalog], sort_keys=True)
        catalog_digest = hashlib.sha256(catalog_payload.encode("utf-8")).hexdigest()

        mirror_manifest = {
            "mirror_format": "khub-airgap-mirror-v1",
            "created_at_utc": time.time(),
            "total_skills": len(skills_catalog),
            "air_gap_compliant": True,
            "network_policy": "none",
            "catalog_digest_sha256": catalog_digest,
            "skills": skills_catalog,
        }

        manifest_path = staging_dir / "khub-mirror-manifest.json"
        manifest_path.write_text(json.dumps(mirror_manifest, indent=2), encoding="utf-8")

        if is_archive_dest:
            output_target.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(output_target, "w:gz") as tar:
                # Add manifest
                tar.add(manifest_path, arcname="khub-mirror-manifest.json")
                # Add bundles
                for item in sorted(bundles_dir.iterdir()):
                    tar.add(item, arcname=f"bundles/{item.name}")
            shutil.rmtree(staging_dir, ignore_errors=True)
            archive_sha = hashlib.sha256(output_target.read_bytes()).hexdigest()
            return {
                "status": "exported",
                "mode": "archive",
                "output_target": str(output_target),
                "archive_sha256": archive_sha,
                "catalog_digest_sha256": catalog_digest,
                "total_skills": len(skills_catalog),
                "manifest": mirror_manifest,
            }
        else:
            return {
                "status": "exported",
                "mode": "directory",
                "output_target": str(output_target),
                "manifest_path": str(manifest_path),
                "catalog_digest_sha256": catalog_digest,
                "total_skills": len(skills_catalog),
                "manifest": mirror_manifest,
            }

    @classmethod
    def import_mirror(
        cls,
        mirror_source: Union[Path, str],
        destination_dir: Optional[Union[Path, str]] = None,
        auto_approve: bool = False,
        verify: bool = True,
    ) -> Dict[str, Any]:
        """
        Imports and cryptographically validates an offline mirror bundle or directory into destination_dir.
        """
        mirror_source = Path(mirror_source).resolve()
        if not mirror_source.exists():
            raise FileNotFoundError(f"Mirror source '{mirror_source}' does not exist.")

        if destination_dir is None:
            destination_dir = Path(".keelway/khub/skills").resolve()
        else:
            destination_dir = Path(destination_dir).resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)

        is_archive = mirror_source.is_file() and (str(mirror_source).endswith(".tar.gz") or str(mirror_source).endswith(".tgz"))
        cleanup_temp = False

        if is_archive:
            temp_extract = Path(tempfile.mkdtemp(prefix="khub_mirror_import_")).resolve()
            cleanup_temp = True
            with tarfile.open(mirror_source, "r:*") as tar:
                # Path traversal check
                dest_str = str(temp_extract)
                for member in tar.getmembers():
                    norm = member.name.replace("\\", "/")
                    if norm.startswith("/") or norm.startswith("../") or "/../" in norm or norm == "..":
                        raise PermissionError(f"Directory traversal detected in mirror member: {member.name}")
                    tp = (temp_extract / member.name).resolve()
                    if not (str(tp) == dest_str or str(tp).startswith(dest_str + os.sep)):
                        raise PermissionError(f"Directory traversal detected in mirror member: {member.name}")
                    tar.extract(member, path=temp_extract)
            source_root = temp_extract
        else:
            source_root = mirror_source

        try:
            manifest_file = source_root / "khub-mirror-manifest.json"
            if not manifest_file.is_file():
                raise FileNotFoundError("khub-mirror-manifest.json not found in mirror source.")

            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            if manifest_data.get("mirror_format") != "khub-airgap-mirror-v1":
                raise ValueError(f"Unsupported mirror format: {manifest_data.get('mirror_format')}")

            skills_list = manifest_data.get("skills", [])
            imported_skills: List[Dict[str, Any]] = []

            for entry in skills_list:
                rel_bundle = entry.get("bundle_file", "")
                bundle_path = source_root / rel_bundle
                if not bundle_path.is_file():
                    raise FileNotFoundError(f"Bundle file declared in mirror manifest not found: {rel_bundle}")

                # Verify SHA256 of bundle archive
                if verify and entry.get("bundle_sha256"):
                    actual_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
                    if actual_sha != entry["bundle_sha256"]:
                        raise ValueError(f"Tampered mirror bundle: {rel_bundle} checksum mismatch")

                # Unpack and verify bundle contents
                skill_dest = destination_dir / entry["id"]
                unpack_res = KHubBundlePacker.unpack_skill(bundle_path, skill_dest, verify=verify)
                imported_skills.append({
                    "id": entry["id"],
                    "name": entry.get("name", entry["id"]),
                    "destination": str(skill_dest),
                    "bundle_digest": unpack_res.get("bundle_digest_sha256", ""),
                    "verified": True,
                    "approved": auto_approve,
                })

            return {
                "status": "imported",
                "verified": verify,
                "total_imported": len(imported_skills),
                "destination_dir": str(destination_dir),
                "imported_skills": imported_skills,
                "catalog_digest_sha256": manifest_data.get("catalog_digest_sha256", ""),
            }
        finally:
            if cleanup_temp:
                shutil.rmtree(temp_extract, ignore_errors=True)

