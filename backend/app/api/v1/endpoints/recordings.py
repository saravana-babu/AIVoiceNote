import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Note, Recording
from app.schemas import schemas

from app.core.r2 import r2_client

router = APIRouter()

@router.post("/upload", response_model=schemas.RecordingResponse)
async def upload_audio(
    note_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Generate a unique key for Cloudflare R2 storage
    file_extension = os.path.splitext(file.filename or "")[1] or ".m4a"
    filename = f"{uuid.uuid4()}{file_extension}"
    key = f"audio/{current_user.id}/{filename}"

    try:
        content = await file.read()
        r2_client.upload_file_bytes(
            key=key,
            data=content,
            content_type=file.content_type
        )
    except Exception as err:
        from app.core.metrics import track_upload_failure
        track_upload_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to Cloudflare R2: {str(err)}"
        )

    # Create recording record
    recording = Recording(
        note_id=note_id,
        local_uri=key,
        is_uploaded=True
    )
    db.add(recording)
    
    # Update note file path
    note.file_path = key
    db.commit()
    db.refresh(recording)
    
    return recording

@router.get("/{recording_id}", response_model=schemas.RecordingResponse)
def get_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recording = db.query(Recording).join(Note).filter(
        Recording.id == recording_id,
        Note.user_id == current_user.id
    ).first()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found"
        )
    return recording
