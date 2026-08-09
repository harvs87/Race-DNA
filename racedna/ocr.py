from __future__ import annotations

from pathlib import Path


def ocr_image(path: str | Path, psm: int = 6) -> str:
    """OCR a sectional screenshot with light preprocessing for table text."""
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OCR requires pillow and pytesseract. Install with: "
            'python3 -m pip install "racedna[ocr]"'
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
