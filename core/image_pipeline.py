"""
core/image_pipeline.py — AI Image + Face-Swap Pipeline

Stage 1: Prompt enhancement  via Grok API  (x.ai)
Stage 2: Image generation    via FreeGen.app  (Playwright)
Stage 3: Face swap           via AIFaceSwap.io (Playwright)

All stages have fallbacks; pipeline continues if any stage fails.
API calls are tracked through utils.api_limiter.
"""

import asyncio
import base64
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import requests

from config.settings import GROK_API_KEY, IMAGES_DIR
from utils.api_limiter import check_and_increment, api_allowed
from utils.logger import get_logger

logger = get_logger("core.image_pipeline")


class ImagePipeline:
    """
    Three-stage AI image pipeline:
      1. Grok → enhanced prompt (+ optional direct image)
      2. FreeGen.app → generate image from prompt
      3. AIFaceSwap.io → swap AI face onto generated image
    """

    OUTPUT_DIR: Path = IMAGES_DIR

    def __init__(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Grok prompt enhancement ───────────────────────────────

    def enhance_prompt(self, base_idea: str) -> Tuple[str, Optional[str]]:
        """
        Returns: (enhanced_prompt, grok_image_url_or_None)
        If Grok returns an image URL, use it directly (skip FreeGen).
        """
        if not GROK_API_KEY:
            logger.debug("GROK_API_KEY not set — using base idea as prompt")
            return base_idea, None

        allowed, pct, reset = check_and_increment("GROK_API_KEY", amount=300)
        if not allowed:
            logger.warning(f"Grok rate-limited (resets {reset}) — using base idea")
            return base_idea, None

        try:
            resp = requests.post(
                "https://api.x.ai/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {GROK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": "grok-2-image", "prompt": base_idea},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                item = data.get("data", [{}])[0]
                revised  = item.get("revised_prompt", base_idea)
                img_url  = item.get("url")
                logger.info(f"Grok enhanced prompt ({pct*100:.0f}% used): {revised[:70]}…")
                return revised, img_url
            else:
                logger.warning(f"Grok API HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as exc:
            logger.error(f"Grok API exception: {exc}")

        return base_idea, None

    # ── Stage 2: FreeGen image generation ──────────────────────────────

    async def _freegen_async(self, prompt: str, aspect_ratio: str = "9:16") -> Optional[str]:
        try:
            from playwright.async_api import async_playwright, TimeoutError as PW_Timeout
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return None

        out = self.OUTPUT_DIR / f"freegen_{int(time.time())}.png"

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            ctx  = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            try:
                await page.goto("https://freegen.app/", timeout=30_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)

                # Locate prompt textarea
                area = await page.wait_for_selector(
                    'textarea, input[type="text"][placeholder]',
                    timeout=10_000,
                )
                await area.fill(prompt)

                # Optionally set aspect ratio (ignore if selector not found)
                try:
                    ar_sel = await page.query_selector(f'button:has-text("{aspect_ratio}")')
                    if ar_sel:
                        await ar_sel.click()
                except Exception:
                    pass

                # Click Generate
                btn = await page.wait_for_selector(
                    'button:has-text("Generate"), button[type="submit"]',
                    timeout=8_000,
                )
                await btn.click()

                # Wait for image (up to 35s)
                img = await page.wait_for_selector(
                    'img.generated, .output img, #result img, canvas',
                    timeout=35_000,
                )
                src = await img.get_attribute("src")
                if src:
                    if src.startswith("data:image"):
                        _, enc = src.split(",", 1)
                        out.write_bytes(base64.b64decode(enc))
                    else:
                        r = requests.get(src, timeout=20)
                        out.write_bytes(r.content)
                    logger.info(f"FreeGen image saved: {out}")
                    return str(out)

                # Last resort: screenshot the page
                await page.screenshot(path=str(out))
                return str(out)

            except PW_Timeout:
                logger.warning("FreeGen timed out — selector not found")
            except Exception as exc:
                logger.error(f"FreeGen automation error: {exc}")
            finally:
                await browser.close()

        return None

    def generate_image(self, prompt: str, aspect_ratio: str = "9:16") -> Optional[str]:
        """Synchronous wrapper around async FreeGen automation."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._freegen_async(prompt, aspect_ratio))
                    return future.result(timeout=60)
            return asyncio.run(self._freegen_async(prompt, aspect_ratio))
        except Exception as exc:
            logger.error(f"generate_image failed: {exc}")
            return None

    # ── Stage 3: AIFaceSwap face swap ───────────────────────────────────

    async def _faceswap_async(self, source_img: str, face_img: str) -> Optional[str]:
        try:
            from playwright.async_api import async_playwright, TimeoutError as PW_Timeout
        except ImportError:
            logger.error("Playwright not installed.")
            return None

        out = self.OUTPUT_DIR / f"faceswap_{int(time.time())}.png"

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx  = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            try:
                await page.goto("https://aifaceswap.io/", timeout=30_000)
                await page.wait_for_load_state("networkidle", timeout=15_000)

                inputs = await page.query_selector_all('input[type="file"]')
                if len(inputs) >= 2:
                    await inputs[0].set_input_files(source_img)  # original
                    await page.wait_for_timeout(1_500)
                    await inputs[1].set_input_files(face_img)    # face
                    await page.wait_for_timeout(1_500)
                elif len(inputs) == 1:
                    await inputs[0].set_input_files(source_img)

                # Click swap
                swap_btn = await page.wait_for_selector(
                    'button:has-text("Swap"), button:has-text("Face Swap"), '
                    'button:has-text("Start"), button[type="submit"]',
                    timeout=10_000,
                )
                await swap_btn.click()

                # Wait for result (up to 45s)
                result = await page.wait_for_selector(
                    '.result img, #result img, .output img, .swapped img',
                    timeout=45_000,
                )
                src = await result.get_attribute("src")
                if src:
                    if src.startswith("data:image"):
                        _, enc = src.split(",", 1)
                        out.write_bytes(base64.b64decode(enc))
                    else:
                        r = requests.get(src, timeout=20)
                        out.write_bytes(r.content)
                    logger.info(f"Face swap saved: {out}")
                    return str(out)

            except PW_Timeout:
                logger.warning("AIFaceSwap timed out")
            except Exception as exc:
                logger.error(f"Face swap error: {exc}")
            finally:
                await browser.close()

        return None

    def face_swap(self, source_img: str, face_img: str) -> Optional[str]:
        """Synchronous wrapper around async face-swap automation."""
        if not os.path.exists(source_img):
            logger.error(f"Source image not found: {source_img}")
            return None
        if not os.path.exists(face_img):
            logger.error(f"Face image not found: {face_img}")
            return None
        try:
            return asyncio.run(self._faceswap_async(source_img, face_img))
        except Exception as exc:
            logger.error(f"face_swap failed: {exc}")
            return None

    # ── Full pipeline ────────────────────────────────────────────────────

    def run(
        self,
        base_idea: str,
        face_image: Optional[str] = None,
        aspect_ratio: str = "9:16",
    ) -> Optional[str]:
        """
        Execute the full 3-stage pipeline.

        Args:
            base_idea:    The news headline / concept
            face_image:   Path to the AI model face photo (optional)
            aspect_ratio: "9:16" for Reels, "1:1" for feed posts

        Returns:
            Path to final image, or None if all stages fail.
        """
        logger.info(f"Image pipeline start: '{base_idea[:60]}…'")

        # Stage 1 — enhance prompt (+ optional Grok image)
        prompt, grok_img_url = self.enhance_prompt(base_idea)

        # Use Grok image directly if returned
        if grok_img_url:
            try:
                path = self.OUTPUT_DIR / f"grok_{int(time.time())}.png"
                r = requests.get(grok_img_url, timeout=20)
                path.write_bytes(r.content)
                source = str(path)
                logger.info(f"Grok image used directly: {source}")
            except Exception:
                source = None
        else:
            source = None

        # Stage 2 — FreeGen if no Grok image
        if not source:
            source = self.generate_image(prompt, aspect_ratio)

        if not source:
            logger.error("Image generation failed at both Grok and FreeGen stages")
            return None

        # Stage 3 — face swap (optional)
        if face_image:
            final = self.face_swap(source, face_image)
            if final:
                logger.info(f"Pipeline complete (with face swap): {final}")
                return final
            logger.warning("Face swap failed — returning un-swapped image")

        logger.info(f"Pipeline complete: {source}")
        return source
