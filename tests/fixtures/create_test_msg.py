"""创建测试用的 MSG 文件

由于 extract_msg 库主要用于读取而非创建 MSG 文件，
这个脚本提供了创建测试 MSG 文件的说明和替代方案。
"""

import os
from pathlib import Path

# 测试文件目录
FIXTURES_DIR = Path(__file__).parent
TEST_MSG_PATH = FIXTURES_DIR / "test_email.msg"

def create_simple_msg():
    """
    创建简单的测试 MSG 文件

    注意：由于 Python 没有直接创建 MSG 的库，建议使用以下方法之一：

    方法 1：使用 Outlook 创建
    1. 打开 Outlook
    2. 创建新邮件：
       - 主题：测试质检报告
       - 发件人：test@example.com
       - 收件人：receiver@example.com
       - 正文：这是一封测试邮件，包含质检报告内容。
       - 附件：添加一个 PDF 或 Excel 文件
    3. 另存为 .msg 格式

    方法 2：使用现有的 MSG 文件
    - 从邮箱导出任意邮件为 .msg 格式

    方法 3：使用在线工具
    - 使用 EML 转 MSG 工具（如果有 .eml 文件）
    """

    print(f"测试 MSG 文件应保存到: {TEST_MSG_PATH}")
    print("\n创建方法：")
    print("1. 使用 Outlook 创建邮件并另存为 .msg")
    print("2. 从邮箱导出现有邮件")
    print("3. 使用 tests/fixtures/sample_email_template.txt 作为参考")

    # 创建邮件模板文本
    template = """
邮件模板参考
====================

主题: 测试质检报告
发件人: test@example.com
收件人: receiver@example.com
日期: 2024-01-15 10:00:00

正文:
这是一封测试邮件，用于验证报告检查系统。

邮件包含以下内容：
1. 质检报告已完成
2. 所有检查项均已通过
3. 详细数据请查看附件

附件建议:
- report.pdf (包含质检结果)
- data.xlsx (包含检测数据)

====================
"""

    template_path = FIXTURES_DIR / "sample_email_template.txt"
    template_path.write_text(template, encoding="utf-8")
    print(f"\n已创建邮件模板: {template_path}")

    return template_path


if __name__ == "__main__":
    create_simple_msg()
