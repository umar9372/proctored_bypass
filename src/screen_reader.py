"""
screen_reader.py — Screenshot capture + OCR engine
MTech Thesis: Proctoring Vulnerability Research — Phase 1

Uses mss for fast screen capture (bypasses OS screenshot restrictions).
Supports pytesseract (if Tesseract installed) or easyocr (pure Python).
"""

import os
import shutil
from PIL import Image

TESSERACT_WINDOWS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
    r"C:\tesseract\tesseract.exe",
]


class ScreenReader:
    def __init__(self):
        self._tesseract_ok = self._check_tesseract()
        self._easy_reader  = None   # lazy-loaded

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def capture_region(self, x: int, y: int, w: int, h: int) -> Image.Image:
        """Grab a pixel rectangle from the screen and return a PIL Image."""
        import mss
        with mss.mss() as sct:
            monitor = {"left": x, "top": y, "width": w, "height": h}
            raw = sct.grab(monitor)
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    def capture_fullscreen(self) -> Image.Image:
        """Grab the primary monitor."""
        import mss
        with mss.mss() as sct:
            raw = sct.grab(sct.monitors[1])
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    def extract_text(self, image: Image.Image) -> str:
        """Run OCR on a PIL image. Returns extracted text string."""
        # Preprocess: upscale small images for better OCR accuracy
        w, h = image.size
        if w < 400 or h < 100:
            scale = max(2, 400 // w)
            image = image.resize((w * scale, h * scale), Image.LANCZOS)

        if self._tesseract_ok:
            return self._tesseract(image)
        return self._easyocr(image)

    def ocr_available(self) -> str:
        """Returns which OCR engine is active."""
        if self._tesseract_ok:
            return "Tesseract"
        try:
            import easyocr  # noqa
            return "EasyOCR"
        except ImportError:
            return "None"

    # ──────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────

    def _check_tesseract(self) -> bool:
        try:
            import pytesseract
            if shutil.which("tesseract"):
                pytesseract.get_tesseract_version()
                return True

            for candidate in TESSERACT_WINDOWS_PATHS:
                if os.path.isfile(candidate):
                    pytesseract.pytesseract.tesseract_cmd = candidate
                    pytesseract.get_tesseract_version()
                    return True
            return False
        except Exception:
            return False

    def _tesseract(self, image: Image.Image) -> str:
        import pytesseract
        config = "--oem 3 --psm 6"   # Assume uniform block of text
        return pytesseract.image_to_string(image, config=config).strip()

    def _easyocr(self, image: Image.Image) -> str:
        try:
            import easyocr
            import numpy as np

            if self._easy_reader is None:
                # First load downloads ~100 MB model once
                self._easy_reader = easyocr.Reader(["en"], gpu=False, verbose=False)

            arr = np.array(image)
            results = self._easy_reader.readtext(arr, detail=0, paragraph=True)
            return "\n".join(results).strip()

        except ImportError:
            return (
                "⚠ No OCR engine found.\n"
                "Install one:\n"
                "  pip install pytesseract   (+ Tesseract binary)\n"
                "  pip install easyocr"
            )
