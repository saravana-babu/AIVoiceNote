"""Meeting minutes API endpoints.

Provides endpoints for generating, retrieving, and deleting structured meeting minutes.
"""

import json
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.models import User, Note, Transcript, MeetingMinutes
from app.schemas import schemas
from app.services.minutes_service import MinutesService, MinutesGenerationError

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_minutes_service() -> MinutesService:
    """Create a MinutesService instance configured from settings."""
    return MinutesService(
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


def _result_to_db_model(result, note_id: str) -> MeetingMinutes:
    """Convert a MinutesResult to a MeetingMinutes database model."""
    data = result.structured_data
    return MeetingMinutes(
        note_id=note_id,
        overview=data.get("overview", ""),
        agenda=json.dumps(data.get("agenda", []), ensure_ascii=False),
        discussion_points=json.dumps(data.get("discussion_points", []), ensure_ascii=False),
        decisions=json.dumps(data.get("decisions", []), ensure_ascii=False),
        risks=json.dumps(data.get("risks", []), ensure_ascii=False),
        action_items=json.dumps(data.get("action_items", []), ensure_ascii=False),
        provider=result.provider,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _model_to_response(model: MeetingMinutes) -> schemas.MeetingMinutesResponse:
    """Convert a MeetingMinutes DB model to a Pydantic response, deserializing JSON columns."""
    try:
        agenda = json.loads(model.agenda) if isinstance(model.agenda, str) else model.agenda
    except (json.JSONDecodeError, TypeError):
        agenda = []

    try:
        discussion_points = json.loads(model.discussion_points) if isinstance(model.discussion_points, str) else model.discussion_points
    except (json.JSONDecodeError, TypeError):
        discussion_points = []

    try:
        decisions = json.loads(model.decisions) if isinstance(model.decisions, str) else model.decisions
    except (json.JSONDecodeError, TypeError):
        decisions = []

    try:
        risks = json.loads(model.risks) if isinstance(model.risks, str) else model.risks
    except (json.JSONDecodeError, TypeError):
        risks = []

    try:
        action_items = json.loads(model.action_items) if isinstance(model.action_items, str) else model.action_items
    except (json.JSONDecodeError, TypeError):
        action_items = []

    return schemas.MeetingMinutesResponse(
        note_id=model.note_id,
        overview=model.overview,
        agenda=agenda,
        discussion_points=discussion_points,
        decisions=decisions,
        risks=risks,
        action_items=action_items,
        provider=model.provider,
        model=model.model,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.post("/generate", response_model=schemas.MeetingMinutesGenerateResponse)
async def generate_meeting_minutes(
    request: schemas.MeetingMinutesGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate structured meeting minutes for a note transcript.
    
    If meeting minutes already exist for this note, they will be replaced.
    """
    transcript_text = _get_transcript_text(request.note_id, current_user.id, db)
    service = _get_minutes_service()
    start_time = time.monotonic()

    try:
        result = await service.generate_minutes(
            transcript_text=transcript_text,
            provider_name=request.provider,
            model=request.model,
        )
    except MinutesGenerationError as e:
        logger.error("Meeting minutes generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI meeting minutes generation failed: {str(e)}"
        )

    generation_time_ms = (time.monotonic() - start_time) * 1000

    # Delete existing if present
    existing = db.query(MeetingMinutes).filter(MeetingMinutes.note_id == request.note_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    db_minutes = _result_to_db_model(result, request.note_id)
    db.add(db_minutes)
    db.commit()
    db.refresh(db_minutes)

    # Trigger knowledge base indexing
    from app.services.knowledge_service import KnowledgeService
    background_tasks.add_task(KnowledgeService.index_note_artifacts, db, request.note_id)

    return schemas.MeetingMinutesGenerateResponse(
        minutes=_model_to_response(db_minutes),
        generation_time_ms=round(generation_time_ms, 2),
    )


@router.get("/note/{note_id}", response_model=schemas.MeetingMinutesResponse)
def get_meeting_minutes(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve existing meeting minutes for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    minutes = db.query(MeetingMinutes).filter(MeetingMinutes.note_id == note_id).first()
    if not minutes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No meeting minutes found for this note."
        )

    return _model_to_response(minutes)


@router.delete("/note/{note_id}", status_code=status.HTTP_200_OK)
def delete_meeting_minutes(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete meeting minutes for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    minutes = db.query(MeetingMinutes).filter(MeetingMinutes.note_id == note_id).first()
    if not minutes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No meeting minutes found for this note."
        )

    db.delete(minutes)
    db.commit()
    return {"status": "success", "message": "Meeting minutes deleted successfully"}
