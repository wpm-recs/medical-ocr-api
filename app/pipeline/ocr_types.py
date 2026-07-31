"""OCR text result data class."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OcrBlock:
    """Represents a single OCR'd text block with bounding box and confidence."""

    text: str
    confidence: float
    bbox: List[List[float]]  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]


@dataclass
class OcrResult:
    """Result from OCR engine containing full text and individual blocks."""

    full_text: str
    blocks: List[OcrBlock] = field(default_factory=list)
    embedded_text: Optional[str] = None
