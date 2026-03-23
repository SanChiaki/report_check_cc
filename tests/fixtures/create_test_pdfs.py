#!/usr/bin/env python3
"""
创建测试 PDF 文件
使用 PyMuPDF (fitz) 创建各种测试场景的 PDF
"""

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io
from pathlib import Path

output_dir = Path(__file__).parent

def create_normal_pdf():
    """创建正常 PDF（有文本层）"""
    print("创建正常 PDF...")

    pdf_path = output_dir / "telecom_report_normal.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # 添加标题
    page.insert_text((50, 50), "中国电信 5G 网络建设进展报告",
                     fontsize=16, fontname="helv", color=(0, 0, 0))

    # 添加内容
    y = 100
    content = [
        "项目名称: 华东区域 5G 覆盖提升工程",
        "报告周期: 2026-03-01 至 2026-03-18",
        "建设单位: 中国电信某地市分公司",
        "总包单位: 智联通信工程有限公司",
        "",
        "本期进展:",
        "- 完成核心机房设备安装巡检",
        "- 南城区 3 号塔位已完成主体完工",
        "",
        "当前状态: 机房侧已完成联调准备",
        "下阶段计划: 开展站点通电与联调测试",
        "风险提示: 雨天可能影响外场割接窗口",
        "跟进事项: 继续跟踪塔下供电接入审批",
    ]

    for line in content:
        page.insert_text((50, y), line, fontsize=11, fontname="helv")
        y += 20

    # 添加现场照片（真实的图片，不是矩形框）
    y += 20
    page.insert_text((50, y), "现场照片:", fontsize=12, fontname="helv")
    y += 25

    # 创建一个模拟的设备安装现场照片
    img = Image.new('RGB', (500, 300), color='#f5f5f0')  # 浅灰背景
    draw = ImageDraw.Draw(img)

    # 绘制基站塔架
    # 塔身
    draw.rectangle([240, 50, 260, 250], fill='#666666', outline='#444444', width=2)
    # 天线（三个扇区）
    for i, angle in enumerate([-30, 0, 30]):
        x_offset = (i - 1) * 40
        draw.rectangle([220 + x_offset, 80, 280 + x_offset, 100],
                      fill='#228b22', outline='#1a6b1a', width=1)
    # 地面设备箱
    draw.rectangle([100, 200, 200, 280], fill='#4169e1', outline='#27408b', width=2)
    draw.text((120, 230), "设备箱", fill='white')
    # 标识牌
    draw.rectangle([350, 220, 450, 260], fill='white', outline='black', width=2)
    draw.text((360, 235), "5G基站 #3", fill='black')
    # 添加噪点模拟真实照片
    import random
    for _ in range(500):
        x = random.randint(0, img.width - 1)
        y = random.randint(0, img.height - 1)
        draw.point((x, y), fill=(230, 230, 230))

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    rect = fitz.Rect(50, y, 350, y + 210)
    page.insert_image(rect, stream=img_buffer.getvalue())
    page.insert_text((50, y + 220), "图1: 南城区3号基站设备安装现场", fontsize=10)

    doc.save(str(pdf_path))
    doc.close()
    print(f"✓ 创建完成: {pdf_path}")
    return pdf_path


def create_scanned_pdf():
    """创建扫描件 PDF（纯图片，无文本层）"""
    print("创建扫描件 PDF...")

    pdf_path = output_dir / "telecom_report_scanned.pdf"
    doc = fitz.open()

    # 创建一个看起来像扫描件的图片
    img = Image.new('RGB', (1654, 2339), color='white')  # A4 at 200 DPI
    draw = ImageDraw.Draw(img)

    # 添加噪点模拟扫描效果
    import random
    for _ in range(1000):
        x = random.randint(0, img.width - 1)
        y = random.randint(0, img.height - 1)
        draw.point((x, y), fill=(245, 245, 245))

    # 使用默认字体绘制文本（作为图片）
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # 标题
    draw.text((100, 100), "5G Network Progress Report", fill='black', font=font_title)

    # 内容
    y = 250
    lines = [
        "Project: East Region 5G Coverage",
        "Period: 2026-03-01 to 2026-03-18",
        "Status: Equipment installation completed",
        "Tower: South district #3 completed",
        "Next: Site power-on and testing",
        "Risk: Weather may affect schedule",
    ]

    for line in lines:
        draw.text((100, y), line, fill='black', font=font_body)
        y += 80

    # 添加照片区域
    y += 50
    draw.rectangle([100, y, 800, y + 400], outline='black', width=3)
    draw.text((300, y + 180), "[Site Photo]", fill='gray', font=font_body)

    # 将图片转为 PDF
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=img_buffer.getvalue())

    doc.save(str(pdf_path))
    doc.close()
    print(f"✓ 创建完成: {pdf_path}")
    return pdf_path


def create_mixed_pdf():
    """创建混合 PDF（文本 + 嵌入图片）"""
    print("创建混合 PDF...")

    pdf_path = output_dir / "telecom_report_mixed.pdf"
    doc = fitz.open()

    # 第一页：文本
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 50), "5G Network Construction Report",
                      fontsize=16, fontname="helv")

    y = 100
    content = [
        "Project: East Region 5G Coverage Enhancement",
        "Construction Unit: China Telecom Regional Branch",
        "Report Period: 2026-03-01 to 2026-03-18",
        "",
        "Progress Summary:",
        "- Core equipment installation: Completed",
        "- Tower construction: 3 sites completed",
        "- Network testing: In progress",
        "",
        "Current Status:",
        "Equipment room setup completed.",
        "South district tower #3 finished.",
        "",
        "Next Steps:",
        "1. Conduct site power-on testing",
        "2. Perform network integration tests",
        "3. Complete final acceptance",
    ]

    for line in content:
        page1.insert_text((50, y), line, fontsize=10, fontname="helv")
        y += 18

    # 第二页：嵌入图片
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 50), "Site Installation Photos",
                      fontsize=14, fontname="helv")

    # 创建一个示例图片
    img = Image.new('RGB', (600, 400), color='lightblue')
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 590, 390], outline='darkblue', width=5)
    draw.text((200, 180), "Equipment Room", fill='darkblue')
    draw.text((160, 210), "Installation Complete", fill='darkblue')

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    rect = fitz.Rect(50, 100, 500, 400)
    page2.insert_image(rect, stream=img_buffer.getvalue())
    page2.insert_text((50, 420), "Figure 1: Core equipment installation", fontsize=10)

    doc.save(str(pdf_path))
    doc.close()
    print(f"✓ 创建完成: {pdf_path}")
    return pdf_path


def create_blank_pdf():
    """创建空白 PDF（边界测试）"""
    print("创建空白 PDF...")

    pdf_path = output_dir / "blank.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)  # 空白页
    doc.save(str(pdf_path))
    doc.close()

    print(f"✓ 创建完成: {pdf_path}")
    return pdf_path


def create_text_heavy_pdf():
    """创建文本密集型 PDF（测试文本提取性能）"""
    print("创建文本密集型 PDF...")

    pdf_path = output_dir / "text_heavy.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text((50, 50), "Technical Specification Document",
                     fontsize=14, fontname="helv")

    y = 80
    for section in range(1, 6):
        page.insert_text((50, y), f"Section {section}: Network Configuration",
                        fontsize=11, fontname="helv")
        y += 20

        for para in range(8):
            text = f"Para {para + 1}: Detailed technical description of network " \
                   f"configuration parameters and settings. System supports " \
                   f"multiple protocols and interfaces for connectivity."
            page.insert_text((50, y), text[:80], fontsize=9, fontname="helv")
            y += 12

            if y > 800:
                page = doc.new_page(width=595, height=842)
                y = 50

    doc.save(str(pdf_path))
    doc.close()
    print(f"✓ 创建完成: {pdf_path}")
    return pdf_path


def create_multipage_scanned_pdf():
    """创建多页扫描件 PDF"""
    print("创建多页扫描件 PDF...")

    pdf_path = output_dir / "multipage_scanned.pdf"
    doc = fitz.open()

    for page_num in range(1, 4):
        # 为每页创建扫描图片
        img = Image.new('RGB', (1654, 2339), color='white')
        draw = ImageDraw.Draw(img)

        # 噪点
        import random
        for _ in range(500):
            x = random.randint(0, img.width - 1)
            y = random.randint(0, img.height - 1)
            draw.point((x, y), fill=(245, 245, 245))

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        except:
            font = ImageFont.load_default()

        # 页码和内容
        draw.text((100, 100), f"Page {page_num} - Scanned Document", fill='black', font=font)
        draw.text((100, 200), f"This is page {page_num} of the report", fill='black', font=font)

        # 转为 PDF 页
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        page = doc.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=img_buffer.getvalue())

    doc.save(str(pdf_path))
    doc.close()
    print(f"✓ 创建完成: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    print("开始创建测试 PDF 文件...\n")

    # 创建各种测试 PDF
    create_normal_pdf()
    create_scanned_pdf()
    create_mixed_pdf()
    create_blank_pdf()
    create_text_heavy_pdf()
    create_multipage_scanned_pdf()

    print("\n✓ 所有测试 PDF 文件创建完成!")
    print(f"输出目录: {output_dir}")
    print("\n测试文件列表:")
    for pdf_file in sorted(output_dir.glob("*.pdf")):
        size_kb = pdf_file.stat().st_size / 1024
        print(f"  - {pdf_file.name} ({size_kb:.1f} KB)")
