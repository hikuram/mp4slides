import json
from pathlib import Path

from mp4slides.config import AppConfig, OutputConfig
from mp4slides.models import Rect
from mp4slides.pipeline import _load_reused_slides


def test_reuse_preserves_boundaries_and_transcript(tmp_path: Path, monkeypatch) -> None:
    segments_path = tmp_path / "source.segments.json"
    segments_path.write_text(
        json.dumps(
            {
                "slides": [
                    {
                        "start": 1.0,
                        "end": 5.0,
                        "representative_time": 4.5,
                        "transcript": "kept transcript",
                        "merged_count": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"placeholder")
    calls = []

    def fake_extract(video_path, timestamp, crop_rect=None, png_compression=3):
        calls.append((video_path, timestamp, crop_rect, png_compression))
        return b"png"

    monkeypatch.setattr("mp4slides.pipeline.extract_frame_png", fake_extract)
    config = AppConfig(
        output=OutputConfig(capture_roi=Rect(0.1, 0.2, 0.7, 0.6))
    )
    slides = _load_reused_slides(video_path, segments_path, config, duration=10.0)

    assert len(slides) == 1
    assert slides[0].start == 1.0
    assert slides[0].end == 5.0
    assert slides[0].representative_time == 4.5
    assert slides[0].transcript == "kept transcript"
    assert slides[0].merged_count == 2
    assert calls[0][2] == Rect(0.1, 0.2, 0.7, 0.6)
