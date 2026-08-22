"""
MinIO Client Service - Quản lý lưu trữ file trên MinIO Object Storage
"""

import os
from datetime import timedelta

import structlog
from minio import Minio
from minio.error import S3Error

logger = structlog.get_logger(__name__)


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
        self._bucket_ready = False

    def _ensure_bucket_exists(self) -> bool:
        """Tạo bucket nếu chưa tồn tại"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Bucket '{self.bucket_name}' created successfully")
            self._bucket_ready = True
            return True
        except S3Error as e:
            logger.info(f"Error checking/creating bucket: {e}")
            self._bucket_ready = False
            return False
        except Exception as e:
            logger.info(f"Could not connect to MinIO bucket '{self.bucket_name}': {e}")
            self._bucket_ready = False
            return False

    def _ensure_ready(self) -> bool:
        if self._bucket_ready:
            return True
        return self._ensure_bucket_exists()

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
            if not self._ensure_ready():
                return False
            self.client.fput_object(self.bucket_name, object_name, local_path)
            return True
        except S3Error as e:
            logger.info(f"Error uploading file {local_path} to {object_name}: {e}")
            return False
        except Exception as e:
            logger.info(f"Error uploading file {local_path} to {object_name}: {e}")
            self._bucket_ready = False
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
            if not self._ensure_ready():
                return False
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
            logger.info(f"Error uploading data to {object_name}: {e}")
            return False
        except Exception as e:
            logger.info(f"Error uploading data to {object_name}: {e}")
            self._bucket_ready = False
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
            if not self._ensure_ready():
                return False
            # Tạo thư mục nếu chưa tồn tại
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            self.client.fget_object(self.bucket_name, object_name, local_path)
            return True
        except S3Error as e:
            logger.info(f"Error downloading file {object_name} to {local_path}: {e}")
            return False
        except Exception as e:
            logger.info(f"Error downloading file {object_name} to {local_path}: {e}")
            self._bucket_ready = False
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
            if not self._ensure_ready():
                return None
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            logger.info(f"Error downloading data from {object_name}: {e}")
            return None
        except Exception as e:
            logger.info(f"Error downloading data from {object_name}: {e}")
            self._bucket_ready = False
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
            if not self._ensure_ready():
                return False
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            logger.info(f"Error deleting file {object_name}: {e}")
            return False
        except Exception as e:
            logger.info(f"Error deleting file {object_name}: {e}")
            self._bucket_ready = False
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
            if not self._ensure_ready():
                return False
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False
        except Exception as e:
            logger.info(f"Error checking file {object_name}: {e}")
            self._bucket_ready = False
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
            if not self._ensure_ready():
                return []
            objects = self.client.list_objects(self.bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.info(f"Error listing files with prefix {prefix}: {e}")
            return []
        except Exception as e:
            logger.info(f"Error listing files with prefix {prefix}: {e}")
            self._bucket_ready = False
            return []

    def get_presigned_url(
        self, object_name: str, expiry_seconds: int = 3600
    ) -> str | None:
        """
        Tạo presigned URL để truy cập object trong thời gian giới hạn.
        """
        try:
            if not self._ensure_ready():
                return None
            return self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(seconds=expiry_seconds),
            )
        except S3Error as e:
            logger.info(f"Error creating presigned URL for {object_name}: {e}")
            return None
        except Exception as e:
            logger.info(f"Error creating presigned URL for {object_name}: {e}")
            self._bucket_ready = False
            return None


# Singleton instance để dùng chung
minio_client = MinIOClient(
    endpoint="localhost:9000",
    access_key="admin",
    secret_key="admin123",
    secure=False,
    bucket_name="mybucket",
)
