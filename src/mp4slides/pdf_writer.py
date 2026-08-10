from __future__ import annotations

import math
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
    paragraphs = text.splitlines()
    if not paragraphs:
        return [""]
    for paragraph in paragraphs:
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


def _draw_lines(
    pdf: canvas.Canvas,
    lines: list[str],
    font_name: str,
    font_size: float,
    x: float,
    y_top: float,
    leading: float,
) -> None:
    pdf.setFont(font_name, font_size)
    y = y_top - leading
    for line in lines:
        pdf.drawString(x, y, line)
        y -= leading


def _fit_or_paginate_text(
    text: str,
    font_name: str,
    preferred_font_size: float,
    min_font_size: float,
    width: float,
    height: float,
) -> tuple[float, float, list[list[str]]]:
    size = preferred_font_size
    while size >= min_font_size - 1e-9:
        leading = size * 1.40
        lines = _wrap_text(text, font_name, size, width)
        capacity = max(1, int(height // leading))
        if len(lines) <= capacity:
            return size, leading, [lines]
        size -= 0.5

    size = min_font_size
    leading = size * 1.40
    lines = _wrap_text(text, font_name, size, width)
    capacity = max(1, int(height // leading))
    pages = [lines[index:index + capacity] for index in range(0, len(lines), capacity)] or [[""]]
    return size, leading, pages


def _draw_fitted_image(
    pdf: canvas.Canvas,
    image_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    image_width, image_height = _fit_image(image_path, width, height)
    image_x = x + (width - image_width) / 2.0
    image_y = y + (height - image_height) / 2.0
    pdf.drawImage(
        image_path,
        image_x,
        image_y,
        width=image_width,
        height=image_height,
        preserveAspectRatio=True,
        mask="auto",
    )


def _write_side_by_side_page(
    pdf: canvas.Canvas,
    item: DetectedSlide,
    index: int,
    font_name: str,
    page_width: float,
    page_height: float,
    config: OutputConfig,
) -> None:
    margin = config.pdf_margin_pt
    gap = config.pdf_gap_pt
    content_width = page_width - 2 * margin
    content_height = page_height - 2 * margin
    transcript_width = content_width * config.pdf_transcript_ratio
    image_width = content_width - transcript_width - gap
    if image_width <= 0 or transcript_width <= 0:
        raise ValueError("PDF side-by-side layout leaves no usable content width")

    header_size = max(config.pdf_min_font_size, min(9.0, config.pdf_font_size))
    header_leading = header_size * 1.4
    header_height = header_leading * 1.8
    text_height = max(1.0, content_height - header_height)
    font_size, leading, text_pages = _fit_or_paginate_text(
        item.transcript,
        font_name,
        config.pdf_font_size,
        config.pdf_min_font_size,
        transcript_width,
        text_height,
    )

    for part_index, lines in enumerate(text_pages, start=1):
        _draw_fitted_image(pdf, item.image_path or "", margin, margin, image_width, content_height)
        text_x = margin + image_width + gap
        pdf.setFont(font_name, header_size)
        header = f"Slide {index}  {item.start:.3f} - {item.end:.3f}"
        if len(text_pages) > 1:
            header += f"  ({part_index}/{len(text_pages)})"
        pdf.drawString(text_x, page_height - margin - header_leading, header)
        _draw_lines(
            pdf,
            lines,
            font_name,
            font_size,
            text_x,
            page_height - margin - header_height,
            leading,
        )
        pdf.showPage()


def _write_below_page(
    pdf: canvas.Canvas,
    item: DetectedSlide,
    font_name: str,
    page_width: float,
    page_height: float,
    config: OutputConfig,
) -> None:
    margin = config.pdf_margin_pt
    transcript_height = page_height * config.pdf_transcript_ratio
    image_box_width = page_width - 2 * margin
    image_box_height = page_height - 2 * margin - transcript_height
    _draw_fitted_image(pdf, item.image_path or "", margin, margin + transcript_height, image_box_width, image_box_height)

    font_size, leading, pages = _fit_or_paginate_text(
        item.transcript,
        font_name,
        config.pdf_font_size,
        config.pdf_min_font_size,
        page_width - 2 * margin,
        max(1.0, transcript_height - 24.0),
    )
    pdf.setFont(font_name, max(config.pdf_min_font_size, min(8.0, config.pdf_font_size)))
    pdf.drawString(margin, transcript_height - 12.0, f"{item.start:.3f} - {item.end:.3f}")
    _draw_lines(pdf, pages[0], font_name, font_size, margin, transcript_height - 16.0, leading)
    pdf.showPage()

    for continuation in pages[1:]:
        _draw_lines(pdf, continuation, font_name, font_size, margin, page_height - margin, leading)
        pdf.showPage()


def _write_notes_page(
    pdf: canvas.Canvas,
    item: DetectedSlide,
    index: int,
    font_name: str,
    page_width: float,
    page_height: float,
    config: OutputConfig,
) -> None:
    margin = config.pdf_margin_pt
    header_size = max(config.pdf_min_font_size, min(10.0, config.pdf_font_size))
    header_leading = header_size * 1.4
    text_height = page_height - 2 * margin - header_leading * 2
    font_size, leading, pages = _fit_or_paginate_text(
        item.transcript,
        font_name,
        config.pdf_font_size,
        config.pdf_min_font_size,
        page_width - 2 * margin,
        max(1.0, text_height),
    )
    for part_index, lines in enumerate(pages, start=1):
        pdf.setFont(font_name, header_size)
        header = f"Slide {index}: {item.start:.3f} - {item.end:.3f}"
        if len(pages) > 1:
            header += f"  ({part_index}/{len(pages)})"
        pdf.drawString(margin, page_height - margin - header_leading, header)
        _draw_lines(
            pdf,
            lines,
            font_name,
            font_size,
            margin,
            page_height - margin - header_leading * 2,
            leading,
        )
        pdf.showPage()


def write_pdf(slides: list[DetectedSlide], output_path: str | Path, config: OutputConfig) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    width_in = config.pdf_page_width_in or config.slide_width_in
    height_in = config.pdf_page_height_in or config.slide_height_in
    page_width = width_in * 72.0
    page_height = height_in * 72.0
    pdf = canvas.Canvas(str(target), pagesize=(page_width, page_height))
    font_name = _register_font(config)

    for index, item in enumerate(slides, start=1):
        if not item.image_path:
            raise ValueError(f"Slide {index} has no image_path")
        mode = config.pdf_transcript_mode
        if mode == "side-by-side":
            _write_side_by_side_page(pdf, item, index, font_name, page_width, page_height, config)
            continue
        if mode == "below":
            _write_below_page(pdf, item, font_name, page_width, page_height, config)
            continue

        margin = config.pdf_margin_pt
        _draw_fitted_image(
            pdf,
            item.image_path,
            margin,
            margin,
            page_width - 2 * margin,
            page_height - 2 * margin,
        )
        pdf.showPage()
        if mode == "notes-page":
            _write_notes_page(pdf, item, index, font_name, page_width, page_height, config)

    pdf.save()
    return target
