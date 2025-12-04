"""
MinIO Client Service - Quản lý lưu trữ file trên MinIO Object Storage
"""

import os
from minio import Minio
from minio.error import S3Error


class MinIOClient:
    """
    MinIO Client để upload/download/delete files
    """

    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "admin",
        secret_key: str = "admin123",
        secure: bool = False,
        bucket_name: str = "mybucket",
    ):
        self.client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Tạo bucket nếu chưa tồn tại"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"Bucket '{self.bucket_name}' created successfully")
        except S3Error as e:
            print(f"Error checking/creating bucket: {e}")

    def upload_file(self, local_path: str, object_name: str) -> bool:
        """
        Upload file lên MinIO

        Args:
            local_path: Đường dẫn file local
            object_name: Tên object trên MinIO (có thể có path như session_id/filename)

        Returns:
            True nếu thành công, False nếu thất bại
        """
        try:
            self.client.fput_object(self.bucket_name, object_name, local_path)
            return True
        except S3Error as e:
            print(f"Error uploading file {local_path} to {object_name}: {e}")
            return False

    def upload_data(self, object_name: str, data: bytes, length: int = None) -> bool:
        """
        Upload dữ liệu (bytes) lên MinIO

        Args:
            object_name: Tên object trên MinIO
            data: Dữ liệu dạng bytes hoặc str (sẽ tự động convert)
            length: Độ dài data (nếu không truyền sẽ tính tự động)

        Returns:
            True nếu thành công, False nếu thất bại
        """
        try:
            from io import BytesIO

            # Ensure data is bytes
            if isinstance(data, str):
                data = data.encode("utf-8")
            elif not isinstance(data, bytes):
                data = bytes(data)

            if length is None:
                length = len(data)

            self.client.put_object(self.bucket_name, object_name, BytesIO(data), length)
            return True
        except S3Error as e:
            print(f"Error uploading data to {object_name}: {e}")
            return False

    def download_file(self, object_name: str, local_path: str) -> bool:
        """
        Download file từ MinIO về local

        Args:
            object_name: Tên object trên MinIO
            local_path: Đường dẫn lưu file local

        Returns:
            True nếu thành công, False nếu thất bại
        """
        try:
            # Tạo thư mục nếu chưa tồn tại
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            self.client.fget_object(self.bucket_name, object_name, local_path)
            return True
        except S3Error as e:
            print(f"Error downloading file {object_name} to {local_path}: {e}")
            return False

    def download_data(self, object_name: str) -> bytes | None:
        """
        Download dữ liệu từ MinIO dưới dạng bytes

        Args:
            object_name: Tên object trên MinIO

        Returns:
            Dữ liệu dạng bytes hoặc None nếu lỗi
        """
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            print(f"Error downloading data from {object_name}: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        Xóa file trên MinIO

        Args:
            object_name: Tên object trên MinIO

        Returns:
            True nếu thành công, False nếu thất bại
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            print(f"Error deleting file {object_name}: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        """
        Kiểm tra file có tồn tại trên MinIO không

        Args:
            object_name: Tên object trên MinIO

        Returns:
            True nếu tồn tại, False nếu không
        """
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False

    def list_files(self, prefix: str = "") -> list:
        """
        Liệt kê các file trong bucket với prefix

        Args:
            prefix: Prefix để filter (vd: "session_id/")

        Returns:
            Danh sách tên các object
        """
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"Error listing files with prefix {prefix}: {e}")
            return []


# Singleton instance để dùng chung
minio_client = MinIOClient(
    endpoint="localhost:9000",
    access_key="admin",
    secret_key="admin123",
    secure=False,
    bucket_name="mybucket",
)
