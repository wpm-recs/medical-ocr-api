"""OCR engine abstraction layer using PaddleOCR only."""

import numpy as np
from PIL import Image
from typing import List, Optional

from .ocr_types import OcrBlock, OcrResult


class OcrEngine:
    def __init__(self, engine_type: str = "paddleocr"):
        if engine_type != "paddleocr":
            raise ValueError(f"Unsupported engine: {engine_type}")
        self.engine_type = engine_type
        self._engine = None
        self._init_paddleocr()

    def _init_paddleocr(self):
        try:
            from paddleocr import PaddleOCR

            self._engine = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
        except ImportError:
            raise RuntimeError(
                "PaddleOCR not installed. Install with: pip install paddleocr paddlepaddle"
            )

    def recognize(
        self, images: List[Image.Image], embedded_text: Optional[str] = None
    ) -> OcrResult:
        all_blocks: list[OcrBlock] = []

        for img in images:
            blocks = self._recognize_paddleocr(img)
            all_blocks.extend(blocks)

        full_text = "\n".join(b.text for b in all_blocks)
        return OcrResult(
            full_text=full_text, blocks=all_blocks, embedded_text=embedded_text
        )

    def _recognize_paddleocr(self, img: Image.Image) -> List[OcrBlock]:
        # PaddleOCR requires RGB (3-channel) images
        if img.mode != "RGB":
            img = img.convert("RGB")
        result = self._engine.ocr(np.array(img), cls=True)
        blocks: list[OcrBlock] = []
        if result and result[0]:
            for line in result[0]:
                bbox, (text, confidence) = line
                blocks.append(OcrBlock(text=text, confidence=confidence, bbox=bbox))
        return blocks
