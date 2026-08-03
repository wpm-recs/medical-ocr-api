"""Application configuration via environment variables."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    ocr_engine: str = field(
        default_factory=lambda: os.getenv("OCR_ENGINE", "paddleocr")
    )
    max_file_size: int = field(
        default_factory=lambda: int(os.getenv("MAX_FILE_SIZE", "20971520"))
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    llm_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("LLM_API_KEY")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o")
    )
    llm_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL")
    )
    llm_max_input_chars: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_INPUT_CHARS", "8000"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "1024"))
    )
    cache_enabled: bool = field(
        default_factory=lambda: os.getenv("CACHE_ENABLED", "false").lower() == "true"
    )
    gpu_enabled: bool = field(
        default_factory=lambda: os.getenv("GPU_ENABLED", "false").lower() == "true"
    )
    app_version: str = "1.0.0"

    # OCR DPI for pdf2image
    ocr_dpi: int = 300

    # Thread pool size for OCR workers
    max_ocr_workers: int = 4


config = Config()