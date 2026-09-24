from __future__ import annotations

import os
import uuid
from pathlib import Path

import pysrt
from gtts import gTTS
from pydub import AudioSegment


def _safe_filename(prefix: str, idx: int, ext: str) -> str:
    return f"{prefix}_{idx:05d}_{uuid.uuid4().hex[:8]}.{ext}"


def _normalize_sub_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split()).strip()


def generate_tts_audio(
    srt_path: str,
    language: str = "en",
    work_dir: str = "temp",
    outputs_dir: str = "outputs",
) -> str:
    """
    Generate speech with pauses that match SRT timings.

    Strategy:
    - Build a single timeline audio track.
    - Insert silent gaps between subtitle start times.
    - For each subtitle, synthesize audio and fit it into its subtitle window
      (pad or trim; optional bounded speed adjustment).
    """
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"SRT not found: {srt_path}")

    subs = pysrt.open(srt_path)
    if not subs:
        raise ValueError("No subtitles found in SRT file.")

    session_dir = Path(work_dir) / f"tts_{uuid.uuid4().hex}"
    session_dir.mkdir(parents=True, exist_ok=True)
    Path(outputs_dir).mkdir(parents=True, exist_ok=True)

    final_audio = AudioSegment.silent(duration=0)
    previous_end_ms = 0

    for i, sub in enumerate(subs):
        text = _normalize_sub_text(sub.text or "")
        if not text:
            previous_end_ms = max(previous_end_ms, int(sub.end.ordinal))
            continue

        start_ms = int(sub.start.ordinal)
        end_ms = int(sub.end.ordinal)
        duration_ms = max(0, end_ms - start_ms)

        # Insert gap from previous subtitle end → current start
        gap_ms = start_ms - previous_end_ms
        if gap_ms > 0:
            final_audio += AudioSegment.silent(duration=gap_ms)

        temp_mp3 = session_dir / _safe_filename("seg", i, "mp3")
        try:
            tts = gTTS(text=text, lang=language, slow=False)
            tts.save(str(temp_mp3))
            segment = AudioSegment.from_mp3(str(temp_mp3))
        except Exception as e:
            raise RuntimeError(f"TTS failed for segment {i}: {text}\n{e}") from e

        # Fit segment into its subtitle window
        if duration_ms > 0 and len(segment) > 0:
            if len(segment) > duration_ms:
                # Speed up a bit (bounded), then trim if still long
                speed = len(segment) / duration_ms
                if 1.05 < speed < 1.8:
                    segment = segment.speedup(playback_speed=speed)
                if len(segment) > duration_ms:
                    segment = segment[:duration_ms]
            elif len(segment) < duration_ms:
                segment += AudioSegment.silent(duration=(duration_ms - len(segment)))

        final_audio += segment
        previous_end_ms = max(previous_end_ms, end_ms)

        try:
            temp_mp3.unlink(missing_ok=True)  # py3.8+ on Windows supports missing_ok
        except Exception:
            pass

    output_audio = os.path.join(outputs_dir, "final_audio.mp3")
    final_audio.export(output_audio, format="mp3", bitrate="192k")

    # Cleanup session temp dir (best effort)
    try:
        for p in session_dir.glob("*"):
            try:
                p.unlink()
            except Exception:
                pass
        session_dir.rmdir()
    except Exception:
        pass

    return output_audio
