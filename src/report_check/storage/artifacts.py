"""任务过程文件管理器

保存每个任务的完整执行过程，包括：
- 原始上传文件
- 解析后的结构化数据
- 规则处理过程
- AI 调用记录
- 检查结果详情
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


class ArtifactsManager:
    """管理任务过程文件的保存和检索"""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._call_counter = 0

    def init_task(self, task_id: str) -> "TaskArtifacts":
        """初始化任务的过程文件夹"""
        return TaskArtifacts(self.base_path / task_id, task_id)

    def get_task(self, task_id: str) -> "TaskArtifacts | None":
        """获取已有任务的过程文件管理器"""
        task_path = self.base_path / task_id
        if not task_path.exists():
            return None
        return TaskArtifacts(task_path, task_id)


class TaskArtifacts:
    """单个任务的过程文件管理"""

    def __init__(self, path: Path, task_id: str):
        self.path = path
        self.task_id = task_id
        self._call_counter = 0
        self._init_dirs()

    def _init_dirs(self):
        """创建标准文件夹结构"""
        dirs = [
            "0_upload",
            "1_parsed/images",
            "1_parsed/pages",  # PDF 页面渲染
            "2_rules",
            "3_checks",
            "4_ai_calls",
            "5_result",
        ]
        for d in dirs:
            (self.path / d).mkdir(parents=True, exist_ok=True)

        # 初始化任务日志
        self._log_path = self.path / "task.log"
        if not self._log_path.exists():
            self._log_path.write_text(f"[{datetime.now().isoformat()}] Task {self.task_id} started\n")

    def _log(self, message: str):
        """追加日志到任务日志文件"""
        timestamp = datetime.now().isoformat()
        with self._log_path.open("a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def _write_json(self, path: Path, data: Any, indent: int = 2):
        """安全地写入 JSON 文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent, default=str)
        except Exception as e:
            logger.error(f"Failed to write JSON to {path}: {e}")
            # 写入失败时也尝试保存原始信息
            path.write_text(f"{{\"error\": \"{str(e)}\", \"type\": \"{type(data).__name__}\"}}", encoding="utf-8")

    def _write_text(self, path: Path, content: str):
        """安全地写入文本文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_bytes(self, path: Path, data: bytes):
        """安全地写入二进制文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _next_call_id(self) -> str:
        """生成下一个 AI 调用序号"""
        self._call_counter += 1
        return f"{self._call_counter:04d}"

    # ==================== Stage 0: Upload ====================

    def save_upload(self, filename: str, data: bytes, content_type: str | None = None) -> Path:
        """保存原始上传文件"""
        upload_dir = self.path / "0_upload"
        file_path = upload_dir / filename
        self._write_bytes(file_path, data)
        self._log(f"Uploaded: {filename} ({len(data)} bytes, type={content_type})")
        return file_path

    # ==================== Stage 1: Parse ====================

    def save_parsed_content_blocks(self, content_blocks: list[dict]):
        """保存解析后的内容块"""
        path = self.path / "1_parsed/content_blocks.json"
        self._write_json(path, content_blocks)
        self._log(f"Saved {len(content_blocks)} content blocks")

    def save_parsed_image(self, image_id: str, data: bytes, format: str, metadata: dict | None = None) -> Path:
        """保存提取的图片"""
        filename = f"{image_id}.{format}"
        path = self.path / "1_parsed/images" / filename
        self._write_bytes(path, data)

        # 同时保存元数据
        if metadata:
            meta_path = self.path / "1_parsed/images" / f"{image_id}.json"
            self._write_json(meta_path, metadata)

        self._log(f"Saved image: {filename} ({len(data)} bytes)")
        return path

    def save_parsed_page(self, page_num: int, data: bytes, format: str = "png", metadata: dict | None = None) -> Path:
        """保存 PDF 渲染页面（用于扫描件）"""
        filename = f"page_{page_num:04d}.{format}"
        path = self.path / "1_parsed/pages" / filename
        self._write_bytes(path, data)

        if metadata:
            meta_path = self.path / "1_parsed/pages" / f"page_{page_num:04d}.json"
            self._write_json(meta_path, metadata)

        self._log(f"Saved page render: {filename} ({len(data)} bytes)")
        return path

    def save_report_data_summary(self, report_data: dict):
        """保存 ReportData 的摘要信息"""
        path = self.path / "1_parsed/report_data_summary.json"
        # 移除二进制数据，只保存元信息
        summary = {
            "file_name": report_data.get("file_name"),
            "source_type": report_data.get("source_type"),
            "content_block_count": len(report_data.get("content_blocks", [])),
            "image_count": len(report_data.get("images", [])),
            "metadata": report_data.get("metadata", {}),
        }
        self._write_json(path, summary)
        self._log(f"Saved report summary: {summary['content_block_count']} blocks, {summary['image_count']} images")

    def save_parse_metadata(self, metadata: dict):
        """保存解析过程的元数据"""
        path = self.path / "1_parsed/parse_metadata.json"
        self._write_json(path, metadata)
        self._log(f"Saved parse metadata: {metadata}")

    # ==================== Stage 2: Rules ====================

    def save_user_rules(self, rules: list[dict]):
        """保存用户原始规则"""
        path = self.path / "2_rules/0_user_rules.json"
        self._write_json(path, rules)
        self._log(f"Saved user rules: {len(rules)} rules")

    def save_merged_rules(self, rules: list[dict]):
        """保存合并模板后的规则"""
        path = self.path / "2_rules/1_merged_rules.json"
        self._write_json(path, rules)
        self._log(f"Saved merged rules: {len(rules)} rules")

    def save_resolved_rules(self, rules: list[dict]):
        """保存变量解析后的最终规则"""
        path = self.path / "2_rules/2_resolved_rules.json"
        self._write_json(path, rules)
        self._log(f"Saved resolved rules: {len(rules)} rules")

    # ==================== Stage 3: Checks ====================

    def init_check_artifact(self, rule_id: str, rule_type: str, rule_name: str) -> "CheckArtifact":
        """初始化单个规则的检查过程记录"""
        check_dir = self.path / "3_checks" / f"{rule_id}_{rule_type}"
        check_dir.mkdir(parents=True, exist_ok=True)

        # 保存规则基本信息
        self._write_json(check_dir / "rule_info.json", {
            "rule_id": rule_id,
            "rule_type": rule_type,
            "rule_name": rule_name,
            "started_at": datetime.now().isoformat(),
        })

        self._log(f"Started check: {rule_id} ({rule_type} - {rule_name})")
        return CheckArtifact(check_dir, self)

    # ==================== Stage 4: AI Calls ====================

    def save_ai_call(
        self,
        call_type: Literal["text", "multimodal", "locate"],
        purpose: str,
        request: dict,
        response: dict | str | None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> Path:
        """保存 AI 调用记录

        Args:
            call_type: 调用类型 (text/multimodal/locate)
            purpose: 调用目的描述，如 "locate_r1_text", "check_r2_image"
            request: 请求数据（包含 prompt, model, 等）
            response: 响应数据
            duration_ms: 调用耗时（毫秒）
            error: 错误信息（如果有）
        """
        call_id = self._next_call_id()
        filename = f"{call_id}_{purpose}.json"
        path = self.path / "4_ai_calls" / filename

        # 截断过长的内容用于日志
        def truncate_content(content: str, max_len: int = 200) -> str:
            if not isinstance(content, str):
                return str(content)[:max_len]
            return content[:max_len] + "..." if len(content) > max_len else content

        record = {
            "call_id": call_id,
            "timestamp": datetime.now().isoformat(),
            "call_type": call_type,
            "purpose": purpose,
            "request": {
                "model": request.get("model"),
                "prompt_preview": truncate_content(request.get("prompt", "")),
                "prompt_full_path": str(path.with_suffix(".request.txt")),
                **{k: v for k, v in request.items() if k not in ("prompt", "model")},
            },
            "response": {
                "content_preview": truncate_content(response) if isinstance(response, str) else None,
                "content_full_path": str(path.with_suffix(".response.txt")) if response else None,
                "structured": response if not isinstance(response, str) else None,
            },
            "duration_ms": duration_ms,
            "error": error,
        }

        self._write_json(path, record)

        # 保存完整的 prompt 和 response 到独立文件
        if "prompt" in request and request["prompt"]:
            self._write_text(path.with_suffix(".request.txt"), str(request["prompt"]))
        if response and isinstance(response, str):
            self._write_text(path.with_suffix(".response.txt"), response)

        status = "ERROR" if error else "OK"
        self._log(f"AI call {call_id} ({call_type}/{purpose}): {status}, {duration_ms:.0f}ms" if duration_ms else f"AI call {call_id} ({call_type}/{purpose}): {status}")

        return path

    # ==================== Stage 5: Result ====================

    def save_check_results(self, results: list[dict]):
        """保存最终检查结果"""
        path = self.path / "5_result/results.json"
        self._write_json(path, results)
        self._log(f"Saved results: {len(results)} items")

    def save_summary(self, summary: dict):
        """保存任务汇总"""
        path = self.path / "5_result/summary.json"
        summary["completed_at"] = datetime.now().isoformat()
        self._write_json(path, summary)
        self._log(f"Saved summary: {summary}")

    # ==================== Utilities ====================

    def get_artifact_list(self) -> dict[str, list[str]]:
        """获取所有过程文件清单"""
        result = {}
        for stage in ["0_upload", "1_parsed", "2_rules", "3_checks", "4_ai_calls", "5_result"]:
            stage_path = self.path / stage
            if stage_path.exists():
                files = []
                for f in stage_path.rglob("*"):
                    if f.is_file():
                        files.append(str(f.relative_to(self.path)))
                result[stage] = sorted(files)
        return result

    def export_package(self, output_path: Path) -> Path:
        """导出过程文件为压缩包"""
        import shutil

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.make_archive(
            str(output_path.with_suffix("")),
            "zip",
            self.path
        )
        return output_path.with_suffix(".zip")


class CheckArtifact:
    """单个规则检查的过程记录"""

    def __init__(self, path: Path, task_artifacts: TaskArtifacts):
        self.path = path
        self.task = task_artifacts
        self._attempt_counter = 0

    def _next_attempt_id(self) -> str:
        self._attempt_counter += 1
        return f"{self._attempt_counter:02d}"

    def save_config(self, config: dict):
        """保存实际使用的检查配置"""
        self.task._write_json(self.path / "config.json", config)

    def save_location_attempt(self, description: str, prompt: str, response: str, result: dict | None, error: str | None = None):
        """保存位置定位尝试"""
        attempt_id = self._next_attempt_id()
        attempt_dir = self.path / "location_attempts" / attempt_id
        attempt_dir.mkdir(parents=True, exist_ok=True)

        self.task._write_text(attempt_dir / "description.txt", description)
        self.task._write_text(attempt_dir / "prompt.txt", prompt)
        self.task._write_text(attempt_dir / "response.txt", response)
        if result:
            self.task._write_json(attempt_dir / "result.json", result)
        if error:
            self.task._write_text(attempt_dir / "error.txt", error)

    def save_check_detail(self, detail: dict):
        """保存检查过程的详细信息"""
        self.task._write_json(self.path / "detail.json", detail)

    def save_result(self, result: dict):
        """保存检查结果"""
        result["finished_at"] = datetime.now().isoformat()
        self.task._write_json(self.path / "result.json", result)
        self.task._log(f"Finished check: {self.path.name} - {result.get('status', 'unknown')}")

    def add_image_evidence(self, name: str, image_data: bytes, format: str = "png") -> Path:
        """保存图片证据（如被检查的图片）"""
        filename = f"{name}.{format}"
        path = self.path / filename
        self.task._write_bytes(path, image_data)
        return path
