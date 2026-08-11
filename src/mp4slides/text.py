from __future__ import annotations

import re


TRANSCRIPT_NEWLINE_MODES = {"preserve", "space", "paragraph"}


def normalize_transcript_text(text: str, mode: str = "preserve") -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    if mode == "preserve":
        return normalized

    if mode == "space":
        return re.sub(r"[ \t]*\n[ \t]*", " ", normalized).strip()

    if mode == "paragraph":
        paragraphs = re.split(r"\n[ \t]*\n+", normalized)
        compacted = []
        for paragraph in paragraphs:
            value = re.sub(r"[ \t]*\n[ \t]*", " ", paragraph).strip()
            if value:
                compacted.append(value)
        return "\n\n".join(compacted)

    raise ValueError(f"Unsupported transcript newline mode: {mode}")
