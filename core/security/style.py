"""
Keelway Stylistic Conditioning & Anti-Slop Writing Engine.
Implements Y Combinator RFS 'LLMs That Write Well':
- Filters out corporate RLHF buzzwords, sycophancy, and robotic filler.
- Calibrates authentic tone, active voice, and high-signal communication.
"""

import re
from enum import Enum
from typing import Dict, List, Tuple


class VoiceStyle(str, Enum):
    HUMAN_ENGINEER = "human-engineer"
    EXECUTIVE = "executive"
    CONVERSATIONAL = "conversational"


class StyleEngine:
    """De-slops model output, injects natural voice prompts, and enforces brevity."""

    # Words and phrases characteristic of robotic RLHF training
    AI_SLOP_PATTERNS = [
        re.compile(r"\bdelve(?:s|d|ing)?\s+into\b", re.IGNORECASE),
        re.compile(r"\ba\s+testament\s+to\b", re.IGNORECASE),
        re.compile(r"\ba\s+beacon\s+of\b", re.IGNORECASE),
        re.compile(r"\bcrucial\s+to\s+note\b", re.IGNORECASE),
        re.compile(r"\bit(?:'s|\s+is)\s+important\s+to\s+remember\s+that\b", re.IGNORECASE),
        re.compile(r"\bin\s+conclusion[,\s]", re.IGNORECASE),
        re.compile(r"\bseamlessly\s+integrates?\b", re.IGNORECASE),
        re.compile(r"\bpivotal\s+role\b", re.IGNORECASE),
        re.compile(r"\bharness(?:ing)?\s+the\s+power\s+of\b", re.IGNORECASE),
        re.compile(r"\bgame-changer\b", re.IGNORECASE),
        re.compile(r"\bfosters?\s+a\s+culture\s+of\b", re.IGNORECASE),
    ]

    STYLE_PROMPTS: Dict[VoiceStyle, str] = {
        VoiceStyle.HUMAN_ENGINEER: (
            "Voice Directive: Write like a pragmatic, senior engineer speaking to an engineer peer. "
            "Use active voice, concrete evidence, and zero marketing fluff. Never say 'delve', 'testament', or 'beacon'. "
            "If an answer is uncertain, explicitly state what is missing rather than guessing."
        ),
        VoiceStyle.EXECUTIVE: (
            "Voice Directive: Write with extreme clarity and executive brevity. "
            "Lead with the bottom line. No corporate filler, no preamble, and no unsolicited apologies. "
            "Use bullets only when ordering decisions or ranked risks."
        ),
        VoiceStyle.CONVERSATIONAL: (
            "Voice Directive: Speak with genuine, warm, human cadence. Avoid sterile corporate polish. "
            "Be direct, candid, and articulate. Speak like a thoughtful person in a private conversation."
        ),
    }

    @classmethod
    def get_style_prompt(cls, style: VoiceStyle = VoiceStyle.HUMAN_ENGINEER) -> str:
        return cls.STYLE_PROMPTS.get(style, cls.STYLE_PROMPTS[VoiceStyle.HUMAN_ENGINEER])

    @classmethod
    def de_slop(cls, text: str) -> Tuple[str, List[str]]:
        """Scans and cleans text from formulaic AI slop patterns."""
        cleaned = text
        removed_slop = []

        for pattern in cls.AI_SLOP_PATTERNS:
            matches = pattern.findall(cleaned)
            if matches:
                removed_slop.extend(matches)
                # Replace with direct alternative or clean punctuation
                cleaned = pattern.sub("", cleaned)

        # Clean up double spaces created by removals
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip(), removed_slop
