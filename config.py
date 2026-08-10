from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .models import Rect


@dataclass(frozen=True)
class VideoConfig:
    sample_fps: float = 3.0


@dataclass(frozen=True)
class RoiConfig:
    rect: Rect = field(default_factory=lambda: Rect(0.0, 0.0, 1.0, 1.0))
    ignore: tuple[Rect, ...] = ()


@dataclass(frozen=True)
class DetectionConfig:
    resize_width: int = 640
    gaussian_kernel: int = 5
    threshold_high: float = 0.030
    threshold_low: float = 0.010
    reference_threshold: float = 0.025
    stable_seconds: float = 1.5
    merge_threshold: float = 0.018
    min_slide_seconds: float = 1.0
    pixel_weight: float = 0.80
    edge_weight: float = 0.20
    canny_low: int = 60
    canny_high: int = 160
    png_compression: int = 3


@dataclass(frozen=True)
class WhisperConfig:
    enabled: bool = True
    model: str = "large-v3"
    language: str | None = "ja"
    device: str = "cuda"
    compute_type: str = "float16"
    beam_size: int = 5
    vad_filter: bool = True
    word_timestamps: bool = False
    condition_on_previous_text: bool = True


@dataclass(frozen=True)
class OutputConfig:
    format: str = "pptx"
    image_region: str = "roi"
    keep_intermediate: bool = True
    save_debug_scores: bool = True
    slide_width_in: float = 13.333333
    slide_height_in: float = 7.5
    pdf_transcript_mode: str = "below"
    pdf_transcript_ratio: float = 0.22
    pdf_font_path: str | None = None


@dataclass(frozen=True)
class AppConfig:
    video: VideoConfig = field(default_factory=VideoConfig)
    roi: RoiConfig = field(default_factory=RoiConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    def validate(self) -> None:
        self.roi.rect.validate("roi")
        for idx, rect in enumerate(self.roi.ignore):
            rect.validate(f"roi.ignore[{idx}]")
        if self.video.sample_fps <= 0:
            raise ValueError("video.sample_fps must be positive")
        if self.detection.resize_width < 64:
            raise ValueError("detection.resize_width must be at least 64")
        kernel = self.detection.gaussian_kernel
        if kernel < 1 or kernel % 2 == 0:
            raise ValueError("detection.gaussian_kernel must be a positive odd integer")
        if not 0 <= self.detection.threshold_low < self.detection.threshold_high <= 1:
            raise ValueError("thresholds must satisfy 0 <= low < high <= 1")
        if not 0 <= self.detection.reference_threshold <= 1:
            raise ValueError("detection.reference_threshold must be within [0, 1]")
        if not 0 <= self.detection.merge_threshold <= 1:
            raise ValueError("detection.merge_threshold must be within [0, 1]")
        if self.detection.stable_seconds < 0:
            raise ValueError("detection.stable_seconds must be non-negative")
        if self.detection.min_slide_seconds < 0:
            raise ValueError("detection.min_slide_seconds must be non-negative")
        if self.detection.pixel_weight < 0 or self.detection.edge_weight < 0:
            raise ValueError("detection weights must be non-negative")
        if self.detection.pixel_weight + self.detection.edge_weight <= 0:
            raise ValueError("at least one detection weight must be positive")
        if not 0 <= self.detection.png_compression <= 9:
            raise ValueError("detection.png_compression must be within [0, 9]")
        if self.output.format not in {"pptx", "pdf", "both"}:
            raise ValueError("output.format must be pptx, pdf, or both")
        if self.output.image_region not in {"roi", "full"}:
            raise ValueError("output.image_region must be roi or full")
        if self.output.pdf_transcript_mode not in {"below", "notes-page", "none"}:
            raise ValueError("output.pdf_transcript_mode is invalid")
        if not 0.05 <= self.output.pdf_transcript_ratio <= 0.60:
            raise ValueError("output.pdf_transcript_ratio must be within [0.05, 0.60]")


def _mapping(data: Any, key: str) -> dict[str, Any]:
    value = data.get(key, {}) if isinstance(data, dict) else {}
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _rect_from_roi(data: dict[str, Any]) -> Rect:
    return Rect(
        float(data.get("x", 0.0)),
        float(data.get("y", 0.0)),
        float(data.get("width", 1.0)),
        float(data.get("height", 1.0)),
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    data: dict[str, Any] = {}
    if path is not None:
        with Path(path).open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Configuration root must be a mapping")
        data = loaded

    video_data = _mapping(data, "video")
    roi_data = _mapping(data, "roi")
    detection_data = _mapping(data, "detection")
    whisper_data = _mapping(data, "whisper")
    output_data = _mapping(data, "output")

    ignore_items = roi_data.get("ignore", []) or []
    if not isinstance(ignore_items, list):
        raise ValueError("roi.ignore must be a list")

    config = AppConfig(
        video=VideoConfig(**video_data),
        roi=RoiConfig(
            rect=_rect_from_roi(roi_data),
            ignore=tuple(Rect.from_sequence(item) for item in ignore_items),
        ),
        detection=DetectionConfig(**detection_data),
        whisper=WhisperConfig(**whisper_data),
        output=OutputConfig(**output_data),
    )
    config.validate()
    return config


def apply_overrides(config: AppConfig, **overrides: Any) -> AppConfig:
    video = config.video
    roi = config.roi
    detection = config.detection
    whisper = config.whisper
    output = config.output

    if overrides.get("sample_fps") is not None:
        video = replace(video, sample_fps=float(overrides["sample_fps"]))
    if overrides.get("roi") is not None:
        roi = replace(roi, rect=Rect.from_sequence(overrides["roi"]))
    if overrides.get("ignore"):
        roi = replace(roi, ignore=tuple(Rect.from_sequence(item) for item in overrides["ignore"]))
    for key in ("stable_seconds", "merge_threshold", "threshold_high", "threshold_low", "reference_threshold"):
        if overrides.get(key) is not None:
            detection = replace(detection, **{key: float(overrides[key])})
    for key in ("model", "language", "device", "compute_type"):
        if overrides.get(key) is not None:
            whisper = replace(whisper, **{key: overrides[key]})
    if overrides.get("skip_transcript"):
        whisper = replace(whisper, enabled=False)
    for key in ("format", "image_region", "pdf_transcript_mode"):
        if overrides.get(key) is not None:
            output = replace(output, **{key: overrides[key]})
    if overrides.get("keep_intermediate") is not None:
        output = replace(output, keep_intermediate=bool(overrides["keep_intermediate"]))

    updated = AppConfig(video=video, roi=roi, detection=detection, whisper=whisper, output=output)
    updated.validate()
    return updated
