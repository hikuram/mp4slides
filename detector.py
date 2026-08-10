from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import DetectionConfig, OutputConfig, RoiConfig, VideoConfig
from .models import DetectedSlide, DetectionScore, Rect


@dataclass
class _ProcessedFrame:
    gray: np.ndarray
    edges: np.ndarray


class SlideDetector:
    def __init__(
        self,
        video_config: VideoConfig,
        roi_config: RoiConfig,
        detection_config: DetectionConfig,
        output_config: OutputConfig,
    ) -> None:
        self.video_config = video_config
        self.roi_config = roi_config
        self.config = detection_config
        self.output_config = output_config
        self._mask: np.ndarray | None = None
        self._mask_shape: tuple[int, int] | None = None

    def _crop_rect(self, frame: np.ndarray, rect: Rect) -> np.ndarray:
        height, width = frame.shape[:2]
        x1 = max(0, min(width - 1, int(round(rect.x * width))))
        y1 = max(0, min(height - 1, int(round(rect.y * height))))
        x2 = max(x1 + 1, min(width, int(round((rect.x + rect.width) * width))))
        y2 = max(y1 + 1, min(height, int(round((rect.y + rect.height) * height))))
        return frame[y1:y2, x1:x2]

    def _output_frame(self, frame: np.ndarray) -> np.ndarray:
        if self.output_config.image_region == "full":
            return frame
        return self._crop_rect(frame, self.roi_config.rect)

    def _build_mask(self, resized_height: int, resized_width: int) -> np.ndarray:
        shape = (resized_height, resized_width)
        if self._mask is not None and self._mask_shape == shape:
            return self._mask
        mask = np.ones(shape, dtype=np.uint8)
        roi = self.roi_config.rect
        for ignored in self.roi_config.ignore:
            ix1 = (ignored.x - roi.x) / roi.width
            iy1 = (ignored.y - roi.y) / roi.height
            ix2 = (ignored.x + ignored.width - roi.x) / roi.width
            iy2 = (ignored.y + ignored.height - roi.y) / roi.height
            ix1 = max(0.0, min(1.0, ix1))
            iy1 = max(0.0, min(1.0, iy1))
            ix2 = max(0.0, min(1.0, ix2))
            iy2 = max(0.0, min(1.0, iy2))
            if ix2 <= ix1 or iy2 <= iy1:
                continue
            x1 = int(round(ix1 * resized_width))
            y1 = int(round(iy1 * resized_height))
            x2 = int(round(ix2 * resized_width))
            y2 = int(round(iy2 * resized_height))
            mask[y1:y2, x1:x2] = 0
        if not np.any(mask):
            raise ValueError("ROI ignore rectangles mask the entire analysis area")
        self._mask = mask
        self._mask_shape = shape
        return mask

    def _preprocess(self, frame: np.ndarray) -> _ProcessedFrame:
        crop = self._crop_rect(frame, self.roi_config.rect)
        height, width = crop.shape[:2]
        scale = self.config.resize_width / float(width)
        resized_height = max(1, int(round(height * scale)))
        resized = cv2.resize(crop, (self.config.resize_width, resized_height), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        kernel = self.config.gaussian_kernel
        if kernel > 1:
            gray = cv2.GaussianBlur(gray, (kernel, kernel), 0)
        edges = cv2.Canny(gray, self.config.canny_low, self.config.canny_high)
        self._build_mask(gray.shape[0], gray.shape[1])
        return _ProcessedFrame(gray=gray, edges=edges)

    def _score(self, left: _ProcessedFrame, right: _ProcessedFrame) -> float:
        if left.gray.shape != right.gray.shape:
            raise ValueError("Processed frames have incompatible shapes")
        mask = self._mask
        if mask is None:
            raise RuntimeError("Analysis mask is not initialized")
        valid = mask.astype(bool)
        pixel = cv2.absdiff(left.gray, right.gray)[valid].mean() / 255.0
        edge = cv2.absdiff(left.edges, right.edges)[valid].mean() / 255.0
        total_weight = self.config.pixel_weight + self.config.edge_weight
        return float(
            (self.config.pixel_weight * pixel + self.config.edge_weight * edge) / total_weight
        )

    def _encode_output(self, frame: np.ndarray) -> bytes:
        output_frame = self._output_frame(frame)
        ok, buffer = cv2.imencode(
            ".png",
            output_frame,
            [cv2.IMWRITE_PNG_COMPRESSION, self.config.png_compression],
        )
        if not ok:
            raise RuntimeError("Failed to encode representative frame")
        return bytes(buffer)

    def _new_slide(
        self,
        start: float,
        end: float,
        representative_time: float,
        image_bytes: bytes,
        processed: _ProcessedFrame,
        trigger_score: float | None,
    ) -> DetectedSlide:
        return DetectedSlide(
            start=start,
            end=end,
            representative_time=representative_time,
            image_bytes=image_bytes,
            analysis_gray=processed.gray.copy(),
            analysis_edges=processed.edges.copy(),
            trigger_score=trigger_score,
        )

    def _score_slides(self, left: DetectedSlide, right: DetectedSlide) -> float:
        return self._score(
            _ProcessedFrame(left.analysis_gray, left.analysis_edges),
            _ProcessedFrame(right.analysis_gray, right.analysis_edges),
        )

    def _merge_minor_changes(self, slides: list[DetectedSlide]) -> list[DetectedSlide]:
        if not slides:
            return []
        merged = [slides[0]]
        for slide in slides[1:]:
            previous = merged[-1]
            score = self._score_slides(previous, slide)
            if score <= self.config.merge_threshold:
                previous.end = slide.end
                previous.representative_time = slide.representative_time
                previous.image_bytes = slide.image_bytes
                previous.analysis_gray = slide.analysis_gray
                previous.analysis_edges = slide.analysis_edges
                previous.merged_count += slide.merged_count
                if slide.trigger_score is not None:
                    previous.trigger_score = slide.trigger_score
            else:
                merged.append(slide)
        return merged

    def _merge_short_slides(self, slides: list[DetectedSlide]) -> list[DetectedSlide]:
        if self.config.min_slide_seconds <= 0 or len(slides) < 2:
            return slides
        work = list(slides)
        changed = True
        while changed and len(work) > 1:
            changed = False
            for index, slide in enumerate(work):
                if slide.duration >= self.config.min_slide_seconds:
                    continue
                if index == 0:
                    next_slide = work[1]
                    next_slide.start = slide.start
                    next_slide.merged_count += slide.merged_count
                    work.pop(0)
                elif index == len(work) - 1:
                    previous = work[index - 1]
                    previous.end = slide.end
                    previous.merged_count += slide.merged_count
                    work.pop(index)
                else:
                    previous = work[index - 1]
                    next_slide = work[index + 1]
                    prev_score = self._score_slides(previous, slide)
                    next_score = self._score_slides(slide, next_slide)
                    if prev_score <= next_score:
                        previous.end = slide.end
                        previous.merged_count += slide.merged_count
                        work.pop(index)
                    else:
                        next_slide.start = slide.start
                        next_slide.merged_count += slide.merged_count
                        work.pop(index)
                changed = True
                break
        return work

    def detect(self, video_path: str | Path, duration: float) -> tuple[list[DetectedSlide], list[DetectionScore]]:
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Unable to open video: {video_path}")
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        if source_fps <= 0:
            capture.release()
            raise ValueError("Unable to determine source FPS")
        sample_step = max(1, int(round(source_fps / self.video_config.sample_fps)))

        slides: list[DetectedSlide] = []
        scores: list[DetectionScore] = []
        frame_index = 0
        sampled = 0
        previous_processed: _ProcessedFrame | None = None
        current_anchor: _ProcessedFrame | None = None
        current_start = 0.0
        current_image: bytes | None = None
        current_processed: _ProcessedFrame | None = None
        current_time = 0.0
        current_trigger: float | None = None
        state = "stable"
        transition_start: float | None = None
        low_since: float | None = None
        transition_image: bytes | None = None
        transition_processed: _ProcessedFrame | None = None
        transition_time = 0.0

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if frame_index % sample_step != 0:
                    frame_index += 1
                    continue
                timestamp = frame_index / source_fps
                processed = self._preprocess(frame)
                image_bytes = self._encode_output(frame)
                sampled += 1

                if previous_processed is None:
                    previous_processed = processed
                    current_anchor = processed
                    current_processed = processed
                    current_image = image_bytes
                    current_time = timestamp
                    scores.append(DetectionScore(timestamp, 0.0, 0.0, state, "start"))
                    frame_index += 1
                    continue

                if current_anchor is None or current_processed is None or current_image is None:
                    raise RuntimeError("Detector state is incomplete")

                frame_delta = self._score(previous_processed, processed)
                reference_delta = self._score(current_anchor, processed)
                event = ""

                if state == "stable":
                    is_change = (
                        frame_delta >= self.config.threshold_high
                        or reference_delta >= self.config.reference_threshold
                    )
                    if is_change:
                        state = "changing"
                        transition_start = timestamp
                        transition_image = image_bytes
                        transition_processed = processed
                        transition_time = timestamp
                        low_since = None
                        current_trigger = max(frame_delta, reference_delta)
                        event = "change-start"
                    else:
                        current_image = image_bytes
                        current_processed = processed
                        current_time = timestamp
                else:
                    transition_image = image_bytes
                    transition_processed = processed
                    transition_time = timestamp
                    if frame_delta <= self.config.threshold_low:
                        if low_since is None:
                            low_since = timestamp
                        if timestamp - low_since >= self.config.stable_seconds:
                            if transition_start is None:
                                raise RuntimeError("Missing transition start")
                            slides.append(
                                self._new_slide(
                                    current_start,
                                    transition_start,
                                    current_time,
                                    current_image,
                                    current_processed,
                                    current_trigger,
                                )
                            )
                            current_start = transition_start
                            current_anchor = processed
                            current_image = image_bytes
                            current_processed = processed
                            current_time = timestamp
                            current_trigger = max(frame_delta, reference_delta)
                            transition_start = None
                            transition_image = None
                            transition_processed = None
                            low_since = None
                            state = "stable"
                            event = "change-end"
                    else:
                        low_since = None

                scores.append(DetectionScore(timestamp, frame_delta, reference_delta, state, event))
                previous_processed = processed
                frame_index += 1
        finally:
            capture.release()

        if sampled == 0 or current_image is None or current_processed is None:
            raise ValueError("No frames were sampled from the video")

        if state == "stable":
            slides.append(
                self._new_slide(
                    current_start,
                    duration,
                    current_time,
                    current_image,
                    current_processed,
                    current_trigger,
                )
            )
        else:
            if transition_start is None:
                raise RuntimeError("Missing final transition start")
            if transition_start > current_start:
                slides.append(
                    self._new_slide(
                        current_start,
                        transition_start,
                        current_time,
                        current_image,
                        current_processed,
                        current_trigger,
                    )
                )
            if transition_image is not None and transition_processed is not None and duration > transition_start:
                slides.append(
                    self._new_slide(
                        transition_start,
                        duration,
                        transition_time,
                        transition_image,
                        transition_processed,
                        current_trigger,
                    )
                )

        slides = [slide for slide in slides if slide.end > slide.start]
        slides = self._merge_minor_changes(slides)
        slides = self._merge_short_slides(slides)
        return slides, scores


def write_detection_scores(scores: list[DetectionScore], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time", "frame_delta", "reference_delta", "state", "event"],
        )
        writer.writeheader()
        for score in scores:
            writer.writerow(score.to_row())
    return target
