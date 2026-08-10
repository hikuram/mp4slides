from pathlib import Path

from PIL import Image
from pptx import Presentation

from mp4slides.config import OutputConfig
from mp4slides.models import DetectedSlide
from mp4slides.pdf_writer import write_pdf
from mp4slides.pptx_writer import write_pptx


def make_image(path: Path) -> None:
    image = Image.new("RGB", (640, 360), (240, 240, 240))
    image.save(path)


def make_slide(image_path: Path) -> DetectedSlide:
    text = "\u65e5\u672c\u8a9e\u306e\u6587\u5b57\u8d77\u3053\u3057"
    return DetectedSlide(
        start=0.0,
        end=5.0,
        representative_time=4.5,
        image_bytes=b"",
        analysis_gray=None,
        analysis_edges=None,
        image_path=str(image_path),
        transcript=text,
    )


def test_pptx_contains_notes(tmp_path: Path) -> None:
    image_path = tmp_path / "slide.png"
    make_image(image_path)
    output = tmp_path / "out.pptx"
    slide = make_slide(image_path)
    write_pptx([slide], output, OutputConfig(format="pptx"))
    presentation = Presentation(output)
    notes = presentation.slides[0].notes_slide.notes_text_frame.text
    assert slide.transcript in notes


def test_pdf_writes_japanese_transcript(tmp_path: Path) -> None:
    image_path = tmp_path / "slide.png"
    make_image(image_path)
    output = tmp_path / "out.pdf"
    write_pdf([make_slide(image_path)], output, OutputConfig(format="pdf"))
    assert output.exists()
    assert output.stat().st_size > 1000
