from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def probe_video(path: str | Path) -> VideoInfo:
    target = str(path)
    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        target,
    ]
    result = _run(command)
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError(f"No video stream found in {target}")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration_value = video_stream.get("duration") or payload.get("format", {}).get("duration")
    if duration_value is None:
        raise ValueError(f"Unable to determine video duration for {target}")
    fps_text = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
    numerator, denominator = fps_text.split("/", 1)
    fps = float(numerator) / float(denominator) if float(denominator) else 0.0
    if fps <= 0:
        raise ValueError(f"Unable to determine video FPS for {target}")
    return VideoInfo(
        duration=float(duration_value),
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        has_audio=has_audio,
    )


def extract_audio(video_path: str | Path, audio_path: str | Path) -> Path:
    output = Path(audio_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    _run(command)
    return output
