from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import streamlit as st

from utils.subtitle_utils import SubtitlePreparationError, extract_or_load_subtitles
from utils.tts_utils import generate_tts_audio
from utils.video_utils import merge_audio_with_video


def _ensure_dirs(*dirs: str) -> None:
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def _file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


def _save_upload(uploaded_file, dst_path: str) -> str:
    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, "wb") as f:
        f.write(uploaded_file.getvalue())
    return dst_path


def _cleanup_dir(path: str) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


st.set_page_config(page_title="Subtitle → Speech → Video", layout="centered")
st.title("Subtitle → Speech → Video")
st.caption(
    "This app generates a voiced video with pauses matching subtitle timings. "
    "For very large videos (e.g. 5GB), use **Local file path mode** instead of uploading."
)

with st.sidebar:
    st.subheader("Settings")
    language = st.text_input("gTTS language code", value="en", help="Examples: en, hi, fr, es, de, ja")
    st.write("Tip: for best results, upload an `.srt` file. Auto-extraction only works when the video contains subtitle streams.")

mode = st.radio(
    "Input mode",
    ["Upload (small videos)", "Local file path (large videos)"],
    index=0,
    help="Uploads load data into memory. For multi-GB videos, use local path mode.",
)

video_file = None
subtitle_file = None
local_video_path = ""

if mode == "Upload (small videos)":
    video_file = st.file_uploader("Upload video", type=["mp4", "mov", "mkv", "webm"])
    subtitle_file = st.file_uploader("Upload subtitles (.srt) (optional but recommended)", type=["srt"])
    allow_huge_upload = st.checkbox(
        "I understand large uploads may crash/hang; allow anyway",
        value=False,
        help="For multi-GB videos, Streamlit uploads can exhaust RAM or time out. Local file path mode is strongly recommended.",
    )
else:
    local_video_path = st.text_input("Local video path", placeholder=r"C:\path\to\video.mp4")
    subtitle_file = st.file_uploader("Upload subtitles (.srt) (recommended)", type=["srt"])

if st.button("Process video", type="primary"):
    session_id = uuid.uuid4().hex[:10]
    work_dir = os.path.join("temp", f"session_{session_id}")
    outputs_dir = "outputs"
    _ensure_dirs(work_dir, outputs_dir)

    try:
        if mode == "Upload (small videos)":
            if not video_file:
                st.error("Please upload a video file.")
                st.stop()

            # Guard: Streamlit uploads are memory-bound; multi-GB uploads will fail/hang.
            # (This checks reported upload size when available.)
            upload_size = getattr(video_file, "size", None)
            if upload_size is not None and upload_size > 1500 * 1024 * 1024 and not allow_huge_upload:
                st.error(
                    "This video is very large and uploads are often unreliable. "
                    "Enable the checkbox to force upload, or switch to **Local file path (large videos)** mode."
                )
                st.stop()
            if upload_size is not None and upload_size > 1500 * 1024 * 1024 and allow_huge_upload:
                st.warning(
                    "Proceeding with a very large upload. If this fails, use Local file path mode (recommended)."
                )

            video_path = os.path.join(work_dir, f"video_{Path(video_file.name).name}")
            _save_upload(video_file, video_path)
            display_name = Path(video_file.name).stem
        else:
            if not local_video_path:
                st.error("Please enter a local video path.")
                st.stop()
            if not os.path.exists(local_video_path):
                st.error(f"Video path not found: {local_video_path}")
                st.stop()
            if _file_size_mb(local_video_path) > 5000:
                st.warning("Large video detected. Processing may take a long time and require lots of disk space.")

            # Use the original file directly (no copy) to avoid doubling disk usage for multi-GB files.
            video_path = local_video_path
            display_name = Path(local_video_path).stem

        st.info("Preparing subtitles...")
        srt_path = extract_or_load_subtitles(video_path, subtitle_file=subtitle_file, work_dir=work_dir)
        st.success("Subtitles ready.")

        st.info("Generating speech (this can take a while)...")
        audio_path = generate_tts_audio(srt_path, language=language, work_dir=work_dir, outputs_dir=outputs_dir)
        st.success("Speech generated.")

        st.info("Merging audio into video...")
        output_video = merge_audio_with_video(video_path, audio_path, outputs_dir=outputs_dir)
        st.success("Done.")

        st.video(output_video)

        with open(output_video, "rb") as f:
            st.download_button(
                label="Download final video",
                data=f,
                file_name=f"voiced_{display_name}.mp4",
                mime="video/mp4",
            )

    except SubtitlePreparationError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Something went wrong:\n\n{e}")
        st.exception(e)
    finally:
        _cleanup_dir(work_dir)
