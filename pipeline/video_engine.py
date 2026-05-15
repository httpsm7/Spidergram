"""
pipeline/video_engine.py
─────────────────────────
Step 7: Produce the final video reel.

Features:
  • Hook intro (2s animated title)
  • Scene-by-scene image slideshow
  • Background video support
  • Narration audio track
  • Background music
  • Fade transitions between scenes
  • Text overlays (headline + branding)
  • 1080×1920 vertical (Instagram Reels)
"""

import os
import textwrap
from pathlib import Path

from config.settings import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    VIDEO_DURATION_S, HOOK_DURATION_S, TEMP_DIR, VIDEO_DIR,
)
from database.models import GeneratedScript
from utils import get_logger, unique_id

logger = get_logger("pipeline.video_engine")

W, H = VIDEO_WIDTH, VIDEO_HEIGHT   # 1080×1920


def _get_moviepy():
    try:
        from moviepy.editor import (
            VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip,
            TextClip, ColorClip, concatenate_videoclips, CompositeAudioClip,
        )
        return dict(
            VideoFileClip=VideoFileClip, ImageClip=ImageClip,
            AudioFileClip=AudioFileClip, CompositeVideoClip=CompositeVideoClip,
            TextClip=TextClip, ColorClip=ColorClip,
            concatenate=concatenate_videoclips,
            CompositeAudioClip=CompositeAudioClip,
        )
    except ImportError as exc:
        logger.error(f"MoviePy not installed: {exc}")
        return None


def _resize_image(img_path: str) -> str:
    """Resize and crop image to 1080×1920 using Pillow."""
    try:
        from PIL import Image as PILImage
        img  = PILImage.open(img_path).convert("RGB")
        # Crop to 9:16 ratio
        img_ratio  = img.width / img.height
        target_ratio = W / H
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            left  = (img.width - new_w) // 2
            img   = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            top   = (img.height - new_h) // 2
            img   = img.crop((0, top, img.width, top + new_h))
        img   = img.resize((W, H))
        dest  = TEMP_DIR / f"resized_{unique_id()}.jpg"
        img.save(str(dest), "JPEG", quality=90)
        return str(dest)
    except Exception as exc:
        logger.warning(f"Image resize failed: {exc}")
        return img_path


def _make_hook_clip(headline: str, mp) -> object:
    """Create a 2-second animated hook clip with bold headline text."""
    bg   = mp["ColorClip"](size=(W, H), color=(15, 15, 15), duration=HOOK_DURATION_S)
    txt  = (mp["TextClip"](
                textwrap.fill(headline, width=30),
                fontsize=70, color="white", font="DejaVu-Sans-Bold",
                method="caption", size=(W - 80, None),
            )
            .set_position("center")
            .set_duration(HOOK_DURATION_S))
    breaking = (mp["TextClip"](
                "🔴 BREAKING NEWS",
                fontsize=40, color="#FF4444", font="DejaVu-Sans-Bold",
            )
            .set_position(("center", 200))
            .set_duration(HOOK_DURATION_S))
    return mp["CompositeVideoClip"]([bg, breaking, txt]).fadein(0.3)


def _make_image_scene(img_path: str, duration: float, mp) -> object:
    """Create a Ken-Burns-style image scene clip."""
    resized = _resize_image(img_path)
    clip    = (mp["ImageClip"](resized)
               .set_duration(duration)
               .fadein(0.4).fadeout(0.4))
    return clip


def _make_bg_video_scene(video_path: str, duration: float, mp) -> object:
    """Use a background video clip resized to portrait."""
    try:
        clip = (mp["VideoFileClip"](video_path)
                .without_audio()
                .subclip(0, min(duration, mp["VideoFileClip"](video_path).duration))
                .resize((W, H)))
        return clip
    except Exception as exc:
        logger.warning(f"BG video error: {exc}")
        return None


def produce_video(
    script:       GeneratedScript,
    image_paths:  list[str],
    audio_path:   str,
    bg_video:     str = "",
    bg_music:     str = "",
    headline:     str = "",
) -> str:
    """
    Assemble the final reel video.

    Returns local path to the output .mp4 file, or '' on failure.
    """
    mp = _get_moviepy()
    if not mp:
        return ""

    try:
        scenes   = []
        # ── Hook (2s) ──────────────────────────────────────────────────
        hook_clip = _make_hook_clip(headline or script.hook, mp)
        scenes.append(hook_clip)

        # ── Determine total body duration ──────────────────────────────
        body_duration = VIDEO_DURATION_S - HOOK_DURATION_S

        # ── Scenes from images or background video ─────────────────────
        if image_paths:
            per_scene = body_duration / max(len(image_paths), 1)
            for img in image_paths:
                scenes.append(_make_image_scene(img, per_scene, mp))
        elif bg_video:
            scene = _make_bg_video_scene(bg_video, body_duration, mp)
            if scene:
                scenes.append(scene)
            else:
                # Solid colour fallback
                scenes.append(mp["ColorClip"](size=(W, H), color=(20, 20, 30),
                                              duration=body_duration))
        else:
            scenes.append(mp["ColorClip"](size=(W, H), color=(20, 20, 30),
                                          duration=body_duration))

        # ── Concatenate ────────────────────────────────────────────────
        video = mp["concatenate"](scenes, method="compose")

        # ── Audio: narration ──────────────────────────────────────────
        audio_tracks = []
        if audio_path and Path(audio_path).exists():
            narr = mp["AudioFileClip"](audio_path).subclip(0, min(video.duration,
                    mp["AudioFileClip"](audio_path).duration))
            audio_tracks.append(narr)

        # ── Audio: background music (low volume) ─────────────────────
        if bg_music and Path(bg_music).exists():
            music = (mp["AudioFileClip"](bg_music)
                     .subclip(0, video.duration)
                     .volumex(0.12))
            audio_tracks.append(music)

        if audio_tracks:
            if len(audio_tracks) == 1:
                video = video.set_audio(audio_tracks[0])
            else:
                video = video.set_audio(mp["CompositeAudioClip"](audio_tracks))

        # ── Caption overlay (bottom banner) ───────────────────────────
        caption_txt = textwrap.fill(script.caption[:100], width=38)
        caption_clip = (
            mp["TextClip"](caption_txt, fontsize=32, color="white",
                           bg_color="rgba(0,0,0,0.6)", font="DejaVu-Sans",
                           method="caption", size=(W - 40, None))
            .set_position(("center", H - 220))
            .set_duration(video.duration)
        )
        video = mp["CompositeVideoClip"]([video, caption_clip])

        # ── Export ────────────────────────────────────────────────────
        out = VIDEO_DIR / f"reel_{unique_id()}.mp4"
        video.write_videofile(
            str(out),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            logger=None,
            verbose=False,
        )
        logger.info(f"Video produced: {out.name}")
        return str(out)

    except Exception as exc:
        logger.exception(f"Video production failed: {exc}")
        return ""
