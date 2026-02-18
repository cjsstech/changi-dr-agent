# core/services/file_store_service.py

import os
import logging
from typing import List

logger = logging.getLogger(__name__)


class S3Storage:

    def __init__(self):

        try:
            import boto3
            self._boto3 = boto3
        except ImportError:
            # Allow tests to run without S3
            self._boto3 = None
            logger.warning("boto3 not installed - S3 disabled")

        self.bucket = os.getenv("FILE_BUCKET")
        self.region = os.getenv("AWS_REGION")

        self.s3 = None  # lazy client


    def _get_client(self):

        if not self._boto3:
            raise RuntimeError("S3 not available (boto3 missing)")

        if self.s3:
            return self.s3

        if not self.bucket:
            raise RuntimeError("FILE_BUCKET not set")

        if self.region:
            self.s3 = self._boto3.client("s3", region_name=self.region)
        else:
            self.s3 = self._boto3.client("s3")

        return self.s3


    def list_files(self, prefix: str) -> List[str]:

        s3 = self._get_client()

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


    def read(self, key: str) -> bytes:

        s3 = self._get_client()

        obj = s3.get_object(
            Bucket=self.bucket,
            Key=key
        )

        return obj["Body"].read()


    def write(self, key: str, data: bytes):

        s3 = self._get_client()

        s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data
        )


    def exists(self, key: str) -> bool:

        try:
            s3 = self._get_client()

            s3.head_object(
                Bucket=self.bucket,
                Key=key
            )

            return True

        except Exception:
            return False


    def delete(self, key: str):

        s3 = self._get_client()

        s3.delete_object(
            Bucket=self.bucket,
            Key=key
        )
