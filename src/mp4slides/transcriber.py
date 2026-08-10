from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config import WhisperConfig
from .models import TranscriptSegment, TranscriptWord

LOGGER = logging.getLogger(__name__)


class FasterWhisperTranscriber:
    def __init__(self, config: WhisperConfig) -> None:
        self.config = config

    def transcribe(self, audio_path: str | Path) -> tuple[list[TranscriptSegment], dict[str, Any]]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed") from exc

        LOGGER.info(
            "Loading Whisper model=%s device=%s compute_type=%s",
            self.config.model,
            self.config.device,
            self.config.compute_type,
        )
        model = WhisperModel(
            self.config.model,
            device=self.config.device,
            compute_type=self.config.compute_type,
        )
        raw_segments, info = model.transcribe(
            str(audio_path),
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
            word_timestamps=self.config.word_timestamps,
            condition_on_previous_text=self.config.condition_on_previous_text,
        )
        segments: list[TranscriptSegment] = []
        for segment in raw_segments:
            words: list[TranscriptWord] = []
            if self.config.word_timestamps and segment.words:
                for word in segment.words:
                    if word.start is None or word.end is None:
                        continue
                    words.append(
                        TranscriptWord(
                            start=float(word.start),
                            end=float(word.end),
                            text=str(word.word),
                        )
                    )
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=str(segment.text).strip(),
                    words=words,
                )
            )
        metadata = {
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration": getattr(info, "duration", None),
            "duration_after_vad": getattr(info, "duration_after_vad", None),
        }
        return segments, metadata
