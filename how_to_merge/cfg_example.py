"""
项目 A 的 cfg 示例。

说明：
- 这里只是演示结构，不要求你逐字照搬
- 你可以把这段合并到 A 现有的 cfg 文件中
"""

cfg = {
    "app": {
        "name": "project-a",
        "api_prefix": "/api/v1",
    },
    "report_check": {
        "route_prefix": "/report-check",
        "upload_path": "data/report_check/uploads",
        "artifacts_path": "data/report_check/tasks",
        "max_waiting_tasks": 10,
        "worker_concurrency": 2,
        "per_task_rule_concurrency": 5,
        "completed_task_retention_seconds": 300,
        "external_api_limits": {
            "default_max_concurrency": 2,
            "by_endpoint": {},
        },
        "default_provider": "openai",
        "providers": {
            "openai": {
                "text_api_key": "your-text-api-key",
                "text_base_url": "https://your-text-endpoint/v1",
                "multimodal_api_key": "your-vision-api-key",
                "multimodal_base_url": "https://your-vision-endpoint/v1",
                "text_model": "gpt-4o",
                "multimodal_model": "gpt-4o",
                "max_concurrency": 3,
                "text_max_concurrency": 2,
                "multimodal_max_concurrency": 1,
            }
        },
    },
}
