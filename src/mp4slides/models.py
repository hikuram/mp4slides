from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def validate(self, name: str = "rect") -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(v < 0.0 or v > 1.0 for v in values):
            raise ValueError(f"{name} values must be within [0, 1]")
        if self.width <= 0.0 or self.height <= 0.0:
            raise ValueError(f"{name} width and height must be positive")
        if self.x + self.width > 1.0 + 1e-9:
            raise ValueError(f"{name} exceeds frame width")
        if self.y + self.height > 1.0 + 1e-9:
            raise ValueError(f"{name} exceeds frame height")

    @classmethod
    def from_sequence(cls, values: list[float] | tuple[float, ...]) -> "Rect":
        if len(values) != 4:
            raise ValueError("Rectangle requires x,y,width,height")
        rect = cls(*(float(v) for v in values))
        rect.validate()
        return rect

    def as_list(self) -> list[float]:
        return [self.x, self.y, self.width, self.height]


@dataclass
class TranscriptWord:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[TranscriptWord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
        }


@dataclass
class DetectedSlide:
    start: float
    end: float
    representative_time: float
    image_bytes: bytes
    analysis_gray: Any
    analysis_edges: Any
    merged_count: int = 1
    trigger_score: float | None = None
    image_path: str | None = None
    transcript: str = ""

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class DetectionScore:
    time: float
    frame_delta: float
    reference_delta: float
    state: str
    event: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "time": f"{self.time:.6f}",
            "frame_delta": f"{self.frame_delta:.8f}",
            "reference_delta": f"{self.reference_delta:.8f}",
            "state": self.state,
            "event": self.event,
        }
