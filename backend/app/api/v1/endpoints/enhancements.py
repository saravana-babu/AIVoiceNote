"""Note enhancements API endpoints.

Provides endpoints for generating, retrieving, and deleting note enhancements.
"""

import json
import logging
import time
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.models import User, Note, Transcript, NoteEnhancement
from app.schemas import schemas
from app.services.enhancement_service import EnhancementService, EnhancementGenerationError
from app.services.enhancement_prompts import EnhancementType

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_enhancement_service() -> EnhancementService:
    """Create an EnhancementService instance configured from settings."""
    return EnhancementService(
        default_provider=settings.LLM_DEFAULT_PROVIDER,
        default_temperature=settings.LLM_TEMPERATURE,
        default_max_tokens=settings.LLM_MAX_TOKENS,
    )


def _get_transcript_text(note_id: str, user_id: str, db: Session) -> str:
    """Fetch and validate transcript text for a note. Raises HTTPException if not found."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    transcript = db.query(Transcript).filter(Transcript.note_id == note_id).first()
    if not transcript or not transcript.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transcript found for this note. Please transcribe the audio first."
        )

    return transcript.text


def _result_to_db_model(result, note_id: str) -> NoteEnhancement:
    """Convert an EnhancementResult to a NoteEnhancement database model."""
    return NoteEnhancement(
        note_id=note_id,
        enhancement_type=result.enhancement_type.value,
        structured_data=json.dumps(result.structured_data, ensure_ascii=False),
        provider=result.provider,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _model_to_response(model: NoteEnhancement) -> schemas.NoteEnhancementResponse:
    """Convert a NoteEnhancement DB model to a Pydantic response, deserializing JSON columns."""
    try:
        structured_data = json.loads(model.structured_data) if isinstance(model.structured_data, str) else model.structured_data
    except Exception:
        structured_data = {}

    return schemas.NoteEnhancementResponse(
        id=model.id,
        note_id=model.note_id,
        enhancement_type=model.enhancement_type,
        structured_data=structured_data,
        provider=model.provider,
        model=model.model,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.post("/generate", response_model=schemas.NoteEnhancementGenerateResponse)
async def generate_note_enhancement(
    request: schemas.NoteEnhancementGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate an enhanced version of a note transcript.
    
    Supported types: improved, professional, blog, executive_report, email, project_update
    
    If an enhancement of the same type already exists for this note, it will be replaced.
    """
    # Validate enhancement type
    try:
        enh_type = EnhancementType(request.enhancement_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid enhancement_type. Supported values: {[t.value for t in EnhancementType]}"
        )

    transcript_text = _get_transcript_text(request.note_id, current_user.id, db)
    service = _get_enhancement_service()
    start_time = time.monotonic()

    try:
        result = await service.generate_enhancement(
            text=transcript_text,
            enhancement_type=enh_type,
            provider_name=request.provider,
            model=request.model,
        )
    except (EnhancementGenerationError, ValueError) as e:
        logger.error("Note enhancement generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI note enhancement generation failed: {str(e)}"
        )

    generation_time_ms = (time.monotonic() - start_time) * 1000

    # Delete existing of the same type for this note
    existing = db.query(NoteEnhancement).filter(
        NoteEnhancement.note_id == request.note_id,
        NoteEnhancement.enhancement_type == request.enhancement_type
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    db_enhancement = _result_to_db_model(result, request.note_id)
    db.add(db_enhancement)
    db.commit()
    db.refresh(db_enhancement)

    return schemas.NoteEnhancementGenerateResponse(
        enhancement=_model_to_response(db_enhancement),
        generation_time_ms=round(generation_time_ms, 2),
    )


@router.get("/note/{note_id}", response_model=List[schemas.NoteEnhancementResponse])
def get_note_enhancements(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all enhancements generated for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    enhancements = db.query(NoteEnhancement).filter(NoteEnhancement.note_id == note_id).all()
    return [_model_to_response(e) for e in enhancements]


@router.delete("/{enhancement_id}", status_code=status.HTTP_200_OK)
def delete_note_enhancement(
    enhancement_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note enhancement."""
    enhancement = db.query(NoteEnhancement).filter(NoteEnhancement.id == enhancement_id).first()
    if not enhancement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note enhancement not found"
        )

    # Check that note belongs to current user
    note = db.query(Note).filter(Note.id == enhancement.note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this enhancement"
        )

    db.delete(enhancement)
    db.commit()
    return {"status": "success", "message": "Note enhancement deleted successfully"}
