"""OCR engine abstraction layer supporting PaddleOCR and Tesseract."""

import numpy as np
from PIL import Image
from typing import List

from .ocr_types import OcrBlock, OcrResult


class OcrEngine:
    def __init__(self, engine_type: str = "paddleocr"):
        self.engine_type = engine_type
        self._engine = None
        if engine_type == "paddleocr":
            self._init_paddleocr()
        elif engine_type == "tesseract":
            self._init_tesseract()
        else:
            raise ValueError(f"Unsupported engine: {engine_type}")

    def _init_paddleocr(self):
        try:
            from paddleocr import PaddleOCR
            self._engine = PaddleOCR(
                use_angle_cls=True, lang="en", use_gpu=False
            )
        except ImportError:
            raise RuntimeError(
                "PaddleOCR not installed. Install with: pip install paddleocr paddlepaddle"
            )

    def _init_tesseract(self):
        try:
            import pytesseract
            self._engine = pytesseract
        except ImportError:
            raise RuntimeError(
                "pytesseract not installed. Install with: pip install pytesseract"
            )

    def recognize(
        self, images: List[Image.Image], embedded_text: str | None = None
    ) -> OcrResult:
        all_blocks: list[OcrBlock] = []

        for img in images:
            if self.engine_type == "paddleocr":
                blocks = self._recognize_paddleocr(img)
            else:
                blocks = self._recognize_tesseract(img)
            all_blocks.extend(blocks)

        full_text = "\n".join(b.text for b in all_blocks)
        return OcrResult(
            full_text=full_text, blocks=all_blocks, embedded_text=embedded_text
        )

    def _recognize_paddleocr(self, img: Image.Image) -> List[OcrBlock]:
        result = self._engine.ocr(np.array(img), cls=True)
        blocks: list[OcrBlock] = []
        if result and result[0]:
            for line in result[0]:
                bbox, (text, confidence) = line
                blocks.append(OcrBlock(text=text, confidence=confidence, bbox=bbox))
        return blocks

    def _recognize_tesseract(self, img: Image.Image) -> List[OcrBlock]:
        import pytesseract
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        blocks: list[OcrBlock] = []
        for i in range(len(data["text"])):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            conf = int(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.0
            x, y, w, h = (
                data["left"][i],
                data["top"][i],
                data["width"][i],
                data["height"][i],
            )
            bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            blocks.append(OcrBlock(text=text, confidence=conf, bbox=bbox))
        return blocks
