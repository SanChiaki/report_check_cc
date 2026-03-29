"""MSG 邮件解析器"""
import logging
from pathlib import Path
from typing import Optional
import extract_msg

from report_check.parser.base import BaseParser
from report_check.parser.models import ReportData, ContentBlock, ImageData
from report_check.parser.pdf import PDFParser
from report_check.parser.excel import ExcelParser

logger = logging.getLogger(__name__)


class MSGParser(BaseParser):
    """MSG 邮件解析器

    解析邮件正文和附件（PDF/Excel），将内容统一为 ReportData 格式
    """

    def __init__(self):
        self.pdf_parser = PDFParser()
        self.excel_parser = ExcelParser()

    def parse(self, file_path: str) -> ReportData:
        """解析 MSG 邮件文件

        Args:
            file_path: MSG 文件路径

        Returns:
            ReportData: 解析后的报告数据（包含邮件正文和附件内容）
        """
        msg_path = Path(file_path)
        logger.info(f"开始解析 MSG 文件: {msg_path}")

        try:
            msg = extract_msg.Message(str(msg_path))

            content_blocks = []
            images = []
            metadata = {
                "subject": msg.subject or "",
                "sender": msg.sender or "",
                "to": msg.to or "",
                "date": str(msg.date) if msg.date else "",
                "cc": msg.cc or "",
                "attachments_count": len(msg.attachments),
            }

            # 1. 解析邮件正文
            body = msg.body or ""
            if body.strip():
                content_blocks.append(
                    ContentBlock(
                        content=body,
                        location="email_body",
                        content_type="text",
                        metadata={"source": "email_body"},
                    )
                )
                logger.info(f"解析邮件正文: {len(body)} 字符")

            # 2. 解析附件
            attachment_data = []
            temp_dir = None
            for i, attachment in enumerate(msg.attachments):
                att_name = attachment.longFilename or attachment.shortFilename or f"attachment_{i}"
                logger.info(f"发现附件 {i+1}/{len(msg.attachments)}: {att_name}")

                # 保存附件到临时文件
                if temp_dir is None:
                    temp_dir = msg_path.parent / f".temp_{msg_path.stem}"
                    temp_dir.mkdir(exist_ok=True)
                att_path = temp_dir / att_name

                try:
                    attachment.save(customPath=str(temp_dir), customFilename=att_name)

                    # 根据附件类型解析
                    if att_name.lower().endswith((".pdf",)):
                        logger.info(f"解析 PDF 附件: {att_name}")
                        att_data = self.pdf_parser.parse(str(att_path))
                        attachment_data.append((att_name, att_data))

                    elif att_name.lower().endswith((".xlsx", ".xls")):
                        logger.info(f"解析 Excel 附件: {att_name}")
                        att_data = self.excel_parser.parse(str(att_path))
                        attachment_data.append((att_name, att_data))

                    else:
                        logger.warning(f"跳过不支持的附件类型: {att_name}")

                except Exception as e:
                    logger.error(f"解析附件 {att_name} 失败: {e}")
                finally:
                    # 清理临时文件
                    if att_path.exists():
                        att_path.unlink()

            # 清理临时目录
            if temp_dir and temp_dir.exists():
                temp_dir.rmdir()

            # 3. 合并附件内容
            for att_name, att_data in attachment_data:
                # 为附件内容添加来源标记
                for block in att_data.content_blocks:
                    block.location = f"attachment:{att_name}:{block.location}"
                    block.metadata["source"] = "attachment"
                    block.metadata["attachment_name"] = att_name
                content_blocks.extend(att_data.content_blocks)

                # 合并图片
                for img in att_data.images:
                    img.id = f"attachment:{att_name}:{img.id}"
                    img.anchor["source"] = "attachment"
                    img.anchor["attachment_name"] = att_name
                images.extend(att_data.images)

            msg.close()

            logger.info(
                f"MSG 解析完成: {len(content_blocks)} 个内容块, "
                f"{len(images)} 张图片, {len(attachment_data)} 个附件"
            )

            return ReportData(
                file_name=msg_path.name,
                source_type="email",
                content_blocks=content_blocks,
                images=images,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"解析 MSG 文件失败: {e}")
            raise RuntimeError(f"MSG 解析失败: {e}") from e

