import os
from abc import ABC, abstractmethod

import aiofiles


class BaseStorageService(ABC):
    @abstractmethod
    async def upload_file(
        self, file_content: bytes, file_name: str, workspace_id: str
    ) -> str:
        """Lưu trữ file và trả về storage key"""

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Xoá file"""

    @abstractmethod
    async def read_file(self, storage_key: str) -> bytes:
        """Đọc nội dung file"""


class LocalStorageService(BaseStorageService):
    def __init__(self, base_dir: str = "./storage"):
        self.base_dir = base_dir

    async def upload_file(
        self, file_content: bytes, file_name: str, workspace_id: str
    ) -> str:
        folder_path = os.path.join(self.base_dir, workspace_id)
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, file_name)
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)

        return file_path

    async def delete_file(self, storage_key: str) -> bool:
        if os.path.exists(storage_key):
            os.remove(storage_key)
            return True
        return False

    async def read_file(self, storage_key: str) -> bytes:
        if not os.path.exists(storage_key):
            raise FileNotFoundError(f"File not found: {storage_key}")
        async with aiofiles.open(storage_key, "rb") as f:
            return await f.read()
