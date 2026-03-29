#!/usr/bin/env python3
"""快速测试 MSG 文件上传和检查

使用方法:
    uv run python scripts/test_msg_upload.py <msg_file_path>

示例:
    uv run python scripts/test_msg_upload.py tests/fixtures/test_email.msg
"""

import sys
import requests
import json
import time
from pathlib import Path


def test_msg_upload(msg_file_path: str, base_url: str = "http://localhost:8000"):
    """测试 MSG 文件上传和检查"""

    msg_path = Path(msg_file_path)
    if not msg_path.exists():
        print(f"❌ 文件不存在: {msg_file_path}")
        print("\n请先创建测试 MSG 文件，参考: tests/fixtures/README_MSG.md")
        return False

    print(f"📧 测试 MSG 文件: {msg_path.name}")
    print(f"📊 文件大小: {msg_path.stat().st_size / 1024:.2f} KB")

    # 测试规则
    rules = {
        "rules": [
            {
                "id": "r1",
                "name": "检查邮件正文包含关键词",
                "type": "text",
                "config": {
                    "field": "email_body",
                    "keywords": ["测试", "报告", "质检", "完成"]
                }
            }
        ]
    }

    print("\n📤 提交检查任务...")
    try:
        with open(msg_path, "rb") as f:
            response = requests.post(
                f"{base_url}/api/v1/check/submit",
                files={"files": (msg_path.name, f, "application/vnd.ms-outlook")},
                data={"rules": json.dumps(rules)}
            )

        if response.status_code != 200:
            print(f"❌ 提交失败: {response.status_code}")
            print(response.json())
            return False

        result = response.json()
        task_id = result["task_id"]
        print(f"✅ 任务已提交")
        print(f"📋 任务 ID: {task_id}")
        print(f"🔄 状态: {result['status']}")

    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到服务器: {base_url}")
        print("请先启动服务: uv run uvicorn report_check.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ 提交失败: {e}")
        return False

    # 轮询结果
    print("\n⏳ 等待处理结果...")
    max_attempts = 30
    for i in range(max_attempts):
        time.sleep(1)
        try:
            response = requests.get(f"{base_url}/api/v1/check/result/{task_id}")
            result = response.json()
            status = result["status"]

            if status == "completed":
                print(f"\n✅ 检查完成!")
                print(f"\n📊 检查结果:")
                print(f"  总计: {result['result']['summary']['total']} 项")
                print(f"  通过: {result['result']['summary']['passed']} 项")
                print(f"  失败: {result['result']['summary']['failed']} 项")
                print(f"  错误: {result['result']['summary']['error']} 项")

                print(f"\n📄 报告信息:")
                print(f"  文件名: {result['result']['report_info']['file_name']}")
                print(f"  类型: {result['result']['report_info'].get('report_type', 'N/A')}")

                print(f"\n📝 详细结果:")
                for item in result['result']['results']:
                    status_icon = "✅" if item['status'] == "passed" else "❌"
                    print(f"  {status_icon} {item['rule_name']}")
                    if item.get('message'):
                        print(f"     消息: {item['message']}")
                    if item.get('location', {}).get('description'):
                        print(f"     位置: {item['location']['description']}")

                return True

            elif status == "failed":
                print(f"\n❌ 检查失败: {result.get('error', '未知错误')}")
                return False

            elif status == "processing":
                print(f"  处理中... ({i+1}/{max_attempts}s)")

        except Exception as e:
            print(f"❌ 查询失败: {e}")
            return False

    print(f"\n⏱️ 超时: 处理时间超过 {max_attempts} 秒")
    return False


def main():
    if len(sys.argv) < 2:
        print("用法: uv run python scripts/test_msg_upload.py <msg_file_path>")
        print("\n示例:")
        print("  uv run python scripts/test_msg_upload.py tests/fixtures/test_email.msg")
        print("\n如果没有测试文件，请参考: tests/fixtures/README_MSG.md")
        sys.exit(1)

    msg_file = sys.argv[1]
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

    success = test_msg_upload(msg_file, base_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
