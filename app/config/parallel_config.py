"""
Cấu hình cho parallel processing.
Điều chỉnh các giá trị này tùy theo plan API và hardware của bạn.
"""
import structlog

logger = structlog.get_logger(__name__)


from dataclasses import dataclass
from typing import Literal


@dataclass
class ParallelProcessingConfig:
    """Cấu hình chung cho parallel processing"""

    # ========== Threading Configuration ==========
    MAX_WORKERS: int = 10
    """Số lượng worker threads tối đa (10 workers phù hợp với 15 RPM)"""

    # ========== Rate Limiting Configuration ==========
    # Tham khảo: https://ai.google.dev/pricing
    RPM_LIMIT: int = 15
    """
    Requests Per Minute limit
    - Gemini Free tier: 15 RPM
    - Gemini Pro (paid): 360 RPM
    - OpenAI GPT-4: 500 RPM (tùy plan)
    """

    RPD_LIMIT: int = 1500
    """
    Requests Per Day limit
    - Gemini Free tier: 1500 RPD
    - Gemini Pro (paid): không giới hạn
    """

    # ========== Chunking Configuration ==========
    CHUNK_SIZE_SMALL: int = 15
    """Số trang/chunk cho PDF nhỏ (<50 trang)"""

    CHUNK_SIZE_LARGE: int = 30
    """Số trang/chunk cho PDF lớn (>=50 trang)"""

    CHUNK_SIZE_THRESHOLD: int = 50
    """Ngưỡng phân biệt PDF nhỏ/lớn"""

    # ========== Retry Configuration ==========
    RETRY_ATTEMPTS: int = 3
    """Số lần retry khi chunk parsing fail"""

    RETRY_DELAY: int = 2
    """Delay (seconds) giữa các retry"""

    RETRY_BACKOFF_MULTIPLIER: float = 2.0
    """Multiplier cho exponential backoff (2^n delay)"""

    # ========== Timeout Configuration ==========
    API_TIMEOUT: int = 60
    """Timeout (seconds) cho mỗi API call"""

    TOTAL_TIMEOUT: int = 3600
    """Timeout (seconds) cho toàn bộ quá trình parsing (1 giờ)"""

    # ========== Memory Configuration ==========
    MAX_CONCURRENT_CHUNKS_IN_MEMORY: int = 50
    """
    Số chunks tối đa được load vào memory cùng lúc
    Mỗi chunk ~5-10MB → 50 chunks = 250-500MB
    """

    ENABLE_MEMORY_OPTIMIZATION: bool = True
    """
    Bật tối ưu hóa memory (giải phóng chunks sau khi xử lý xong)
    """

    # ========== API Selection ==========
    DEFAULT_API: Literal["gemini", "openai"] = "gemini"
    """API mặc định để sử dụng"""

    FALLBACK_API: Literal["gemini", "openai", None] = "openai"
    """
    API dự phòng khi API chính fail
    Set None để disable fallback
    """

    # ========== Logging Configuration ==========
    ENABLE_VERBOSE_LOGGING: bool = True
    """Bật logging chi tiết"""

    LOG_FILE: str = "parallel_processing.log"
    """Đường dẫn file log"""

    ENABLE_PROGRESS_BAR: bool = True
    """Hiển thị progress bar với tqdm"""

    # ========== Output Configuration ==========
    SAVE_INTERMEDIATE_RESULTS: bool = False
    """
    Lưu kết quả từng chunk vào file riêng
    Hữu ích khi debug hoặc xử lý dataset rất lớn
    """

    INTERMEDIATE_OUTPUT_DIR: str = "./temp_chunks"
    """Thư mục lưu kết quả tạm thời của từng chunk"""

    # ========== Performance Optimization ==========
    ENABLE_CACHING: bool = True
    """
    Cache kết quả parsing để tránh xử lý lại chunks đã parse
    """

    CACHE_DIR: str = "./.cache/parsed_chunks"
    """Thư mục lưu cache"""

    CACHE_EXPIRY_DAYS: int = 7
    """Thời gian cache hết hạn (days)"""


@dataclass
class GeminiConfig:
    """Cấu hình riêng cho Gemini API"""

    MODEL_NAME: str = "gemini-2.0-flash-exp"
    """
    Gemini models:
    - gemini-2.0-flash-exp: Nhanh nhất, free 15 RPM
    - gemini-2.5-pro-exp-03-25: Chất lượng cao hơn
    - gemini-1.5-flash: Stable version
    """

    TEMPERATURE: float = 0.1
    """Temperature cho generation (0.0 = deterministic, 1.0 = creative)"""

    MAX_OUTPUT_TOKENS: int = 8192
    """Số tokens tối đa trong output"""

    SAFETY_SETTINGS: dict = None
    """Safety settings cho content filtering"""

    def __post_init__(self):
        if self.SAFETY_SETTINGS is None:
            from google.genai import types

            self.SAFETY_SETTINGS = {
                types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: types.HarmBlockThreshold.BLOCK_NONE,
                types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: types.HarmBlockThreshold.BLOCK_NONE,
                types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: types.HarmBlockThreshold.BLOCK_NONE,
                types.HarmCategory.HARM_CATEGORY_HARASSMENT: types.HarmBlockThreshold.BLOCK_NONE,
            }


@dataclass
class OpenAIConfig:
    """Cấu hình riêng cho OpenAI API"""

    MODEL_NAME: str = "gpt-4o-mini"
    """
    OpenAI models:
    - gpt-4o-mini: Rẻ, nhanh
    - gpt-4o: Chất lượng cao
    - gpt-4-turbo: Balance giữa speed và quality
    """

    TEMPERATURE: float = 0.1
    """Temperature cho generation"""

    MAX_TOKENS: int = 4096
    """Số tokens tối đa trong response"""

    TOP_P: float = 1.0
    """Nucleus sampling parameter"""


# ========== Presets ==========


class Presets:
    """Các preset cấu hình cho different use cases"""

    @staticmethod
    def free_tier():
        """Cấu hình tối ưu cho Free Tier (Gemini 15 RPM)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=50,  # Thấp để tránh hit rate limit
            RPM_LIMIT=500,
            RPD_LIMIT=1500,
            CHUNK_SIZE_SMALL=15,
            CHUNK_SIZE_LARGE=30,
            RETRY_ATTEMPTS=3,
            DEFAULT_API="gemini",
            FALLBACK_API=None,
        )

    @staticmethod
    def paid_tier():
        """Cấu hình cho Paid Tier (Gemini Pro/OpenAI)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=20,
            RPM_LIMIT=360,  # Gemini Pro
            RPD_LIMIT=None,
            CHUNK_SIZE_SMALL=10,
            CHUNK_SIZE_LARGE=20,
            RETRY_ATTEMPTS=2,
            DEFAULT_API="gemini",
            FALLBACK_API="openai",
        )

    @staticmethod
    def high_performance():
        """Cấu hình tối ưu performance (yêu cầu paid tier)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=30,
            RPM_LIMIT=500,
            CHUNK_SIZE_SMALL=8,
            CHUNK_SIZE_LARGE=15,
            RETRY_ATTEMPTS=2,
            ENABLE_CACHING=True,
            ENABLE_MEMORY_OPTIMIZATION=True,
            DEFAULT_API="openai",  # OpenAI thường nhanh hơn
        )

    @staticmethod
    def cost_optimized():
        """Cấu hình tối ưu chi phí (chunks lớn hơn, ít requests)"""
        return ParallelProcessingConfig(
            MAX_WORKERS=50,
            RPM_LIMIT=500,
            CHUNK_SIZE_SMALL=30,
            CHUNK_SIZE_LARGE=50,
            RETRY_ATTEMPTS=3,
            ENABLE_CACHING=True,
            DEFAULT_API="gemini",  # Gemini free/cheaper
        )

    @staticmethod
    def development():
        """Cấu hình cho development/testing"""
        return ParallelProcessingConfig(
            MAX_WORKERS=50,
            RPM_LIMIT=500,
            CHUNK_SIZE_SMALL=5,
            CHUNK_SIZE_LARGE=10,
            RETRY_ATTEMPTS=1,
            ENABLE_VERBOSE_LOGGING=True,
            SAVE_INTERMEDIATE_RESULTS=True,
            DEFAULT_API="gemini",
        )


# ========== Usage Examples ==========

if __name__ == "__main__":
    # Example 1: Sử dụng preset
    config = Presets.free_tier()
    logger.info("Free Tier Config:")
    logger.info(f"  Max Workers: {config.MAX_WORKERS}")
    logger.info(f"  RPM Limit: {config.RPM_LIMIT}")
    logger.info(f"  Chunk Size: {config.CHUNK_SIZE_LARGE}")

    # Example 2: Custom config
    custom_config = ParallelProcessingConfig(
        MAX_WORKERS=15,
        RPM_LIMIT=100,
        DEFAULT_API="openai",
        ENABLE_CACHING=True,
    )

    # Example 3: Override preset
    config = Presets.paid_tier()
    config.MAX_WORKERS = 25  # Override
    config.ENABLE_VERBOSE_LOGGING = False
