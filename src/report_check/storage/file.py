from pathlib import Path


class FileStorage:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_uploaded_file(self, file_data: bytes, filename: str, task_id: str) -> str:
        task_dir = self.base_path / task_id
        task_dir.mkdir(exist_ok=True)
        file_path = task_dir / filename
        file_path.write_bytes(file_data)
        return str(file_path)

    async def cleanup_task_files(self, task_id: str):
        import shutil
        task_dir = self.base_path / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)
