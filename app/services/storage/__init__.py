"""MinIO/S3 Storage service for document uploads and deletions."""
import uuid
from typing import Optional, List
from minio import Minio
from minio.error import S3Error
from app.config.settings import settings
from app.config.logging_config import logger


class StorageService:
    """Handles file storage operations with MinIO (S3-compatible)."""

    def __init__(self):
        self._client = None
        self.bucket_name = settings.S3_BUCKET_NAME

    @property
    def client(self) -> Minio:
        """Lazily initializes the MinIO client."""
        if self._client is None:
            self._client = Minio(
                endpoint=settings.S3_ENDPOINT_URL.replace("http://", "").replace("https://", ""),
                access_key=settings.S3_ACCESS_KEY,
                secret_key=settings.S3_SECRET_KEY,
                secure=settings.S3_ENDPOINT_URL.startswith("https"),
                region=settings.S3_REGION,
            )
            self._ensure_bucket_exists()
        return self._client

    def _ensure_bucket_exists(self) -> None:
        """Creates the bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name, location=settings.S3_REGION)
                logger.info("Created MinIO bucket", bucket=self.bucket_name)
        except S3Error as e:
            logger.error("Failed to ensure bucket exists", bucket=self.bucket_name, error=str(e))
            raise

    def upload_file(
        self,
        file_bytes: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Uploads a file to MinIO.

        Args:
            file_bytes: Raw file content
            object_name: Unique object name (e.g., "student_id/doc_id.pdf")
            content_type: MIME type

        Returns:
            The object name (key) of the uploaded file
        """
        import io
        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=io.BytesIO(file_bytes),
                length=len(file_bytes),
                content_type=content_type,
            )
            logger.info("Uploaded file to MinIO", object_name=object_name, size=len(file_bytes))
            return object_name
        except S3Error as e:
            logger.error("Failed to upload file to MinIO", object_name=object_name, error=str(e))
            raise

    def delete_file(self, object_name: str) -> bool:
        """
        Deletes a file from MinIO.

        Args:
            object_name: The object name to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info("Deleted file from MinIO", object_name=object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning("File not found in MinIO for deletion", object_name=object_name)
                return False
            logger.error("Failed to delete file from MinIO", object_name=object_name, error=str(e))
            raise

    def delete_files_by_prefix(self, prefix: str) -> int:
        """
        Deletes all files with a given prefix.

        Args:
            prefix: Object name prefix (e.g., "student_id/")

        Returns:
            Number of files deleted
        """
        try:
            objects_to_delete = [
                obj.object_name
                for obj in self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            ]
            if not objects_to_delete:
                return 0

            from minio.deleteobjects import DeleteObject
            delete_object_list = [DeleteObject(obj) for obj in objects_to_delete]
            errors = list(self.client.remove_objects(self.bucket_name, delete_object_list))
            if errors:
                for err in errors:
                    logger.error("Error deleting object", object_name=err.object_name, error=str(err))
            deleted_count = len(objects_to_delete) - len(errors)
            logger.info("Deleted files by prefix", prefix=prefix, count=deleted_count)
            return deleted_count
        except S3Error as e:
            logger.error("Failed to delete files by prefix", prefix=prefix, error=str(e))
            raise

    def get_file_url(self, object_name: str, expires_seconds: int = 3600) -> str:
        """
        Generates a presigned URL for temporary file access.

        Args:
            object_name: The object name
            expires_seconds: URL expiration time

        Returns:
            Presigned URL
        """
        from datetime import timedelta
        try:
            return self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
            )
        except S3Error as e:
            logger.error("Failed to generate presigned URL", object_name=object_name, error=str(e))
            raise

    def file_exists(self, object_name: str) -> bool:
        """Checks if a file exists in MinIO."""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise


# Global instance - lazily initialized
storage_service = StorageService()