from mp4slides.alignment import align_transcript
from mp4slides.models import DetectedSlide, TranscriptSegment


def make_slide(start: float, end: float) -> DetectedSlide:
    return DetectedSlide(start, end, start, b"", None, None)


def test_segment_is_assigned_by_overlap() -> None:
    slides = [make_slide(0.0, 5.0), make_slide(5.0, 10.0)]
    segments = [TranscriptSegment(4.0, 7.0, "second")]
    align_transcript(slides, segments)
    assert slides[0].transcript == ""
    assert slides[1].transcript == "second"


def test_segments_keep_order() -> None:
    slides = [make_slide(0.0, 10.0)]
    segments = [
        TranscriptSegment(1.0, 2.0, "a"),
        TranscriptSegment(3.0, 4.0, "b"),
    ]
    align_transcript(slides, segments)
    assert slides[0].transcript == "a\nb"
