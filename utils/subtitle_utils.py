from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


class SubtitlePreparationError(RuntimeError):
    """Raised when subtitles cannot be prepared from the provided inputs."""


_STREAM_RE = re.compile(r"Stream #\d+:\d+")
_SUBTITLE_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?Subtitle:", re.IGNORECASE)


def _write_uploaded_file(uploaded_file, dst_path: str) -> str:
    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return dst_path


def _run_ffmpeg(command: list[str], *, check: bool) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise SubtitlePreparationError(
            "ffmpeg is not available on PATH. Install ffmpeg and try again."
        ) from e


def _decode_process_output(process: subprocess.CompletedProcess | subprocess.CalledProcessError) -> str:
    stdout = process.stdout if isinstance(process.stdout, bytes) else b""
    stderr = process.stderr if isinstance(process.stderr, bytes) else b""
    return b"\n".join(part for part in (stdout, stderr) if part).decode(errors="ignore")


def _inspect_streams(video_path: str) -> str:
    process = _run_ffmpeg(["ffmpeg", "-hide_banner", "-i", video_path], check=False)
    return _decode_process_output(process)


def _has_subtitle_stream(ffmpeg_output: str) -> bool:
    return bool(_SUBTITLE_STREAM_RE.search(ffmpeg_output))


def _has_any_stream(ffmpeg_output: str) -> bool:
    return bool(_STREAM_RE.search(ffmpeg_output))


def _summarize_ffmpeg_error(ffmpeg_output: str) -> str:
    lines = [line.strip() for line in ffmpeg_output.splitlines() if line.strip()]
    if not lines:
        return "ffmpeg did not return any diagnostic output."
    return "\n".join(lines[-12:])


def extract_or_load_subtitles(
    video_path: str,
    subtitle_file=None,
    work_dir: str = "temp",
) -> str:
    """
    Returns a usable .srt path.

    Priority:
    - If user uploaded an .srt, use it.
    - Else try extracting subtitles from the video using ffmpeg.
    """
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    if subtitle_file is not None:
        name = getattr(subtitle_file, "name", "uploaded.srt")
        if not name.lower().endswith(".srt"):
            raise ValueError("Subtitle file must be an .srt file.")
        srt_path = os.path.join(work_dir, f"uploaded_{Path(name).name}")
        return _write_uploaded_file(subtitle_file, srt_path)

    # Attempt extraction via ffmpeg (works only if the video contains subtitle streams)
    stream_info = _inspect_streams(video_path)
    if _has_any_stream(stream_info) and not _has_subtitle_stream(stream_info):
        raise SubtitlePreparationError(
            "This video does not contain an embedded subtitle stream. "
            "Please upload an .srt file manually."
        )

    srt_path = os.path.join(work_dir, "extracted.srt")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-map",
        "0:s:0",
        srt_path,
    ]

    try:
        _run_ffmpeg(command, check=True)
        if (not os.path.exists(srt_path)) or os.path.getsize(srt_path) == 0:
            raise SubtitlePreparationError("Extracted subtitle file is empty or missing.")
        return srt_path
    except subprocess.CalledProcessError as e:
        stderr = _decode_process_output(e)
        raise SubtitlePreparationError(
            "Could not extract subtitles from this video. "
            "Please upload an .srt file manually.\n\n"
            f"ffmpeg error:\n{_summarize_ffmpeg_error(stderr)}".strip()
        ) from e
