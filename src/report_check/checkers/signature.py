"""签名对比检查器

从两份报告中各自定位签名区域（网格编号法 + PIL 裁切），
再用多模态 AI 对比是否为同一人签名。

规则 config 格式：
{
    "file1_ref": 0,                    # 对应 files[0]（主文件），默认 0
    "file2_ref": 1,                    # 对应 files[1]（附加文件），默认 1
    "signature_description": "客户手写签名",
    "grid_size": 20,                   # 网格大小，默认 20x20
    "padding_cells": 1,                # 边界扩展格子数，默认 1
    "context_hint": ""                 # 可选，辅助定位提示
}
"""
import io
import json
import logging
import string
import time
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from report_check.checkers.base import BaseChecker, CheckResult

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class SignatureChecker(BaseChecker):
    """从两份报告中定位签名区域，裁切后用多模态 AI 对比是否为同一人。"""

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()

        file1_ref = rule_config.get("file1_ref", 0)
        file2_ref = rule_config.get("file2_ref", 1)
        sig_desc = rule_config.get("signature_description", "客户手写签名")
        grid_size = rule_config.get("grid_size", 20)
        padding_cells = rule_config.get("padding_cells", 1)
        context_hint = rule_config.get("context_hint", "")

        if self.artifacts:
            self.artifacts.save_check_detail({
                "file1_ref": file1_ref,
                "file2_ref": file2_ref,
                "signature_description": sig_desc,
                "grid_size": grid_size,
                "padding_cells": padding_cells,
                "context_hint": context_hint,
            })

        # 构建 report_data 列表（index 0 = 主文件，1+ = extra_report_data）
        all_reports = [self.report_data] + list(self.extra_report_data)

        if file1_ref >= len(all_reports):
            return CheckResult(
                status="error",
                message=f"file1_ref={file1_ref} 超出上传文件数量（共 {len(all_reports)} 份）",
                execution_time=time.time() - start,
            )
        if file2_ref >= len(all_reports):
            return CheckResult(
                status="error",
                message=f"file2_ref={file2_ref} 超出上传文件数量（共 {len(all_reports)} 份）",
                execution_time=time.time() - start,
            )

        report1 = all_reports[file1_ref]
        report2 = all_reports[file2_ref]

        # Step 1: 渲染两份报告的页面
        pages1 = await self._render_report(report1)
        pages2 = await self._render_report(report2)

        if not pages1:
            return CheckResult(
                status="error",
                message=f"无法渲染文件 {file1_ref} 的页面",
                execution_time=time.time() - start,
            )
        if not pages2:
            return CheckResult(
                status="error",
                message=f"无法渲染文件 {file2_ref} 的页面",
                execution_time=time.time() - start,
            )

        # Step 2: 定位签名并裁切（使用网格编号法）
        sig1 = await self._locate_and_crop_with_grid(
            pages1, sig_desc, context_hint, grid_size, padding_cells, label="file1"
        )
        sig2 = await self._locate_and_crop_with_grid(
            pages2, sig_desc, context_hint, grid_size, padding_cells, label="file2"
        )

        if sig1 is None:
            return CheckResult(
                status="error",
                message=f"在文件 {file1_ref} 中未能定位到签名区域",
                suggestion="请确认该文件中存在签名，或补充 context_hint 提供更多定位信息",
                execution_time=time.time() - start,
            )
        if sig2 is None:
            return CheckResult(
                status="error",
                message=f"在文件 {file2_ref} 中未能定位到签名区域",
                suggestion="请确认该文件中存在签名，或补充 context_hint 提供更多定位信息",
                execution_time=time.time() - start,
            )

        # Step 3: 保存裁切的签名图为 artifacts 证据
        if self.artifacts:
            self.artifacts.add_image_evidence("signature_file1", sig1, "png")
            self.artifacts.add_image_evidence("signature_file2", sig2, "png")

        # Step 4: 多模态 AI 对比两张签名
        result = await self._compare_signatures(sig1, sig2, sig_desc)

        return CheckResult(
            status=result.get("status", "error"),
            message=result.get("message", ""),
            suggestion=result.get("suggestion", ""),
            confidence=result.get("confidence", 0.0),
            execution_time=time.time() - start,
        )

    async def _render_report(self, report_data) -> list[bytes]:
        """渲染报告所有页面为图片列表。"""
        from report_check.parser.renderer import ReportRenderer
        renderer = ReportRenderer()
        return await renderer.render(report_data, self.artifacts)

    async def _locate_and_crop_with_grid(
        self,
        pages: list[bytes],
        sig_desc: str,
        context_hint: str,
        grid_size: int,
        padding_cells: int,
        label: str,
    ) -> bytes | None:
        """遍历页面，使用网格编号法定位签名并裁切。"""
        for i, page_bytes in enumerate(pages):
            result = await self._locate_signature_with_grid(
                page_bytes, sig_desc, context_hint, grid_size, purpose=f"locate_sig_{label}_page{i+1}"
            )
            if result is None:
                continue

            try:
                # 加载原始页面图片
                img = Image.open(io.BytesIO(page_bytes)).convert("RGB")
                w, h = img.size

                # 转换边界格子为像素坐标
                bbox = self._boundary_to_bbox(
                    result["top_left_cell"],
                    result["bottom_right_cell"],
                    w, h, grid_size, padding_cells
                )

                if bbox is None:
                    continue

                # 裁切签名
                crop = img.crop((bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]))
                buf = io.BytesIO()
                crop.save(buf, format="PNG")

                # 保存网格图为 artifact（用于调试）
                if self.artifacts:
                    grid_img = self._add_grid_overlay(img, grid_size)
                    grid_buf = io.BytesIO()
                    grid_img.save(grid_buf, format="PNG")
                    self.artifacts.add_image_evidence(
                        f"grid_{label}_page{i+1}", grid_buf.getvalue(), "png"
                    )

                return buf.getvalue()
            except Exception as e:
                logger.warning(f"Crop failed for {label} page {i+1}: {e}")
                continue

        return None

    async def _locate_signature_with_grid(
        self,
        page_bytes: bytes,
        sig_desc: str,
        context_hint: str,
        grid_size: int,
        purpose: str,
    ) -> dict | None:
        """使用网格编号法定位签名，返回边界格子或 None。"""
        # 添加网格叠加层
        img = Image.open(io.BytesIO(page_bytes)).convert("RGB")
        img_with_grid = self._add_grid_overlay(img, grid_size)

        # 转换为 bytes
        buf = io.BytesIO()
        img_with_grid.save(buf, format="PNG")
        grid_img_bytes = buf.getvalue()

        # 构建 prompt
        prompt = f"""你是一个签名定位专家。图片上叠加了 {grid_size}x{grid_size} 的网格系统。

请找出"{sig_desc}"的位置，并返回其**边界格子**（左上角和右下角）。
{f'提示：{context_hint}' if context_hint else ''}

要求：
1. 只定位手写签名，不包含印刷文字
2. 边界格子应该刚好框住签名，不要太大也不要太小
3. 如果有多个签名，只返回第一个

返回 JSON：
{{
  "found": true/false,
  "top_left_cell": "左上角格子编号（如 C15）",
  "bottom_right_cell": "右下角格子编号（如 D15）",
  "confidence": "high|medium|low"
}}

只返回 JSON。"""

        try:
            response = await self.call_multimodal_model_with_artifact(
                prompt, grid_img_bytes, purpose=purpose, image_format="png", max_tokens=300
            )
            data = self._parse_json_response(response)
            if not data or not data.get("found"):
                return None

            top_left = data.get("top_left_cell")
            bottom_right = data.get("bottom_right_cell")

            if not top_left or not bottom_right:
                return None

            return {
                "top_left_cell": top_left,
                "bottom_right_cell": bottom_right,
                "confidence": data.get("confidence", "unknown"),
            }
        except Exception as e:
            logger.warning(f"Grid-based signature location failed ({purpose}): {e}")
            return None

    def _add_grid_overlay(self, img: Image.Image, grid_size: int) -> Image.Image:
        """在图片上叠加网格编号系统。"""
        canvas = img.copy()
        draw = ImageDraw.Draw(canvas)
        w, h = img.size

        try:
            font = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 10)
            font_large = ImageFont.truetype('/System/Library/Fonts/PingFang.ttc', 14)
        except Exception:
            font = ImageFont.load_default()
            font_large = ImageFont.load_default()

        cell_width = w / grid_size
        cell_height = h / grid_size

        # 生成列标签 A-Z, AA-AZ...
        col_labels = []
        for i in range(grid_size):
            if i < 26:
                col_labels.append(string.ascii_uppercase[i])
            else:
                col_labels.append(string.ascii_uppercase[i // 26 - 1] + string.ascii_uppercase[i % 26])

        row_labels = [str(i+1) for i in range(grid_size)]

        # 绘制网格线
        for i in range(grid_size + 1):
            x = int(i * cell_width)
            draw.line([(x, 0), (x, h)], fill=(200, 200, 200, 128), width=1)
            y = int(i * cell_height)
            draw.line([(0, y), (w, y)], fill=(200, 200, 200, 128), width=1)

        # 标注列标签（顶部，红色）
        for i, label in enumerate(col_labels):
            x = int((i + 0.5) * cell_width)
            draw.text((x-5, 5), label, fill='red', font=font_large)

        # 标注行标签（左侧，蓝色）
        for i, label in enumerate(row_labels):
            y = int((i + 0.5) * cell_height)
            draw.text((5, y-7), label, fill='blue', font=font_large)

        # 在每个格子中心标注格子编号
        for i in range(grid_size):
            for j in range(grid_size):
                cell_id = f"{col_labels[i]}{row_labels[j]}"
                x = int((i + 0.5) * cell_width)
                y = int((j + 0.5) * cell_height)
                bbox = draw.textbbox((x, y), cell_id, font=font)
                draw.rectangle(bbox, fill=(255, 255, 255, 180))
                draw.text((x, y), cell_id, fill=(100, 100, 100, 200), font=font, anchor='mm')

        return canvas

    def _boundary_to_bbox(
        self,
        top_left: str,
        bottom_right: str,
        img_width: int,
        img_height: int,
        grid_size: int,
        padding_cells: int,
    ) -> dict | None:
        """将边界格子转换为像素坐标，支持 padding 扩展。"""
        # 生成列标签
        col_labels = []
        for i in range(grid_size):
            if i < 26:
                col_labels.append(string.ascii_uppercase[i])
            else:
                col_labels.append(string.ascii_uppercase[i // 26 - 1] + string.ascii_uppercase[i % 26])

        row_labels = [str(i+1) for i in range(grid_size)]

        cell_width = img_width / grid_size
        cell_height = img_height / grid_size

        # 解析格子编号
        tl_col = ''.join(c for c in top_left if c.isalpha())
        tl_row = ''.join(c for c in top_left if c.isdigit())
        br_col = ''.join(c for c in bottom_right if c.isalpha())
        br_row = ''.join(c for c in bottom_right if c.isdigit())

        if tl_col not in col_labels or br_col not in col_labels:
            logger.warning(f"Invalid column labels: {tl_col}, {br_col}")
            return None
        if tl_row not in row_labels or br_row not in row_labels:
            logger.warning(f"Invalid row labels: {tl_row}, {br_row}")
            return None

        tl_col_idx = col_labels.index(tl_col)
        tl_row_idx = row_labels.index(tl_row)
        br_col_idx = col_labels.index(br_col)
        br_row_idx = row_labels.index(br_row)

        # 应用 padding
        tl_col_idx = max(0, tl_col_idx - padding_cells)
        tl_row_idx = max(0, tl_row_idx - padding_cells)
        br_col_idx = min(grid_size - 1, br_col_idx + padding_cells)
        br_row_idx = min(grid_size - 1, br_row_idx + padding_cells)

        # 转换为像素坐标
        x1 = int(tl_col_idx * cell_width)
        y1 = int(tl_row_idx * cell_height)
        x2 = int((br_col_idx + 1) * cell_width)
        y2 = int((br_row_idx + 1) * cell_height)

        return {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

    async def _compare_signatures(self, sig1: bytes, sig2: bytes, sig_desc: str) -> dict:
        """将两张签名图发给多模态 AI 对比，返回结果 dict。"""
        prompt = f"""这是来自两份不同报告的"{sig_desc}"图片（第一张是报告1的签名，第二张是报告2的签名）。

请判断这两个签名是否为同一人所签，综合考虑：笔迹走势、字形结构、签名习惯等特征。

请以 JSON 格式返回：
{{
  "status": "passed（是同一人）| failed（不是同一人）| error（无法判断）",
  "message": "判断结论和理由",
  "suggestion": "如果不一致，说明可能的问题",
  "confidence": 0.0-1.0
}}

只返回 JSON，不要有其他文字。"""

        try:
            response = await self.call_multimodal_model_with_artifact(
                prompt, sig1, purpose="compare_signatures",
                image_format="png", extra_images=[sig2], max_tokens=500
            )
            result = self._parse_json_response(response)
            if result:
                return result
        except Exception as e:
            logger.error(f"Signature comparison failed: {e}")

        return {"status": "error", "message": "签名对比 AI 调用失败", "confidence": 0.0}

    def _parse_json_response(self, response: str) -> dict | None:
        """解析 AI 返回的 JSON 响应。"""
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse JSON response: {response[:200]}")
            return None
