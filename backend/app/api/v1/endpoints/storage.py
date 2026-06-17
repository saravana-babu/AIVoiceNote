import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.api.deps import get_current_user
from app.models.models import User
from app.schemas import storage as schemas
from app.core.r2 import r2_client

router = APIRouter()

def validate_key_ownership(key: str, user_id: str) -> None:
    """Enforces that object keys are strictly nested within the user's specific path."""
    parts = key.split("/")
    if len(parts) < 3 or parts[1] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this object key."
        )

@router.get("/presign-upload", response_model=schemas.PresignUploadResponse)
def get_presigned_upload_url(
    purpose: str = Query(..., description="Purpose: 'audio' or 'export'"),
    extension: str = Query(..., description="File extension, e.g. 'm4a', 'wav', 'json'"),
    current_user: User = Depends(get_current_user)
):
    if purpose not in ["audio", "export"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purpose must be either 'audio' or 'export'"
        )
    
    # Generate structured object key to prevent namespace pollution or collisions
    file_id = str(uuid.uuid4())
    key = f"{purpose}/{current_user.id}/{file_id}.{extension.strip('.')}"
    
    try:
        url = r2_client.generate_presigned_upload_url(key)
        return {"url": url, "key": key}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned upload URL: {str(err)}"
        )

@router.get("/presign-download", response_model=schemas.PresignDownloadResponse)
def get_presigned_download_url(
    key: str = Query(..., description="Cloud storage object key"),
    current_user: User = Depends(get_current_user)
):
    validate_key_ownership(key, current_user.id)
    try:
        url = r2_client.generate_presigned_download_url(key)
        return {"url": url}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned download URL: {str(err)}"
        )

@router.post("/multipart/initiate", response_model=schemas.MultipartInitiateResponse)
def initiate_multipart_upload(
    request: schemas.MultipartInitiateRequest,
    current_user: User = Depends(get_current_user)
):
    if request.purpose not in ["audio", "export"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purpose must be either 'audio' or 'export'"
        )
        
    file_id = str(uuid.uuid4())
    key = f"{request.purpose}/{current_user.id}/{file_id}.{request.extension.strip('.')}"
    
    try:
        upload_id = r2_client.initiate_multipart_upload(key)
        return {"upload_id": upload_id, "key": key}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate multipart upload: {str(err)}"
        )

@router.post("/multipart/presign-parts", response_model=schemas.MultipartPresignPartsResponse)
def get_presigned_part_urls(
    request: schemas.MultipartPresignPartsRequest,
    current_user: User = Depends(get_current_user)
):
    validate_key_ownership(request.key, current_user.id)
    try:
        parts = []
        for part_num in request.part_numbers:
            url = r2_client.generate_presigned_part_url(
                key=request.key,
                upload_id=request.upload_id,
                part_number=part_num
            )
            parts.append({"part_number": part_num, "url": url})
        return {"parts": parts}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate presigned part URLs: {str(err)}"
        )

@router.post("/multipart/complete", response_model=schemas.MultipartCompleteResponse)
def complete_multipart_upload(
    request: schemas.MultipartCompleteRequest,
    current_user: User = Depends(get_current_user)
):
    validate_key_ownership(request.key, current_user.id)
    try:
        # Convert schemas to boto3 format
        parts_list = [
            {"PartNumber": part.part_number, "ETag": part.etag}
            for part in request.parts
        ]
        response = r2_client.complete_multipart_upload(
            key=request.key,
            upload_id=request.upload_id,
            parts=parts_list
        )
        location = response.get("Location") or f"https://r2.voicemind.ai/{request.key}"
        return {"location": location, "key": request.key}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete multipart upload: {str(err)}"
        )

@router.post("/multipart/abort", response_model=schemas.MultipartAbortResponse)
def abort_multipart_upload(
    request: schemas.MultipartAbortRequest,
    current_user: User = Depends(get_current_user)
):
    validate_key_ownership(request.key, current_user.id)
    try:
        r2_client.abort_multipart_upload(
            key=request.key,
            upload_id=request.upload_id
        )
        return {"status": "aborted"}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to abort multipart upload: {str(err)}"
        )

