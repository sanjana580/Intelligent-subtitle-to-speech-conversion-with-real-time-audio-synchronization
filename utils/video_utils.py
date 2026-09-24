from __future__ import annotations

import os
import uuid
from pathlib import Path


def merge_audio_with_video(
    video_path: str,
    audio_path: str,
    outputs_dir: str = "outputs",
) -> str:
    from moviepy.editor import AudioFileClip, VideoFileClip

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    Path(outputs_dir).mkdir(parents=True, exist_ok=True)
    output_path = os.path.join(outputs_dir, f"output_{uuid.uuid4().hex[:8]}.mp4")

    video = None
    audio = None
    try:
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)

        # Match durations reasonably (MoviePy will trim/extend; extend can add silence depending on backend)
        if abs(audio.duration - video.duration) > 0.5:
            audio = audio.set_duration(video.duration)

        final = video.set_audio(audio)
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,
        )
        return output_path
    except Exception as e:
        raise RuntimeError(f"Video merging failed: {e}") from e
    finally:
        try:
            if audio is not None:
                audio.close()
        except Exception:
            pass
        try:
            if video is not None:
                video.close()
        except Exception:
            pass
