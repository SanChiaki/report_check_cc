"""测试扫描件 OCR 并构造检查规则"""
import asyncio
import base64
import os
from pathlib import Path

# 加载环境变量
os.environ.setdefault("OPENAI_API_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("OPENAI_API_KEY", "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")

from report_check.parser.pdf import PDFParser
from report_check.models.manager import ModelManager
from report_check.models.openai_adapter import OpenAIAdapter
from report_check.checkers.factory import CheckerFactory
import fitz


async def extract_content_with_vision(pdf_path: str, model_manager: ModelManager):
    """使用多模态模型提取 PDF 内容"""

    # 先用 PyMuPDF 渲染页面
    doc = fitz.open(pdf_path)
    dpi = 150

    all_extracted_text = []
    page_images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        img_data = pix.tobytes("png")
        page_images.append(img_data)

        prompt = """请提取这张图片中的所有文字内容，保持原有的段落和格式。
如果包含表格，请保留表格结构（用 | 分隔列，用换行分隔行）。
只返回提取的纯文本内容，不要添加任何解释。"""

        print(f"Extracting text from page {page_num + 1}...")
        try:
            response = await model_manager.call_multimodal_model(
                prompt=prompt,
                image=img_data
            )
            extracted_text = response.strip()
            all_extracted_text.append(f"=== Page {page_num + 1} ===\n{extracted_text}")
            print(f"Page {page_num + 1} extracted: {len(extracted_text)} chars")
        except Exception as e:
            print(f"Failed to extract page {page_num + 1}: {e}")

    doc.close()
    return "\n\n".join(all_extracted_text), page_images


async def main():
    pdf_path = "tests/fixtures/telecom_progress_report_scanned.pdf"

    if not Path(pdf_path).exists():
        print(f"File not found: {pdf_path}")
        return

    # 初始化模型管理器
    model_manager = ModelManager(default_provider="openai")
    adapter = OpenAIAdapter({
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "text_base_url": os.environ.get("OPENAI_API_BASE_URL"),
        "multimodal_base_url": os.environ.get("OPENAI_API_BASE_URL"),
        "text_model": "openai/gpt-4o-2024-11-20",
        "multimodal_model": "qwen/qwen2.5-vl-32b-instruct",
    })
    model_manager.register_adapter("openai", adapter)

    # 提取内容
    print("=" * 60)
    print("Step 1: Extracting content with vision model")
    print("=" * 60)
    extracted_content, page_images = await extract_content_with_vision(pdf_path, model_manager)

    print("\n" + "=" * 60)
    print("Extracted Content:")
    print("=" * 60)
    print(extracted_content[:3000] if len(extracted_content) > 3000 else extracted_content)
    if len(extracted_content) > 3000:
        print(f"\n... (truncated, total {len(extracted_content)} chars)")

    # 解析 PDF 获取 ReportData
    print("\n" + "=" * 60)
    print("Step 2: Parsing PDF with OCR support")
    print("=" * 60)
    parser = PDFParser(model_manager=model_manager)
    report_data = parser.parse(pdf_path)
    print(f"Is scanned: {report_data.metadata.get('is_scanned')}")
    print(f"Page count: {report_data.metadata.get('page_count')}")
    print(f"Images: {len(report_data.images)}")

    # OCR 提取
    ocr_blocks = await parser.extract_text_with_vision(report_data)
    print(f"OCR blocks extracted: {len(ocr_blocks)}")
    for block in ocr_blocks:
        print(f"  - {block.location}: {len(str(block.content))} chars")

    # 将 OCR 内容合并到 report_data
    report_data.content_blocks = ocr_blocks + report_data.content_blocks

    # 根据提取的内容构造检查规则
    print("\n" + "=" * 60)
    print("Step 3: Constructing check rules based on extracted content")
    print("=" * 60)

    # 分析提取的内容，找出关键信息
    full_text = "\n".join([str(b.content) for b in ocr_blocks])

    # 构造能 PASS 的检查规则（基于实际提取的内容）
    check_rules = {
        "rules": [
            # 1. Text check - 检查报告标题（实际内容包含"中国电信 5G 网络建设"）
            {
                "id": "text_001",
                "name": "报告标题检查",
                "type": "text",
                "config": {
                    "keywords": ["中国电信", "5G 网络建设"],
                    "match_mode": "any",
                    "case_sensitive": False,
                    "min_occurrences": 1
                }
            },
            # 2. Text check - 检查建设单位
            {
                "id": "text_002",
                "name": "建设单位检查",
                "type": "text",
                "config": {
                    "keywords": ["中国电信", "智联通信"],
                    "match_mode": "any",
                    "case_sensitive": False,
                    "min_occurrences": 1
                }
            },
            # 3. Text check - 检查项目进展关键词
            {
                "id": "text_003",
                "name": "项目进展检查",
                "type": "text",
                "config": {
                    "keywords": ["完成", "完工", "施工"],
                    "match_mode": "any",
                    "case_sensitive": False,
                    "min_occurrences": 1
                }
            },
            # 4. Semantic check - 检查建设内容
            {
                "id": "semantic_001",
                "name": "建设内容语义检查",
                "type": "semantic",
                "config": {
                    "requirement": "报告中应包含项目建设相关内容，如5G网络、机房、信号塔等",
                    "context_hint": "查找项目建设或工程进展相关内容"
                }
            },
            # 5. Semantic check - 检查检查记录
            {
                "id": "semantic_002",
                "name": "检查记录语义检查",
                "type": "semantic",
                "config": {
                    "requirement": "报告中应包含检查记录或完工信息",
                    "context_hint": "查找检查日期、完工日期、审核结论等信息"
                }
            },
            # 6. Image check - 检查现场照片
            {
                "id": "image_001",
                "name": "现场照片检查",
                "type": "image",
                "config": {
                    "description": "检查是否包含机房安装检查照片或信号塔照片",
                    "min_count": 1
                }
            },
            # 6. API check - 健康检查
            {
                "id": "api_001",
                "name": "API连通性检查",
                "type": "api",
                "config": {
                    "extract": {
                        "type": "text",
                        "description": "报告标题",
                        "context_hint": "查找报告标题"
                    },
                    "api": {
                        "endpoint": "https://httpbin.org/get",
                        "method": "GET"
                    },
                    "validation": {
                        "success_field": "url",
                        "success_value": "httpbin",
                        "operator": "contains"
                    }
                }
            },
            # 7. External data check - 验证外部 API 可访问
            {
                "id": "external_001",
                "name": "外部API可用性检查",
                "type": "external_data",
                "config": {
                    "extract": {
                        "type": "text",
                        "description": "中国电信或5G网络",
                        "context_hint": "查找项目相关信息"
                    },
                    "external_api": {
                        "endpoint": "https://httpbin.org/json",
                        "method": "GET"
                    },
                    "analysis": {
                        "requirement": "验证外部API返回的JSON数据格式正确，包含slideshow字段"
                    }
                }
            }
        ]
    }

    print("\nConstructed Rules:")
    import json
    print(json.dumps(check_rules, indent=2, ensure_ascii=False))

    # 运行检查
    print("\n" + "=" * 60)
    print("Step 4: Running checks")
    print("=" * 60)

    results = []
    for rule in check_rules["rules"]:
        print(f"\nRunning: {rule['name']} ({rule['type']})")
        try:
            checker = CheckerFactory.create(
                rule["type"], report_data, model_manager, artifacts=None
            )
            result = checker.check(rule["config"])
            if asyncio.iscoroutine(result):
                result = await result

            print(f"  Status: {result.status}")
            print(f"  Message: {result.message}")
            results.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "rule_type": rule["type"],
                "status": result.status,
                "message": result.message,
                "suggestion": result.suggestion,
            })
        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "rule_type": rule["type"],
                "status": "error",
                "message": str(e),
                "suggestion": "",
            })

    # 输出结果汇总
    print("\n" + "=" * 60)
    print("Step 5: Results Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["status"] == "error")

    print(f"Total: {len(results)} checks")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")

    print("\nDetailed Results:")
    for r in results:
        icon = "✅" if r["status"] == "passed" else "❌"
        print(f"\n{icon} {r['rule_name']} ({r['rule_type']})")
        print(f"   Status: {r['status']}")
        print(f"   Message: {r['message']}")
        if r['suggestion']:
            print(f"   Suggestion: {r['suggestion']}")

    # 保存结果到文件
    output = {
        "check_rules": check_rules,
        "check_results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors
        },
        "extracted_content_preview": extracted_content[:2000] if len(extracted_content) > 2000 else extracted_content
    }

    output_path = Path("test_scanned_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
