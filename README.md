# Subtitle → Speech → Video (Streamlit)

This app takes a **video** and **subtitles (.srt)** and generates a new video with **speech aligned to subtitle timing**, including **correct pauses** between lines.

## Run locally

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure **ffmpeg** is installed and available on PATH.

3. Start the app:

```bash
streamlit run app.py
```

## Streamlit Community Cloud

- `requirements.txt` installs Python packages
- `packages.txt` installs system packages (this project uses `ffmpeg`)

## Notes

- Subtitle extraction from the video only works if the video contains embedded subtitle streams. For best reliability, **upload an `.srt` file**.
- Output files are written to `outputs/`. Temporary session files go to `temp/` and are cleaned up after each run (best effort).
