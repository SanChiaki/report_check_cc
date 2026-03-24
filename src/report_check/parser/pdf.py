"""PDF 报告解析器"""
import logging
from pathlib import Path
from io import BytesIO
from typing import TYPE_CHECKING
import fitz  # PyMuPDF
import pdfplumber
from report_check.parser.base import BaseParser
from report_check.parser.models import ContentBlock, ImageData, ReportData
from report_check.parser.utils import detect_and_convert_format

if TYPE_CHECKING:
    from report_check.storage.artifacts import TaskArtifacts

logger = logging.getLogger(__name__)
SCANNED_THRESHOLD = 50  # 每页少于50字符视为扫描件
DPI = 150  # 页面渲染 DPI


class PDFParser(BaseParser):
    """PDF 报告解析器，支持正常 PDF 和扫描件"""

    def __init__(self, artifacts: "TaskArtifacts | None" = None):
        """
        Args:
            artifacts: Optional TaskArtifacts instance for recording parse details
        """
        self.artifacts = artifacts

    def parse(self, file_path: str) -> ReportData:
        """解析 PDF 文件

        Args:
            file_path: PDF 文件路径

        Returns:
            ReportData: 解析后的报告数据
        """
        is_scanned = self._detect_scanned_pdf(file_path)

        if is_scanned:
            logger.info(f"Detected scanned PDF: {file_path}")
            return self._parse_scanned_pdf(file_path)
        else:
            logger.info(f"Detected normal PDF: {file_path}")
            return self._parse_normal_pdf(file_path)

    def _detect_scanned_pdf(self, file_path: str) -> bool:
        """检测是否为扫描件 PDF

        Args:
            file_path: PDF 文件路径

        Returns:
            bool: True 表示扫描件，False 表示正常 PDF
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                # 检查前3页或全部页面
                pages_to_check = min(3, len(pdf.pages))
                for i in range(pages_to_check):
                    text = pdf.pages[i].extract_text() or ""
                    if len(text.strip()) >= SCANNED_THRESHOLD:
                        return False
            return True
        except Exception as e:
            logger.warning(f"Error detecting PDF type: {e}, treating as scanned")
            return True

    def _parse_normal_pdf(self, file_path: str) -> ReportData:
        """解析正常 PDF（结构化文本提取）"""
        content_blocks = []
        images = []
        parse_metadata = {"type": "normal", "pages": []}

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_info = {"page": page_num, "text_chars": 0, "images": 0}

                # 提取文本
                text = page.extract_text() or ""
                if text.strip():
                    page_info["text_chars"] = len(text)
                    content_blocks.append(ContentBlock(
                        content=text,
                        location=f"page_{page_num}",
                        content_type="text",
                        metadata={"page": page_num, "extraction_method": "pdfplumber"},
                    ))

                # 提取图片
                page_images = self._extract_images_from_page(page, page_num)
                images.extend(page_images)
                page_info["images"] = len(page_images)
                parse_metadata["pages"].append(page_info)

        # Save parse metadata
        if self.artifacts:
            self.artifacts.save_parse_metadata(parse_metadata)

        return ReportData(
            file_name=Path(file_path).name,
            source_type="pdf",
            content_blocks=content_blocks,
            images=images,
            metadata={"page_count": len(pdf.pages), "is_scanned": False},
        )

    def _parse_scanned_pdf(self, file_path: str) -> ReportData:
        """解析扫描件 PDF（页面渲染为图片）"""
        content_blocks = []
        images = []
        parse_metadata = {"type": "scanned", "pages": [], "dpi": DPI}

        doc = fitz.open(file_path)
        page_count = len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            page_info = {"page": page_num + 1}

            # 渲染页面为图片
            pix = page.get_pixmap(dpi=DPI)
            img_data = pix.tobytes("png")

            # 转换格式
            fmt = detect_and_convert_format(img_data)
            if fmt:
                final_data = img_data if fmt[1] is None else fmt[1]
                final_format = fmt[0]

                images.append(ImageData(
                    id=f"page_{page_num + 1}",
                    data=final_data,
                    format=final_format,
                    anchor={"page": page_num + 1},
                    nearby_blocks=[],
                ))

                # Save page image to artifacts
                if self.artifacts:
                    self.artifacts.save_parsed_page(
                        page_num=page_num + 1,
                        data=final_data,
                        format=final_format,
                        metadata={"dpi": DPI, "width": pix.width, "height": pix.height}
                    )

                page_info["rendered"] = True
                page_info["width"] = pix.width
                page_info["height"] = pix.height
                page_info["format"] = final_format

            # 创建占位内容块
            content_blocks.append(ContentBlock(
                content=f"[Scanned page {page_num + 1}]",
                location=f"page_{page_num + 1}",
                content_type="image",
                metadata={"page": page_num + 1, "extraction_method": "pymupdf_render"},
            ))

            parse_metadata["pages"].append(page_info)

        doc.close()

        # Save parse metadata
        if self.artifacts:
            self.artifacts.save_parse_metadata(parse_metadata)

        return ReportData(
            file_name=Path(file_path).name,
            source_type="pdf",
            content_blocks=content_blocks,
            images=images,
            metadata={"page_count": page_count, "is_scanned": True},
        )

    def _extract_images_from_page(self, page, page_num: int) -> list[ImageData]:
        """从 pdfplumber 页面提取图片"""
        images = []

        try:
            for i, img_obj in enumerate(page.images):
                # 获取图片数据
                img_data = self._get_pdfplumber_image_data(page, img_obj)
                if not img_data:
                    continue

                # 转换格式
                fmt = detect_and_convert_format(img_data)
                if not fmt:
                    continue

                final_data = img_data if fmt[1] is None else fmt[1]
                final_format = fmt[0]

                image_id = f"page_{page_num}_img_{i}"
                images.append(ImageData(
                    id=image_id,
                    data=final_data,
                    format=final_format,
                    anchor={"page": page_num, "x0": img_obj.get("x0"), "y0": img_obj.get("y0")},
                    nearby_blocks=[],
                ))

                # Save image to artifacts
                if self.artifacts:
                    self.artifacts.save_parsed_image(
                        image_id=image_id,
                        data=final_data,
                        format=final_format,
                        metadata={
                            "page": page_num,
                            "x0": img_obj.get("x0"),
                            "y0": img_obj.get("y0"),
                            "width": img_obj.get("width"),
                            "height": img_obj.get("height"),
                        }
                    )
        except Exception as e:
            logger.warning(f"Failed to extract images from page {page_num}: {e}")

        return images

    def _get_pdfplumber_image_data(self, page, img_obj) -> bytes | None:
        """获取 pdfplumber 图片对象的字节数据"""
        try:
            # pdfplumber 的图片对象包含 stream 属性
            if hasattr(img_obj, "stream"):
                return img_obj.stream.get_data()

            # 尝试从页面对象获取
            if "stream" in img_obj:
                return img_obj["stream"].get_data()

        except Exception as e:
            logger.warning(f"Cannot extract image data: {e}")

        return None

