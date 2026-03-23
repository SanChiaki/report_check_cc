"""共享工具函数"""
import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)
MAX_IMAGE_SIZE = 2048  # Qwen3-VL 支持更大尺寸
MAX_IMAGE_BYTES = 1024 * 2048  # 2MB 最大图片大小


def detect_and_convert_format(data: bytes) -> tuple[str, bytes | None] | None:
    """检测图片格式并转换为支持的格式

    Args:
        data: 原始图片字节数据

    Returns:
        (格式名, 转换后的数据) 或 (格式名, None) 如果无需转换
        如果无法识别则返回 None
    """
    try:
        pil_img = Image.open(BytesIO(data))
    except Exception:
        return None

    fmt = (pil_img.format or "PNG").lower()

    # 检查原始数据大小
    original_size = len(data)

    # 缩放过大的图片并使用 JPEG 压缩
    needs_resize = max(pil_img.size) > MAX_IMAGE_SIZE
    needs_compress = original_size > MAX_IMAGE_BYTES

    if needs_resize or needs_compress:
        # 调整尺寸
        if needs_resize:
            pil_img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))

        # 尝试 JPEG 压缩（质量从高到低）
        for quality in [90, 75, 60]:
            buf = BytesIO()
            rgb_img = pil_img.convert("RGB") if pil_img.mode in ("RGBA", "P") else pil_img
            rgb_img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed = buf.getvalue()

            if len(compressed) <= MAX_IMAGE_BYTES:
                logger.debug(f"图片压缩: {original_size/1024:.1f}KB -> {len(compressed)/1024:.1f}KB (JPEG q={quality})")
                return ("jpeg", compressed)

        # 如果 JPEG 还是太大，强制缩放
        if len(compressed) > MAX_IMAGE_BYTES:
            scale = (MAX_IMAGE_BYTES / len(compressed)) ** 0.5 * 0.9
            new_size = (int(pil_img.width * scale), int(pil_img.height * scale))
            pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
            buf = BytesIO()
            rgb_img = pil_img.convert("RGB")
            rgb_img.save(buf, format="JPEG", quality=60)
            compressed = buf.getvalue()
            logger.debug(f"图片强制缩放: {original_size/1024:.1f}KB -> {len(compressed)/1024:.1f}KB")
            return ("jpeg", compressed)

        return ("jpeg", compressed)

    # 转换不支持的格式
    if fmt not in ("png", "jpeg", "jpg", "gif", "webp"):
        buf = BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        return ("jpeg", buf.getvalue())

    return (fmt, None)
