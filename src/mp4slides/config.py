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
    capture_roi: Rect | None = None
    keep_intermediate: bool = True
    save_debug_scores: bool = True
    slide_width_in: float = 13.333333
    slide_height_in: float = 7.5
    pdf_transcript_mode: str = "side-by-side"
    pdf_transcript_newline_mode: str = "space"
    pptx_notes_newline_mode: str = "preserve"
    pdf_transcript_ratio: float = 0.40
    pdf_font_path: str | None = None
    pdf_font_size: float = 10.0
    pdf_min_font_size: float = 8.0
    pdf_margin_pt: float = 18.0
    pdf_gap_pt: float = 18.0
    pdf_page_width_in: float | None = None
    pdf_page_height_in: float | None = None


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
        if self.output.capture_roi is not None:
            self.output.capture_roi.validate("output.capture_roi")
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
        if self.output.pdf_transcript_mode not in {"side-by-side", "below", "notes-page", "none"}:
            raise ValueError("output.pdf_transcript_mode is invalid")
        newline_modes = {"preserve", "space", "paragraph"}
        if self.output.pdf_transcript_newline_mode not in newline_modes:
            raise ValueError("output.pdf_transcript_newline_mode is invalid")
        if self.output.pptx_notes_newline_mode not in newline_modes:
            raise ValueError("output.pptx_notes_newline_mode is invalid")
        if not 0.05 <= self.output.pdf_transcript_ratio <= 0.80:
            raise ValueError("output.pdf_transcript_ratio must be within [0.05, 0.80]")
        if self.output.pdf_font_size <= 0 or self.output.pdf_min_font_size <= 0:
            raise ValueError("PDF font sizes must be positive")
        if self.output.pdf_min_font_size > self.output.pdf_font_size:
            raise ValueError("output.pdf_min_font_size must not exceed output.pdf_font_size")
        if self.output.pdf_margin_pt < 0 or self.output.pdf_gap_pt < 0:
            raise ValueError("PDF margin and gap must be non-negative")
        for name, value in (
            ("output.pdf_page_width_in", self.output.pdf_page_width_in),
            ("output.pdf_page_height_in", self.output.pdf_page_height_in),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")


def _mapping(data: Any, key: str) -> dict[str, Any]:
    value = data.get(key, {}) if isinstance(data, dict) else {}
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _rect_from_mapping(data: dict[str, Any]) -> Rect:
    return Rect(
        float(data.get("x", 0.0)),
        float(data.get("y", 0.0)),
        float(data.get("width", 1.0)),
        float(data.get("height", 1.0)),
    )


def _optional_rect(value: Any, name: str) -> Rect | None:
    if value is None:
        return None
    if isinstance(value, dict):
        rect = _rect_from_mapping(value)
        rect.validate(name)
        return rect
    if isinstance(value, (list, tuple)):
        rect = Rect.from_sequence(value)
        rect.validate(name)
        return rect
    raise ValueError(f"{name} must be x,y,width,height or a mapping")


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
    output_data = dict(_mapping(data, "output"))

    ignore_items = roi_data.get("ignore", []) or []
    if not isinstance(ignore_items, list):
        raise ValueError("roi.ignore must be a list")

    capture_roi = _optional_rect(output_data.pop("capture_roi", None), "output.capture_roi")

    config = AppConfig(
        video=VideoConfig(**video_data),
        roi=RoiConfig(
            rect=_rect_from_mapping(roi_data),
            ignore=tuple(Rect.from_sequence(item) for item in ignore_items),
        ),
        detection=DetectionConfig(**detection_data),
        whisper=WhisperConfig(**whisper_data),
        output=OutputConfig(capture_roi=capture_roi, **output_data),
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
    for key in (
        "format",
        "image_region",
        "pdf_transcript_mode",
        "pdf_transcript_newline_mode",
        "pptx_notes_newline_mode",
    ):
        if overrides.get(key) is not None:
            output = replace(output, **{key: overrides[key]})
    if overrides.get("capture_roi") is not None:
        output = replace(output, capture_roi=Rect.from_sequence(overrides["capture_roi"]))
    for key in (
        "pdf_transcript_ratio",
        "pdf_font_size",
        "pdf_min_font_size",
        "pdf_margin_pt",
        "pdf_gap_pt",
        "slide_width_in",
        "slide_height_in",
        "pdf_page_width_in",
        "pdf_page_height_in",
    ):
        if overrides.get(key) is not None:
            output = replace(output, **{key: float(overrides[key])})
    if overrides.get("keep_intermediate") is not None:
        output = replace(output, keep_intermediate=bool(overrides["keep_intermediate"]))

    updated = AppConfig(video=video, roi=roi, detection=detection, whisper=whisper, output=output)
    updated.validate()
    return updated
