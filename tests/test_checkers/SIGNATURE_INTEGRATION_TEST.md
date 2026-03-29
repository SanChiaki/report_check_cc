# 签名对比集成测试指南

## 测试文件准备

在 `tests/fixtures/` 目录下准备两份包含手写签名的 PDF 文件：
- `signature_sample_1.pdf` - 第一份带签名的报告
- `signature_sample_2.pdf` - 第二份带签名的报告（可以是同一人或不同人）

## 手动测试步骤

### 1. 启动后端服务

```bash
uv run uvicorn report_check.main:app --reload
```

### 2. 准备测试规则

创建 `test_signature_rules.json`:

```json
{
  "rules": [
    {
      "id": "sig_compare_1",
      "name": "客户签名一致性检查",
      "type": "signature_compare",
      "config": {
        "file1_ref": 0,
        "file2_ref": 1,
        "signature_description": "客户手写签名",
        "context_hint": "通常在报告底部",
        "grid_size": 20,
        "padding_cells": 1
      }
    }
  ]
}
```

### 3. 提交检查任务

使用 curl 或 Postman 提交：

```bash
curl -X POST "http://localhost:8000/api/v1/check/submit" \
  -F "files=@tests/fixtures/signature_sample_1.pdf" \
  -F "files=@tests/fixtures/signature_sample_2.pdf" \
  -F "user_rules=@test_signature_rules.json"
```

### 4. 查询结果

```bash
# 获取任务 ID 后查询
curl "http://localhost:8000/api/v1/check/result/{task_id}"
```

### 5. 查看过程文件

```bash
# 下载所有过程文件
curl "http://localhost:8000/api/v1/tasks/{task_id}/artifacts/download" -o artifacts.zip

# 解压查看
unzip artifacts.zip
```

## 验证要点

### 网格标注图片

在 `3_checks/sig_compare_1/` 目录下查看：
- `grid_file1_page_X.png` - 第一份文件的网格标注图
- `grid_file2_page_X.png` - 第二份文件的网格标注图

验证：
- 红色列标签（A-T）清晰可见
- 蓝色行标签（1-20）清晰可见
- 灰色网格线均匀分布
- 每个格子中心有格子编号（如 A1, B2）

### 裁切签名图片

在同一目录下查看：
- `cropped_signature_file1.png` - 第一份文件裁切的签名
- `cropped_signature_file2.png` - 第二份文件裁切的签名

验证：
- 签名完整，没有被截断
- 包含适当的边距（padding_cells=1 的效果）
- 图片清晰，可以看清签名细节

### AI 定位结果

查看 `4_ai_calls/` 目录下的 JSON 文件：

```json
{
  "found": true,
  "top_left_cell": "C15",
  "bottom_right_cell": "D15",
  "confidence": "high"
}
```

验证：
- `found` 为 true
- 格子编号合理（在 A1-T20 范围内）
- confidence 为 high/medium/low

### 对比结果

查看最终的 CheckResult：

```json
{
  "status": "pass",  // 或 "fail"
  "confidence": 0.95,
  "message": "两个签名高度相似，判断为同一人所签",
  "location": {
    "file1_page": 0,
    "file1_cells": "C15-D15",
    "file2_page": 1,
    "file2_cells": "D16-E16"
  }
}
```

## 常见问题

### 签名未找到

可能原因：
1. 签名太小或太淡，AI 无法识别
2. `signature_description` 描述不准确
3. 签名在扫描件中，需要确保 PDF 已正确渲染为图片

解决方案：
- 调整 `context_hint` 提供更多上下文
- 检查网格标注图，确认签名可见
- 尝试不同的 `grid_size`（10, 20, 30）

### 裁切不完整

可能原因：
1. AI 返回的格子范围太小
2. `padding_cells` 设置为 0

解决方案：
- 增加 `padding_cells` 到 2 或 3
- 检查 AI 返回的 `top_left_cell` 和 `bottom_right_cell` 是否合理

### 对比结果不准确

可能原因：
1. 裁切的签名图片质量不佳
2. 两个签名差异很大（不同人）
3. 多模态模型能力限制

解决方案：
- 检查裁切的签名图片是否清晰完整
- 尝试使用更强的多模态模型（如 GPT-4o）
- 调整 `grid_size` 和 `padding_cells` 优化裁切质量

## 性能基准

基于测试数据（2000x2000px 图片，20x20 网格）：

- 网格标注生成：~50ms
- AI 签名定位：~2-3s（取决于模型）
- 图片裁切：~10ms
- AI 签名对比：~2-3s（取决于模型）
- 总耗时：~5-7s（单次对比）

## 自动化测试（可选）

如果配置了 AI API 密钥，可以运行自动化测试：

```bash
# 需要设置环境变量
export OPENAI_API_KEY=your_key
export OPENAI_API_BASE_URL=https://api.openai.com/v1

# 运行测试
uv run pytest tests/test_checkers/test_signature_unit.py -v
```

注意：自动化测试仅覆盖网格生成和坐标转换逻辑，不包含实际的 AI 调用。
