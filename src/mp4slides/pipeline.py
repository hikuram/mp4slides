from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .alignment import align_transcript
from .config import AppConfig
from .detector import SlideDetector, write_detection_scores
from .media import extract_audio, extract_frame_png, probe_video
from .models import DetectedSlide, TranscriptSegment
from .pdf_writer import write_pdf
from .pptx_writer import write_pptx
from .transcriber import FasterWhisperTranscriber

LOGGER = logging.getLogger(__name__)


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _save_slide_images(slides: list[DetectedSlide], directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index, slide in enumerate(slides, start=1):
        path = directory / f"{stem}_slide_{index:04d}.png"
        path.write_bytes(slide.image_bytes)
        slide.image_path = str(path)


def _transcript_payload(segments: list[TranscriptSegment], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": metadata,
        "segments": [segment.to_dict() for segment in segments],
    }


def _segments_payload(
    input_path: Path,
    config: AppConfig,
    slides: list[DetectedSlide],
    reuse_segments: Path | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": str(input_path),
        "config": {
            "video": asdict(config.video),
            "roi": {
                "rect": config.roi.rect.as_list(),
                "ignore": [rect.as_list() for rect in config.roi.ignore],
            },
            "detection": asdict(config.detection),
            "whisper": asdict(config.whisper),
            "output": asdict(config.output),
        },
        "slides": [
            {
                "index": index,
                "start": slide.start,
                "end": slide.end,
                "duration": slide.duration,
                "representative_time": slide.representative_time,
                "image": slide.image_path,
                "merged_count": slide.merged_count,
                "trigger_score": slide.trigger_score,
                "transcript": slide.transcript,
            }
            for index, slide in enumerate(slides, start=1)
        ],
    }
    if reuse_segments is not None:
        payload["render"] = {
            "mode": "reuse-segments",
            "reuse_segments": str(reuse_segments),
        }
    return payload


def _capture_rect(config: AppConfig):
    if config.output.image_region == "full":
        return None
    return config.output.capture_roi or config.roi.rect


def _load_reused_slides(
    input_file: Path,
    segments_path: Path,
    config: AppConfig,
    duration: float,
) -> list[DetectedSlide]:
    payload = _load_json(segments_path)
    items = payload.get("slides")
    if not isinstance(items, list) or not items:
        raise ValueError(f"No slides found in reuse segments: {segments_path}")

    slides: list[DetectedSlide] = []
    crop_rect = _capture_rect(config)
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid slide entry {index} in {segments_path}")
        start = float(item["start"])
        end = float(item["end"])
        representative_time = float(item.get("representative_time", max(start, end - 0.05)))
        if start < 0 or end <= start:
            raise ValueError(f"Invalid time range for slide {index}: {start} - {end}")
        if representative_time < 0 or representative_time > duration + 1e-6:
            raise ValueError(
                f"Representative time for slide {index} is outside the video: {representative_time:.3f}s"
            )
        image_bytes = extract_frame_png(
            input_file,
            min(representative_time, max(0.0, duration - 0.001)),
            crop_rect=crop_rect,
            png_compression=config.detection.png_compression,
        )
        slides.append(
            DetectedSlide(
                start=start,
                end=end,
                representative_time=representative_time,
                image_bytes=image_bytes,
                analysis_gray=None,
                analysis_edges=None,
                merged_count=int(item.get("merged_count", 1)),
                trigger_score=item.get("trigger_score"),
                transcript=str(item.get("transcript", "")),
            )
        )
    return slides


def _copy_reuse_sidecar(reuse_segments: Path, output: Path, stem: str, suffix: str) -> Path | None:
    source_stem = reuse_segments.name.removesuffix(".segments.json")
    source = reuse_segments.parent / f"{source_stem}.{suffix}"
    if not source.exists():
        return None
    target = output / f"{stem}.{suffix}"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    config: AppConfig,
    reuse_segments: str | Path | None = None,
) -> dict[str, Path]:
    input_file = Path(input_path).resolve()
    if not input_file.exists():
        raise FileNotFoundError(input_file)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = input_file.stem

    LOGGER.info("Probing video: %s", input_file)
    video_info = probe_video(input_file)
    LOGGER.info(
        "Video %.2fs %dx%d %.3ffps audio=%s",
        video_info.duration,
        video_info.width,
        video_info.height,
        video_info.fps,
        video_info.has_audio,
    )

    artifacts: dict[str, Path] = {}
    reuse_path = Path(reuse_segments).resolve() if reuse_segments is not None else None
    if reuse_path is not None:
        if not reuse_path.exists():
            raise FileNotFoundError(reuse_path)
        LOGGER.info("Reusing slide boundaries and transcripts from %s", reuse_path)
        slides = _load_reused_slides(input_file, reuse_path, config, video_info.duration)
        LOGGER.info("Re-rendering %d preserved slide intervals", len(slides))
        transcript_sidecar = _copy_reuse_sidecar(reuse_path, output, stem, "transcript.json")
        if transcript_sidecar is not None:
            artifacts["transcript"] = transcript_sidecar
        if config.output.save_debug_scores:
            score_sidecar = _copy_reuse_sidecar(reuse_path, output, stem, "detection_scores.csv")
            if score_sidecar is not None:
                artifacts["detection_scores"] = score_sidecar
    else:
        detector = SlideDetector(config.video, config.roi, config.detection, config.output)
        LOGGER.info("Detecting slide intervals")
        slides, detection_scores = detector.detect(input_file, video_info.duration)
        LOGGER.info("Detected %d slide intervals after merging", len(slides))
        if config.output.save_debug_scores:
            score_path = output / f"{stem}.detection_scores.csv"
            write_detection_scores(detection_scores, score_path)
            artifacts["detection_scores"] = score_path

    slides_dir = output / "slides"
    _save_slide_images(slides, slides_dir, stem)

    temp_context = tempfile.TemporaryDirectory(prefix="mp4slides-")
    temp_dir = Path(temp_context.name)
    try:
        if reuse_path is None and config.whisper.enabled:
            if not video_info.has_audio:
                raise ValueError("Whisper is enabled but the input video has no audio stream")
            LOGGER.info("Extracting audio")
            audio_path = extract_audio(input_file, temp_dir / "audio.wav")
            LOGGER.info("Transcribing audio")
            transcriber = FasterWhisperTranscriber(config.whisper)
            transcript_segments, transcript_metadata = transcriber.transcribe(audio_path)
            transcript_metadata["enabled"] = True
            align_transcript(slides, transcript_segments)

            transcript_path = output / f"{stem}.transcript.json"
            _save_json(transcript_path, _transcript_payload(transcript_segments, transcript_metadata))
            artifacts["transcript"] = transcript_path

            if config.output.keep_intermediate:
                kept_audio = output / f"{stem}.audio.wav"
                shutil.copy2(audio_path, kept_audio)
                artifacts["audio"] = kept_audio

        segments_path = output / f"{stem}.segments.json"
        _save_json(segments_path, _segments_payload(input_file, config, slides, reuse_path))
        artifacts["segments"] = segments_path

        if config.output.format in {"pptx", "both"}:
            pptx_path = output / f"{stem}.pptx"
            write_pptx(slides, pptx_path, config.output)
            artifacts["pptx"] = pptx_path
            LOGGER.info("Wrote %s", pptx_path)

        if config.output.format in {"pdf", "both"}:
            pdf_path = output / f"{stem}.pdf"
            write_pdf(slides, pdf_path, config.output)
            artifacts["pdf"] = pdf_path
            LOGGER.info("Wrote %s", pdf_path)
    finally:
        temp_context.cleanup()

    return artifacts
