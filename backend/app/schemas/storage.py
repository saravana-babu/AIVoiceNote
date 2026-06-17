from pydantic import BaseModel
from typing import List, Optional

class PresignUploadResponse(BaseModel):
    url: str
    key: str

class PresignDownloadResponse(BaseModel):
    url: str

class MultipartInitiateRequest(BaseModel):
    purpose: str  # "audio" or "export"
    extension: str  # "m4a", "wav", "mp3", "json", etc.

class MultipartInitiateResponse(BaseModel):
    upload_id: str
    key: str

class MultipartPresignPartsRequest(BaseModel):
    key: str
    upload_id: str
    part_numbers: List[int]

class PartPresignedUrl(BaseModel):
    part_number: int
    url: str

class MultipartPresignPartsResponse(BaseModel):
    parts: List[PartPresignedUrl]

class MultipartPartInfo(BaseModel):
    part_number: int
    etag: str

class MultipartCompleteRequest(BaseModel):
    key: str
    upload_id: str
    parts: List[MultipartPartInfo]

class MultipartCompleteResponse(BaseModel):
    location: str
    key: str

class MultipartAbortRequest(BaseModel):
    key: str
    upload_id: str

class MultipartAbortResponse(BaseModel):
    status: str
