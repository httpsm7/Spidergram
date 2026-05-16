"""
pipeline/subtitle_engine.py
────────────────────────────
Step 8: Burn auto-generated subtitles onto the video using OpenCV + Pillow.
Splits script body into timed word chunks and renders them frame by frame.
"""

import math
import textwrap
from pathlib import Path

from config.settings import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, TEMP_DIR
from utils import get_logger, unique_id

logger = get_logger("pipeline.subtitle_engine")


def _split_into_chunks(text: str, words_per_chunk: int = 6) -> list[str]:
    """Split script text into short subtitle chunks."""
    words  = text.split()
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunks.append(" ".join(words[i:i + words_per_chunk]))
    return chunks


def add_subtitles_pillow(video_path: str, script_body: str,
                         audio_duration: float = 60.0) -> str:
    """
    Burn subtitles onto every frame of the video using Pillow + OpenCV.
    Returns path to the subtitled video, or original path on failure.
    """
    try:
        import cv2
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        logger.warning(f"OpenCV/Pillow not available for subtitles: {exc}")
        return video_path

    chunks        = _split_into_chunks(script_body)
    chunk_duration = audio_duration / max(len(chunks), 1)  # seconds per chunk

    try:
        cap    = cv2.VideoCapture(video_path)
        fps    = cap.get(cv2.CAP_PROP_FPS) or VIDEO_FPS
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        out_path = str(TEMP_DIR / f"subtitled_{unique_id()}.mp4")
        fourcc   = cv2.VideoWriter_fourcc(*"mp4v")
        writer   = cv2.VideoWriter(out_path, fourcc, fps, (width, height))

        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40
            )
        except OSError:
            font = ImageFont.load_default()

        frame_idx    = 0
        frames_per_chunk = int(fps * chunk_duration)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            chunk_idx = min(frame_idx // max(frames_per_chunk, 1), len(chunks) - 1)
            text      = chunks[chunk_idx] if chunks else ""

            if text:
                # Convert frame to PIL for text rendering
                img  = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(img)
                wrapped  = textwrap.fill(text, width=32)
                # Semi-transparent background band
                bbox  = draw.textbbox((0, 0), wrapped, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x     = (width - tw) // 2
                y     = height - th - 100
                draw.rectangle([x - 10, y - 10, x + tw + 10, y + th + 10],
                               fill=(0, 0, 0, 180))
                draw.text((x, y), wrapped, font=font, fill=(255, 255, 255))
                frame = cv2.cvtColor(
                    cv2.cvtColor(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), cv2.COLOR_RGB2BGR
                    ), cv2.COLOR_BGR2RGB
                )
                frame = cv2.cvtColor(
                    Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    .__array__(), cv2.COLOR_RGB2BGR
                )
                frame = cv2.cvtColor(
                    img.__array__(), cv2.COLOR_RGB2BGR
                )

            writer.write(frame)
            frame_idx += 1

        cap.release()
        writer.release()
        logger.info(f"Subtitles added: {Path(out_path).name}")
        return out_path

    except Exception as exc:
        logger.warning(f"Subtitle engine error: {exc} — returning original video.")
        return video_path


def add_subtitles_moviepy(video_path: str, script_body: str,
                          audio_duration: float = 60.0) -> str:
    """
    Alternative: add subtitles using MoviePy TextClips.
    Slower but cleaner rendering.
    """
    try:
        from moviepy.editor import (
            VideoFileClip, TextClip, CompositeVideoClip
        )
        chunks        = _split_into_chunks(script_body, words_per_chunk=5)
        chunk_dur     = audio_duration / max(len(chunks), 1)
        clip          = VideoFileClip(video_path)
        subtitle_clips = []

        for i, chunk in enumerate(chunks):
            t_start = i * chunk_dur
            t_end   = min(t_start + chunk_dur, clip.duration)
            txt     = (
                TextClip(chunk, fontsize=42, color="white",
                         bg_color="rgba(0,0,0,0.65)",
                         font="DejaVu-Sans-Bold", method="caption",
                         size=(clip.w - 60, None))
                .set_start(t_start)
                .set_end(t_end)
                .set_position(("center", clip.h - 180))
            )
            subtitle_clips.append(txt)

        final    = CompositeVideoClip([clip] + subtitle_clips)
        out_path = str(TEMP_DIR / f"subtitled_{unique_id()}.mp4")
        final.write_videofile(out_path, codec="libx264", audio_codec="aac",
                              logger=None, verbose=False)
        logger.info(f"MoviePy subtitles added: {Path(out_path).name}")
        return out_path
    except Exception as exc:
        logger.warning(f"MoviePy subtitle error: {exc}")
        return video_path
