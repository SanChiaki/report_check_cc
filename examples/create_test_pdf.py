"""创建简单的测试 PDF 文件"""
import fitz  # PyMuPDF

# 创建一个简单的测试 PDF
doc = fitz.open()
page = doc.new_page(width=595, height=842)  # A4 size

# 添加标题
page.insert_text((50, 50), "电信项目进度报告", fontsize=20, color=(0, 0, 0))

# 添加内容
content = """
项目编号: PROJ-2024-001
项目名称: 5G基站建设项目
完成进度: 75%

主要成果:
- 完成基站选址 20 个
- 完成设备安装 15 个
- 完成网络测试 10 个

下一步计划:
- 继续推进剩余 5 个基站的安装
- 开展全网性能优化
- 准备验收材料
"""

y_position = 100
for line in content.strip().split('\n'):
    page.insert_text((50, y_position), line, fontsize=12, color=(0, 0, 0))
    y_position += 20

# 保存 PDF
doc.save("examples/test_report.pdf")
doc.close()

print("✅ 测试 PDF 已创建: examples/test_report.pdf")
