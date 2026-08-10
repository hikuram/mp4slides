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
from .media import extract_audio, probe_video
from .models import DetectedSlide, TranscriptSegment
from .pdf_writer import write_pdf
from .pptx_writer import write_pptx
from .transcriber import FasterWhisperTranscriber

LOGGER = logging.getLogger(__name__)


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


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
) -> dict[str, Any]:
    return {
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


def run_pipeline(input_path: str | Path, output_dir: str | Path, config: AppConfig) -> dict[str, Path]:
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

    detector = SlideDetector(config.video, config.roi, config.detection, config.output)
    LOGGER.info("Detecting slide intervals")
    slides, detection_scores = detector.detect(input_file, video_info.duration)
    LOGGER.info("Detected %d slide intervals after merging", len(slides))

    slides_dir = output / "slides"
    _save_slide_images(slides, slides_dir, stem)

    artifacts: dict[str, Path] = {}
    if config.output.save_debug_scores:
        score_path = output / f"{stem}.detection_scores.csv"
        write_detection_scores(detection_scores, score_path)
        artifacts["detection_scores"] = score_path

    transcript_segments: list[TranscriptSegment] = []
    transcript_metadata: dict[str, Any] = {"enabled": False}

    temp_context = tempfile.TemporaryDirectory(prefix="mp4slides-")
    temp_dir = Path(temp_context.name)
    try:
        if config.whisper.enabled:
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
        _save_json(segments_path, _segments_payload(input_file, config, slides))
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
