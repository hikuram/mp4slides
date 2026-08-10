import cv2
import numpy as np

from mp4slides.config import DetectionConfig, OutputConfig, RoiConfig, VideoConfig
from mp4slides.detector import SlideDetector


def make_detector(merge_threshold: float = 0.02) -> SlideDetector:
    return SlideDetector(
        VideoConfig(sample_fps=3.0),
        RoiConfig(),
        DetectionConfig(merge_threshold=merge_threshold),
        OutputConfig(),
    )


def test_score_identical_frames_is_zero() -> None:
    detector = make_detector()
    frame = np.full((360, 640, 3), 255, dtype=np.uint8)
    left = detector._preprocess(frame)
    right = detector._preprocess(frame.copy())
    assert detector._score(left, right) == 0.0


def test_score_detects_content_change() -> None:
    detector = make_detector()
    left_frame = np.full((360, 640, 3), 255, dtype=np.uint8)
    right_frame = left_frame.copy()
    cv2.rectangle(right_frame, (100, 100), (500, 250), (0, 0, 0), -1)
    left = detector._preprocess(left_frame)
    right = detector._preprocess(right_frame)
    assert detector._score(left, right) > 0.05
