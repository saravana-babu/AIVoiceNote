import logging
from typing import Dict, Any, List, Optional
import boto3
from botocore.client import Config
from app.core.config import settings

logger = logging.getLogger("voicemind.r2")

class R2Client:
    def __init__(self):
        self.is_configured = all([
            settings.R2_ACCOUNT_ID,
            settings.R2_ACCESS_KEY_ID,
            settings.R2_SECRET_ACCESS_KEY
        ])
        
        if self.is_configured:
            # Cloudflare R2 endpoint format: https://<account_id>.r2.cloudflarestorage.com
            endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            self.client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name="auto"
            )
            self.bucket = settings.R2_BUCKET_NAME
            logger.info(f"Cloudflare R2 Client initialized successfully on bucket '{self.bucket}'.")
        else:
            self.client = None
            self.bucket = settings.R2_BUCKET_NAME
            logger.warning("Cloudflare R2 credentials are not set. R2 Client will run in MOCK mode.")

    def generate_presigned_upload_url(self, key: str, expires_in: int = 3600) -> str:
        if self.is_configured:
            try:
                url = self.client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expires_in
                )
                return url
            except Exception as e:
                logger.error(f"Failed to generate presigned upload URL: {e}")
                raise
        else:
            return f"http://localhost:8000/mock-r2/{self.bucket}/{key}?upload=true"

    def generate_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        if self.is_configured:
            try:
                url = self.client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expires_in
                )
                return url
            except Exception as e:
                logger.error(f"Failed to generate presigned download URL: {e}")
                raise
        else:
            return f"http://localhost:8000/mock-r2/{self.bucket}/{key}?download=true"

    def initiate_multipart_upload(self, key: str) -> str:
        if self.is_configured:
            try:
                response = self.client.create_multipart_upload(
                    Bucket=self.bucket,
                    Key=key
                )
                return response["UploadId"]
            except Exception as e:
                logger.error(f"Failed to initiate multipart upload: {e}")
                raise
        else:
            return "mock-upload-id-12345"

    def generate_presigned_part_url(self, key: str, upload_id: str, part_number: int, expires_in: int = 3600) -> str:
        if self.is_configured:
            try:
                url = self.client.generate_presigned_url(
                    ClientMethod="upload_part",
                    Params={
                        "Bucket": self.bucket,
                        "Key": key,
                        "UploadId": upload_id,
                        "PartNumber": part_number
                    },
                    ExpiresIn=expires_in
                )
                return url
            except Exception as e:
                logger.error(f"Failed to generate presigned part URL: {e}")
                raise
        else:
            return f"http://localhost:8000/mock-r2/{self.bucket}/{key}?upload_id={upload_id}&part_number={part_number}"

    def complete_multipart_upload(self, key: str, upload_id: str, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        parts format: [{"PartNumber": 1, "ETag": "..."}]
        """
        if self.is_configured:
            try:
                sorted_parts = sorted(parts, key=lambda p: p["PartNumber"])
                response = self.client.complete_multipart_upload(
                    Bucket=self.bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": sorted_parts}
                )
                return response
            except Exception as e:
                logger.error(f"Failed to complete multipart upload: {e}")
                raise
        else:
            return {"Location": f"http://localhost:8000/mock-r2/{self.bucket}/{key}", "Bucket": self.bucket, "Key": key, "ETag": "mock-etag"}

    def abort_multipart_upload(self, key: str, upload_id: str) -> Dict[str, Any]:
        if self.is_configured:
            try:
                response = self.client.abort_multipart_upload(
                    Bucket=self.bucket,
                    Key=key,
                    UploadId=upload_id
                )
                return response
            except Exception as e:
                logger.error(f"Failed to abort multipart upload: {e}")
                raise
        else:
            return {"status": "aborted"}

    def upload_file_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        """Upload raw bytes directly to R2 bucket.

        Returns:
            The public or endpoint URL of the uploaded object.
        """
        if self.is_configured:
            try:
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=data,
                    **extra_args
                )
                endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
                return f"{endpoint_url}/{self.bucket}/{key}"
            except Exception as e:
                logger.error(f"Failed to upload file bytes to R2: {e}")
                raise
        else:
            logger.info(f"[Mock R2] Uploaded {len(data)} bytes to bucket '{self.bucket}' under key '{key}'")
            return f"http://localhost:8000/mock-r2/{self.bucket}/{key}"

r2_client = R2Client()
