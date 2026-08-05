"""OCR engine abstraction layer using Tesseract via pytesseract.

This implementation returns the same `OcrResult` structure expected
by the rest of the codebase.
"""

from PIL import Image
from typing import List, Optional

from .ocr_types import OcrBlock, OcrResult


class OcrEngine:
    def __init__(self, engine_type: str = "tesseract"):
        if engine_type != "tesseract":
            raise ValueError(f"Unsupported engine: {engine_type}")
        self.engine_type = engine_type

    def recognize(self, images: List[Image.Image], embedded_text: Optional[str] = None) -> OcrResult:
        """Run pytesseract on a list of PIL Images and return OcrResult."""
        all_blocks: List[OcrBlock] = []

        try:
            import pytesseract
        except ImportError as e:
            raise RuntimeError("pytesseract not installed. Install with: pip install pytesseract") from e

        for img in images:
            # Ensure image is in a mode pytesseract accepts
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            for i in range(len(data.get("text", []))):
                text = (data["text"][i] or "").strip()
                if not text:
                    continue
                conf_raw = data.get("conf", [])[i]
                try:
                    conf_f = float(conf_raw)
                    conf = 0.0 if conf_f == -1 else conf_f / 100.0
                except Exception:
                    conf = 0.0

                x = data.get("left", [])[i]
                y = data.get("top", [])[i]
                w = data.get("width", [])[i]
                h = data.get("height", [])[i]
                bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                all_blocks.append(OcrBlock(text=text, confidence=conf, bbox=bbox))

        full_text = "\n".join(b.text for b in all_blocks)
        return OcrResult(full_text=full_text, blocks=all_blocks, embedded_text=embedded_text)
