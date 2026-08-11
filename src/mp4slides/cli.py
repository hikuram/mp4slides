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
    parser.add_argument(
        "--reuse-segments",
        help="Reuse page boundaries, representative times, and transcripts from a previous segments JSON",
    )
    parser.add_argument("--format", choices=["pptx", "pdf", "both"])
    parser.add_argument("--roi", type=_rect, help="Normalized analysis ROI: x,y,width,height")
    parser.add_argument(
        "--capture-roi",
        type=_rect,
        help="Normalized output crop ROI; does not affect reused page boundaries",
    )
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
    parser.add_argument(
        "--pdf-transcript-mode",
        choices=["side-by-side", "below", "notes-page", "none"],
    )
    parser.add_argument(
        "--pdf-transcript-newline-mode",
        choices=["preserve", "space", "paragraph"],
        help="How transcript newlines are rendered in PDF output",
    )
    parser.add_argument(
        "--pptx-notes-newline-mode",
        choices=["preserve", "space", "paragraph"],
        help="How transcript newlines are rendered in PPTX speaker notes",
    )
    parser.add_argument("--pdf-transcript-ratio", type=float)
    parser.add_argument("--pdf-font-size", type=float)
    parser.add_argument("--pdf-min-font-size", type=float)
    parser.add_argument("--pdf-margin-pt", type=float)
    parser.add_argument("--pdf-gap-pt", type=float)
    parser.add_argument("--pdf-page-width-in", type=float)
    parser.add_argument("--pdf-page-height-in", type=float)
    parser.add_argument("--slide-width-in", type=float)
    parser.add_argument("--slide-height-in", type=float)
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
        capture_roi=args.capture_roi,
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
        pdf_transcript_newline_mode=args.pdf_transcript_newline_mode,
        pptx_notes_newline_mode=args.pptx_notes_newline_mode,
        pdf_transcript_ratio=args.pdf_transcript_ratio,
        pdf_font_size=args.pdf_font_size,
        pdf_min_font_size=args.pdf_min_font_size,
        pdf_margin_pt=args.pdf_margin_pt,
        pdf_gap_pt=args.pdf_gap_pt,
        pdf_page_width_in=args.pdf_page_width_in,
        pdf_page_height_in=args.pdf_page_height_in,
        slide_width_in=args.slide_width_in,
        slide_height_in=args.slide_height_in,
        keep_intermediate=args.keep_intermediate,
    )
    artifacts = run_pipeline(
        Path(args.input),
        Path(args.output_dir),
        config,
        reuse_segments=args.reuse_segments,
    )
    for name, path in artifacts.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
