from pathlib import Path

from mp4slides.config import load_config


def test_default_config_is_valid() -> None:
    config = load_config()
    assert config.video.sample_fps == 3.0
    assert config.whisper.language == "ja"
    assert config.output.pdf_transcript_mode == "side-by-side"
    assert config.output.pdf_transcript_newline_mode == "space"
    assert config.output.pptx_notes_newline_mode == "preserve"
    assert config.output.pdf_transcript_ratio == 0.40


def test_yaml_config(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "video:\n  sample_fps: 2.0\nroi:\n  x: 0.1\n  y: 0.2\n  width: 0.8\n  height: 0.7\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.video.sample_fps == 2.0
    assert config.roi.rect.x == 0.1


def test_capture_roi_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "output:\n  capture_roi: [0.1, 0.2, 0.7, 0.6]\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.output.capture_roi is not None
    assert config.output.capture_roi.x == 0.1
    assert config.output.capture_roi.height == 0.6


def test_transcript_newline_modes_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "output:\n"
        "  pdf_transcript_newline_mode: paragraph\n"
        "  pptx_notes_newline_mode: space\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.output.pdf_transcript_newline_mode == "paragraph"
    assert config.output.pptx_notes_newline_mode == "space"
