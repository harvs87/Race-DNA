from __future__ import annotations

from pathlib import Path


class OcrUnavailable(RuntimeError):
    """Raised when screenshot OCR cannot run (missing deps / tesseract)."""


def ocr_available() -> bool:
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    try:
        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001
        return False
    return True


def ocr_image(path: str | Path, psm: int = 6) -> str:
    """OCR a sectional screenshot with light preprocessing for table text."""
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise OcrUnavailable(
            "OCR requires pillow and pytesseract. Install with: "
            'python3 -m pip install -e ".[ocr]"'
        ) from exc

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:  # noqa: BLE001
        raise OcrUnavailable(
            "System Tesseract not found. On Mac: brew install tesseract. "
            "Or pick the horse + run style in the form — screenshot still saves."
        ) from exc

    path = Path(path)
    image = Image.open(path)
    # Upscale small phone screenshots for better glyph separation
    min_width = 1600
    if image.width < min_width:
        scale = min_width / image.width
        image = image.resize(
            (int(image.width * scale), int(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.SHARPEN)
    # Mild threshold helps dense PF tables
    bw = gray.point(lambda x: 255 if x > 175 else 0)
    config = f"--psm {psm} -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(bw, config=config)
    if len(text.strip()) < 40:
        # Fallback without thresholding
        text = pytesseract.image_to_string(gray, config=config)
    return text
