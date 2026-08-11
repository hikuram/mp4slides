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


def test_example_config_matches_built_in_defaults() -> None:
    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    assert load_config(example) == load_config()


def test_example_config_explicitly_lists_all_default_fields() -> None:
    from dataclasses import fields

    import yaml

    from mp4slides.config import DetectionConfig, OutputConfig, VideoConfig, WhisperConfig

    example = Path(__file__).resolve().parents[1] / "config.example.yaml"
    data = yaml.safe_load(example.read_text(encoding="utf-8"))

    assert set(data) == {"video", "roi", "detection", "whisper", "output"}
    assert set(data["video"]) == {field.name for field in fields(VideoConfig)}
    assert set(data["roi"]) == {"x", "y", "width", "height", "ignore"}
    assert set(data["detection"]) == {field.name for field in fields(DetectionConfig)}
    assert set(data["whisper"]) == {field.name for field in fields(WhisperConfig)}
    assert set(data["output"]) == {field.name for field in fields(OutputConfig)}


def test_pdf_font_path_cli_override() -> None:
    from mp4slides.cli import build_parser
    from mp4slides.config import apply_overrides

    parser = build_parser()
    args = parser.parse_args(["input.mp4", "--pdf-font-path", "/fonts/custom.ttf"])
    config = apply_overrides(load_config(), pdf_font_path=args.pdf_font_path)
    assert config.output.pdf_font_path == "/fonts/custom.ttf"


def test_pdf_font_path_cli_overrides_yaml(tmp_path: Path) -> None:
    from mp4slides.cli import build_parser
    from mp4slides.config import apply_overrides

    path = tmp_path / "config.yaml"
    path.write_text("output:\n  pdf_font_path: /fonts/yaml.ttf\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["input.mp4", "--pdf-font-path", "/fonts/cli.ttf"])
    config = apply_overrides(load_config(path), pdf_font_path=args.pdf_font_path)
    assert config.output.pdf_font_path == "/fonts/cli.ttf"
