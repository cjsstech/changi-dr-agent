# core/services/file_store_service.py

import os
import logging
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)

CLOUD_ENV = os.environ.get("CLOUD_ENV", "false").lower() == "true"


class FileStorageService:

    def __init__(self):

        # ---------- Cloud (S3) ----------
        self.bucket = os.getenv("FILE_BUCKET")
        self.region = os.getenv("AWS_REGION")

        self._boto3 = None
        self.s3 = None  # lazy client

        # ---------- Local storage ----------
        project_root = Path(__file__).resolve().parents[2]
        self.local_root = project_root / "storage"

        if CLOUD_ENV:
            try:
                import boto3
                self._boto3 = boto3
            except ImportError:
                raise RuntimeError("boto3 required in CLOUD_ENV")

        else:
            self.local_root.mkdir(parents=True, exist_ok=True)
            logger.info(f"Using local storage at {self.local_root}")

    # =========================================================
    # Internal helpers
    # =========================================================

    def _get_s3_client(self):

        if not self._boto3:
            raise RuntimeError("S3 not available")

        if self.s3:
            return self.s3

        if not self.bucket:
            raise RuntimeError("FILE_BUCKET not set")

        if self.region:
            self.s3 = self._boto3.client("s3", region_name=self.region)
        else:
            self.s3 = self._boto3.client("s3")

        return self.s3

    def _local_path(self, key: str) -> Path:
        return self.local_root / key

    # =========================================================
    # Public API
    # =========================================================

    def list_files(self, prefix: str) -> List[str]:

        if CLOUD_ENV:
            s3 = self._get_s3_client()
            paginator = s3.get_paginator("list_objects_v2")

            files = []

            for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix
            ):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith("/"):
                        files.append(key)

            return files

        else:
            base_path = self._local_path(prefix)

            if not base_path.exists():
                return []

            result = []

            for path in base_path.rglob("*"):
                if path.is_file():
                    rel_path = path.relative_to(self.local_root)
                    result.append(str(rel_path))

            return result

    # ---------------------------------------------------------

    def read(self, key: str) -> bytes:

        if CLOUD_ENV:
            s3 = self._get_s3_client()

            obj = s3.get_object(
                Bucket=self.bucket,
                Key=key
            )

            return obj["Body"].read()

        else:
            with open(self._local_path(key), "rb") as f:
                return f.read()

    # ---------------------------------------------------------

    def write(self, key: str, data: bytes):

        if CLOUD_ENV:
            s3 = self._get_s3_client()

            s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data
            )

        else:
            path = self._local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "wb") as f:
                f.write(data)

    # ---------------------------------------------------------

    def exists(self, key: str) -> bool:

        if CLOUD_ENV:
            try:
                s3 = self._get_s3_client()

                s3.head_object(
                    Bucket=self.bucket,
                    Key=key
                )
                return True

            except Exception:
                return False

        else:
            return self._local_path(key).exists()

    # ---------------------------------------------------------

    def delete(self, key: str):

        if CLOUD_ENV:
            s3 = self._get_s3_client()

            s3.delete_object(
                Bucket=self.bucket,
                Key=key
            )

        else:
            path = self._local_path(key)

            if path.exists():
                path.unlink()