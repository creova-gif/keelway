"""
Multi-Agent Git Conflict Detection & Autonomous Resolution Engine for KSpaces.
Provides deterministic 3-way merge analysis, hunk classification, non-overlapping auto-resolution,
and conflict marker synthesis.
"""

from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ConflictHunk:
    """A localized diff region in a 3-way merge."""
    file_path: str
    base_content: str
    left_content: str
    right_content: str
    is_clean: bool
    resolved_content: Optional[str]
    conflict_type: str  # "clean", "non_overlapping_addition", "overlapping_mutation"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConflictReport:
    """Comprehensive report of 3-way merge analysis across a file or changes."""
    has_conflicts: bool
    conflict_files: List[str]
    hunks: List[ConflictHunk]
    auto_resolvable: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["hunks"] = [h.to_dict() if hasattr(h, "to_dict") else h for h in self.hunks]
        return data


def _spans_overlap(l1: int, l2: int, r1: int, r2: int) -> bool:
    """Determine whether two base line index spans [l1, l2) and [r1, r2) intersect."""
    if l1 == l2 and r1 == r2:
        return l1 == r1
    if l1 == l2:
        return r1 <= l1 <= r2
    if r1 == r2:
        return l1 <= r1 <= l2
    return max(l1, r1) < min(l2, r2)


def _get_side_content(
    base_lines: List[str],
    other_lines: List[str],
    start: int,
    end: int,
    ops: List[Tuple[str, int, int, int, int]],
) -> str:
    """Reconstruct side lines corresponding to base slice [start, end)."""
    if not ops:
        return "".join(base_lines[start:end])
    res: List[str] = []
    curr = start
    for _tag, i1, i2, j1, j2 in sorted(ops, key=lambda o: (o[1], o[2])):
        if i1 > curr:
            res.append("".join(base_lines[curr:i1]))
        res.append("".join(other_lines[j1:j2]))
        curr = max(curr, i2)
    if curr < end:
        res.append("".join(base_lines[curr:end]))
    return "".join(res)


class ConflictDetector:
    """Autonomous 3-way git conflict detector and resolution engine."""

    @classmethod
    def detect_3way(
        cls,
        base_text: str,
        left_text: str,
        right_text: str,
        file_path: str = "",
    ) -> ConflictReport:
        """
        Performs deterministic line-by-line 3-way merge analysis.
        - If only left modified: clean merge (takes left).
        - If only right modified: clean merge (takes right).
        - If both made identical changes: clean merge.
        - If both made non-overlapping additions/modifications: automatically synthesizes
          non-conflicting merged text with auto_resolvable = True.
        - If overlapping modifications touch identical lines with different text:
          marks has_conflicts = True, auto_resolvable = False, and generates conflict markers.
        """
        base_lines = base_text.splitlines(keepends=True)
        left_lines = left_text.splitlines(keepends=True)
        right_lines = right_text.splitlines(keepends=True)

        # 1. Trivial clean cases
        if left_text == right_text:
            hunk = ConflictHunk(
                file_path=file_path,
                base_content=base_text,
                left_content=left_text,
                right_content=right_text,
                is_clean=True,
                resolved_content=left_text,
                conflict_type="clean",
            )
            return ConflictReport(
                has_conflicts=False,
                conflict_files=[],
                hunks=[hunk],
                auto_resolvable=True,
                summary="Clean 3-way merge: both branches identical.",
            )

        if left_text == base_text:
            hunk = ConflictHunk(
                file_path=file_path,
                base_content=base_text,
                left_content=left_text,
                right_content=right_text,
                is_clean=True,
                resolved_content=right_text,
                conflict_type="clean",
            )
            return ConflictReport(
                has_conflicts=False,
                conflict_files=[],
                hunks=[hunk],
                auto_resolvable=True,
                summary="Clean 3-way merge: only right branch modified.",
            )

        if right_text == base_text:
            hunk = ConflictHunk(
                file_path=file_path,
                base_content=base_text,
                left_content=left_text,
                right_content=right_text,
                is_clean=True,
                resolved_content=left_text,
                conflict_type="clean",
            )
            return ConflictReport(
                has_conflicts=False,
                conflict_files=[],
                hunks=[hunk],
                auto_resolvable=True,
                summary="Clean 3-way merge: only left branch modified.",
            )

        # 2. Detailed opcode alignment
        sm_l = difflib.SequenceMatcher(None, base_lines, left_lines)
        sm_r = difflib.SequenceMatcher(None, base_lines, right_lines)

        l_ops = [op for op in sm_l.get_opcodes() if op[0] != "equal"]
        r_ops = [op for op in sm_r.get_opcodes() if op[0] != "equal"]

        # Group operations into clusters along base spans
        clusters: List[Dict[str, Any]] = []
        for op in l_ops:
            clusters.append({"span": [op[1], op[2]], "left_ops": [op], "right_ops": []})
        for op in r_ops:
            clusters.append({"span": [op[1], op[2]], "left_ops": [], "right_ops": [op]})

        # Iteratively merge overlapping clusters
        merged = True
        while merged:
            merged = False
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    ca, cb = clusters[i], clusters[j]
                    if _spans_overlap(ca["span"][0], ca["span"][1], cb["span"][0], cb["span"][1]):
                        ca["span"][0] = min(ca["span"][0], cb["span"][0])
                        ca["span"][1] = max(ca["span"][1], cb["span"][1])
                        ca["left_ops"].extend(cb["left_ops"])
                        ca["right_ops"].extend(cb["right_ops"])
                        clusters.pop(j)
                        merged = True
                        break
                if merged:
                    break

        clusters.sort(key=lambda c: (c["span"][0], c["span"][1]))

        hunks: List[ConflictHunk] = []
        has_overlapping_conflict = False

        for c in clusters:
            start, end = c["span"]
            base_content = "".join(base_lines[start:end])
            left_content = _get_side_content(base_lines, left_lines, start, end, c["left_ops"])
            right_content = _get_side_content(base_lines, right_lines, start, end, c["right_ops"])

            # Classification
            if left_content == right_content:
                # Both modified to identical content
                hunk = ConflictHunk(
                    file_path=file_path,
                    base_content=base_content,
                    left_content=left_content,
                    right_content=right_content,
                    is_clean=True,
                    resolved_content=left_content,
                    conflict_type="clean",
                )
            elif not c["left_ops"] and c["right_ops"]:
                # Only right modified this region
                hunk = ConflictHunk(
                    file_path=file_path,
                    base_content=base_content,
                    left_content=left_content,
                    right_content=right_content,
                    is_clean=True,
                    resolved_content=right_content,
                    conflict_type="non_overlapping_addition",
                )
            elif c["left_ops"] and not c["right_ops"]:
                # Only left modified this region
                hunk = ConflictHunk(
                    file_path=file_path,
                    base_content=base_content,
                    left_content=left_content,
                    right_content=right_content,
                    is_clean=True,
                    resolved_content=left_content,
                    conflict_type="non_overlapping_addition",
                )
            else:
                # Both modified with different content -> overlapping mutation
                has_overlapping_conflict = True
                hunk = ConflictHunk(
                    file_path=file_path,
                    base_content=base_content,
                    left_content=left_content,
                    right_content=right_content,
                    is_clean=False,
                    resolved_content=cls.resolve_hunk(
                        ConflictHunk(
                            file_path=file_path,
                            base_content=base_content,
                            left_content=left_content,
                            right_content=right_content,
                            is_clean=False,
                            resolved_content=None,
                            conflict_type="overlapping_mutation",
                        ),
                        strategy="auto",
                    ),
                    conflict_type="overlapping_mutation",
                )
            hunks.append(hunk)

        auto_resolvable = not has_overlapping_conflict
        conflict_files = [file_path] if (has_overlapping_conflict and file_path) else (
            ["conflicted_file"] if has_overlapping_conflict else []
        )

        if not has_overlapping_conflict:
            summary = (
                f"Auto-resolved {len(hunks)} non-overlapping hunk(s) across branches."
                if hunks
                else "Clean 3-way merge."
            )
        else:
            overlapping_count = sum(1 for h in hunks if not h.is_clean)
            summary = f"Detected {overlapping_count} overlapping conflict hunk(s) requiring resolution."

        return ConflictReport(
            has_conflicts=has_overlapping_conflict,
            conflict_files=conflict_files,
            hunks=hunks,
            auto_resolvable=auto_resolvable,
            summary=summary,
        )

    @classmethod
    def resolve_hunk(cls, hunk: ConflictHunk, strategy: str = "auto") -> str:
        """
        Resolves a single ConflictHunk according to the chosen strategy:
        - 'left': takes left_content
        - 'right': takes right_content
        - 'base': takes base_content
        - 'auto': returns clean resolved_content if non-overlapping or identical,
                  otherwise emits standard conflict markers.
        """
        strat = (strategy or "auto").strip().lower()
        if strat == "left":
            return hunk.left_content
        elif strat == "right":
            return hunk.right_content
        elif strat == "base":
            return hunk.base_content
        elif strat == "auto":
            if hunk.is_clean and hunk.resolved_content is not None:
                return hunk.resolved_content
            if hunk.left_content == hunk.right_content:
                return hunk.left_content
            if hunk.left_content == hunk.base_content:
                return hunk.right_content
            if hunk.right_content == hunk.base_content:
                return hunk.left_content

            # Format conflict markers
            l_str = hunk.left_content
            r_str = hunk.right_content
            if l_str and not l_str.endswith("\n"):
                l_str += "\n"
            if r_str and not r_str.endswith("\n"):
                r_str += "\n"
            return f"<<<<<<< LEFT\n{l_str}=======\n{r_str}>>>>>>> RIGHT\n"
        else:
            raise ValueError(f"Unknown resolution strategy '{strategy}'. Supported: auto, left, right, base.")

    @classmethod
    def resolve_3way(
        cls,
        base_text: str,
        left_text: str,
        right_text: str,
        strategy: str = "auto",
        file_path: str = "",
    ) -> str:
        """
        Synthesizes the complete merged text for a 3-way merge using the given strategy.
        """
        strat = (strategy or "auto").strip().lower()
        if strat == "left":
            return left_text
        if strat == "right":
            return right_text
        if strat == "base":
            return base_text

        report = cls.detect_3way(base_text, left_text, right_text, file_path=file_path)
        if not report.hunks:
            return base_text

        # If there's only 1 hunk covering the entire text
        if len(report.hunks) == 1 and report.hunks[0].base_content == base_text:
            return cls.resolve_hunk(report.hunks[0], strategy=strat)

        base_lines = base_text.splitlines(keepends=True)
        left_lines = left_text.splitlines(keepends=True)
        right_lines = right_text.splitlines(keepends=True)

        sm_l = difflib.SequenceMatcher(None, base_lines, left_lines)
        sm_r = difflib.SequenceMatcher(None, base_lines, right_lines)

        l_ops = [op for op in sm_l.get_opcodes() if op[0] != "equal"]
        r_ops = [op for op in sm_r.get_opcodes() if op[0] != "equal"]

        clusters: List[Dict[str, Any]] = []
        for op in l_ops:
            clusters.append({"span": [op[1], op[2]], "left_ops": [op], "right_ops": []})
        for op in r_ops:
            clusters.append({"span": [op[1], op[2]], "left_ops": [], "right_ops": [op]})

        merged = True
        while merged:
            merged = False
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    ca, cb = clusters[i], clusters[j]
                    if _spans_overlap(ca["span"][0], ca["span"][1], cb["span"][0], cb["span"][1]):
                        ca["span"][0] = min(ca["span"][0], cb["span"][0])
                        ca["span"][1] = max(ca["span"][1], cb["span"][1])
                        ca["left_ops"].extend(cb["left_ops"])
                        ca["right_ops"].extend(cb["right_ops"])
                        clusters.pop(j)
                        merged = True
                        break
                if merged:
                    break

        clusters.sort(key=lambda c: (c["span"][0], c["span"][1]))

        out: List[str] = []
        curr = 0
        hunk_idx = 0
        for c in clusters:
            start, end = c["span"]
            if start > curr:
                out.append("".join(base_lines[curr:start]))

            if hunk_idx < len(report.hunks):
                hunk = report.hunks[hunk_idx]
                out.append(cls.resolve_hunk(hunk, strategy=strat))
                hunk_idx += 1

            curr = max(curr, end)

        if curr < len(base_lines):
            out.append("".join(base_lines[curr:]))

        return "".join(out)
