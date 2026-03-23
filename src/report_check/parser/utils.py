"""共享工具函数"""
import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)
MAX_IMAGE_SIZE = 2048


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

    # 缩放过大的图片
    if max(pil_img.size) > MAX_IMAGE_SIZE:
        pil_img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return ("png", buf.getvalue())

    # 转换不支持的格式
    if fmt not in ("png", "jpeg", "jpg", "gif", "webp"):
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return ("png", buf.getvalue())

    return (fmt, None)
