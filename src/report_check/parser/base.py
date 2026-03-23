"""解析器基类"""
from abc import ABC, abstractmethod
from report_check.parser.models import ReportData


class BaseParser(ABC):
    """报告解析器基类"""

    @abstractmethod
    def parse(self, file_path: str) -> ReportData:
        """解析报告文件

        Args:
            file_path: 文件路径

        Returns:
            ReportData: 解析后的报告数据
        """
        pass
