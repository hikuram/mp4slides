from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .config import OutputConfig
from .models import DetectedSlide


def _register_font(config: OutputConfig) -> str:
    if config.pdf_font_path:
        path = Path(config.pdf_font_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF font not found: {path}")
        name = "Mp4SlidesCustom"
        pdfmetrics.registerFont(TTFont(name, str(path)))
        return name

    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    name = "HeiseiKakuGo-W5"
    pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name



def _fit_image(image_path: str, box_width: float, box_height: float) -> tuple[float, float]:
    with Image.open(image_path) as image:
        width, height = image.size
    scale = min(box_width / width, box_height / height)
    return width * scale, height * scale


def _wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and pdfmetrics.stringWidth(candidate, font_name, font_size) > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def _draw_transcript(
    pdf: canvas.Canvas,
    text: str,
    font_name: str,
    x: float,
    y_top: float,
    width: float,
    height: float,
) -> None:
    font_size = 10.0
    leading = 14.0
    lines = _wrap_text(text, font_name, font_size, width)
    max_lines = max(1, int(height // leading))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1][:-1] + "..." if lines[-1] else "..."
    pdf.setFont(font_name, font_size)
    y = y_top - leading
    for line in lines:
        if y < y_top - height:
            break
        pdf.drawString(x, y, line)
        y -= leading


def write_pdf(slides: list[DetectedSlide], output_path: str | Path, config: OutputConfig) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    page_width = config.slide_width_in * 72.0
    page_height = config.slide_height_in * 72.0
    pdf = canvas.Canvas(str(target), pagesize=(page_width, page_height))
    font_name = _register_font(config)
    margin = 18.0

    for index, item in enumerate(slides, start=1):
        if not item.image_path:
            raise ValueError(f"Slide {index} has no image_path")
        mode = config.pdf_transcript_mode
        transcript_height = page_height * config.pdf_transcript_ratio if mode == "below" else 0.0
        image_box_width = page_width - 2 * margin
        image_box_height = page_height - 2 * margin - transcript_height
        image_width, image_height = _fit_image(item.image_path, image_box_width, image_box_height)
        image_x = (page_width - image_width) / 2.0
        image_y = margin + transcript_height + (image_box_height - image_height) / 2.0
        pdf.drawImage(
            item.image_path,
            image_x,
            image_y,
            width=image_width,
            height=image_height,
            preserveAspectRatio=True,
            mask="auto",
        )
        if mode == "below":
            pdf.setFont(font_name, 8.0)
            pdf.drawString(margin, transcript_height - 12.0, f"{item.start:.3f} - {item.end:.3f}")
            _draw_transcript(
                pdf,
                item.transcript,
                font_name,
                margin,
                transcript_height - 16.0,
                page_width - 2 * margin,
                max(12.0, transcript_height - 24.0),
            )
        pdf.showPage()

        if mode == "notes-page":
            pdf.setFont(font_name, 12.0)
            pdf.drawString(margin, page_height - margin - 12.0, f"Slide {index}: {item.start:.3f} - {item.end:.3f}")
            _draw_transcript(
                pdf,
                item.transcript,
                font_name,
                margin,
                page_height - margin - 28.0,
                page_width - 2 * margin,
                page_height - 2 * margin - 32.0,
            )
            pdf.showPage()

    pdf.save()
    return target
