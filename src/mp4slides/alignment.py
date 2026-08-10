from __future__ import annotations

from .models import DetectedSlide, TranscriptSegment


def _overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def align_transcript(slides: list[DetectedSlide], segments: list[TranscriptSegment]) -> None:
    buckets: list[list[str]] = [[] for _ in slides]
    if not slides:
        return

    for segment in segments:
        if segment.words:
            word_buckets: dict[int, list[str]] = {}
            for word in segment.words:
                midpoint = (word.start + word.end) / 2.0
                index = min(
                    range(len(slides)),
                    key=lambda idx: 0.0
                    if slides[idx].start <= midpoint < slides[idx].end
                    else min(abs(midpoint - slides[idx].start), abs(midpoint - slides[idx].end)),
                )
                word_buckets.setdefault(index, []).append(word.text)
            for index, words in word_buckets.items():
                text = "".join(words).strip()
                if text:
                    buckets[index].append(text)
            continue

        overlaps = [
            _overlap(segment.start, segment.end, slide.start, slide.end)
            for slide in slides
        ]
        best = max(range(len(slides)), key=lambda idx: overlaps[idx])
        if overlaps[best] <= 0:
            midpoint = (segment.start + segment.end) / 2.0
            best = min(
                range(len(slides)),
                key=lambda idx: abs(midpoint - (slides[idx].start + slides[idx].end) / 2.0),
            )
        text = segment.text.strip()
        if text:
            buckets[best].append(text)

    for slide, bucket in zip(slides, buckets):
        slide.transcript = "\n".join(bucket).strip()
