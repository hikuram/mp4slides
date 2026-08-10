from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import apply_overrides, load_config
from .pipeline import run_pipeline


def _rect(text: str) -> list[float]:
    try:
        values = [float(item.strip()) for item in text.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("rectangle must contain four numbers") from exc
    if len(values) != 4:
        raise argparse.ArgumentTypeError("rectangle must be x,y,width,height")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mp4slides",
        description="Create PPTX/PDF slide documents from a presentation video.",
    )
    parser.add_argument("input", help="Input MP4 or other FFmpeg-readable video")
    parser.add_argument("--output-dir", default="/output", help="Output directory")
    parser.add_argument("--config", help="YAML configuration file")
    parser.add_argument("--format", choices=["pptx", "pdf", "both"])
    parser.add_argument("--roi", type=_rect, help="Normalized x,y,width,height")
    parser.add_argument(
        "--ignore",
        type=_rect,
        action="append",
        help="Ignored full-frame normalized rectangle; repeatable",
    )
    parser.add_argument("--sample-fps", type=float)
    parser.add_argument("--stable-seconds", type=float)
    parser.add_argument("--threshold-high", type=float)
    parser.add_argument("--threshold-low", type=float)
    parser.add_argument("--reference-threshold", type=float)
    parser.add_argument("--merge-threshold", type=float)
    parser.add_argument("--model")
    parser.add_argument("--language")
    parser.add_argument("--device", choices=["cuda", "cpu", "auto"])
    parser.add_argument("--compute-type")
    parser.add_argument("--skip-transcript", action="store_true")
    parser.add_argument("--image-region", choices=["roi", "full"])
    parser.add_argument("--pdf-transcript-mode", choices=["below", "notes-page", "none"])
    parser.add_argument(
        "--keep-intermediate",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    config = apply_overrides(
        config,
        format=args.format,
        roi=args.roi,
        ignore=args.ignore,
        sample_fps=args.sample_fps,
        stable_seconds=args.stable_seconds,
        threshold_high=args.threshold_high,
        threshold_low=args.threshold_low,
        reference_threshold=args.reference_threshold,
        merge_threshold=args.merge_threshold,
        model=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        skip_transcript=args.skip_transcript,
        image_region=args.image_region,
        pdf_transcript_mode=args.pdf_transcript_mode,
        keep_intermediate=args.keep_intermediate,
    )
    artifacts = run_pipeline(Path(args.input), Path(args.output_dir), config)
    for name, path in artifacts.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
