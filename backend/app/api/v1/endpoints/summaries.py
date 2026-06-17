"""
AI Summary Generation API Endpoints.

Provides endpoints for generating, retrieving, and managing AI-powered
structured summaries using multiple LLM providers (OpenAI, Anthropic, Gemini).
"""

import json
import logging
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.models import User, Note, Transcript, StructuredSummary
from app.schemas import schemas
from app.services.summary_service import SummaryService, SummaryGenerationError
from app.services.prompt_templates import SummaryType
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_summary_service() -> SummaryService:
    """Create a SummaryService instance configured from application settings."""
    return SummaryService(
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


def _result_to_db_model(result, note_id: str) -> StructuredSummary:
    """Convert a SummaryResult to a StructuredSummary database model."""
    return StructuredSummary(
        note_id=note_id,
        summary_type=result.summary_type.value,
        structured_data=json.dumps(result.structured_data, ensure_ascii=False),
        provider=result.provider,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def _model_to_response(model: StructuredSummary) -> schemas.StructuredSummaryResponse:
    """Convert a StructuredSummary DB model to a Pydantic response, parsing JSON data."""
    try:
        structured_data = json.loads(model.structured_data) if isinstance(model.structured_data, str) else model.structured_data
    except (json.JSONDecodeError, TypeError):
        structured_data = {"raw": model.structured_data}

    return schemas.StructuredSummaryResponse(
        id=model.id,
        note_id=model.note_id,
        summary_type=model.summary_type,
        structured_data=structured_data,
        provider=model.provider,
        model=model.model,
        prompt_tokens=model.prompt_tokens,
        completion_tokens=model.completion_tokens,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


@router.post("/generate", response_model=schemas.SummaryGenerateResponse)
async def generate_summary(
    request: schemas.SummaryGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a single AI summary for a note.

    Requires a transcript to exist for the note. The summary is generated
    using the specified (or default) LLM provider and stored in the database.
    If a summary of the same type already exists, it will be replaced.
    """
    transcript_text = _get_transcript_text(request.note_id, current_user.id, db)

    service = _get_summary_service()
    start_time = time.monotonic()

    try:
        summary_type = SummaryType(request.summary_type)
        result = await service.generate_summary(
            transcript_text=transcript_text,
            summary_type=summary_type,
            provider_name=request.provider,
            model=request.model,
        )
    except SummaryGenerationError as e:
        logger.error("Summary generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI summary generation failed: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    generation_time_ms = (time.monotonic() - start_time) * 1000

    # Upsert: remove existing summary of the same type, then insert new
    existing = db.query(StructuredSummary).filter(
        StructuredSummary.note_id == request.note_id,
        StructuredSummary.summary_type == request.summary_type,
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    db_summary = _result_to_db_model(result, request.note_id)
    db.add(db_summary)
    db.commit()
    db.refresh(db_summary)
    background_tasks.add_task(SearchService.update_summary_embedding, db, request.note_id)

    # Trigger knowledge base indexing
    from app.services.knowledge_service import KnowledgeService
    background_tasks.add_task(KnowledgeService.index_note_artifacts, db, request.note_id)

    return schemas.SummaryGenerateResponse(
        summary=_model_to_response(db_summary),
        generation_time_ms=round(generation_time_ms, 2),
    )


@router.post("/generate-all", response_model=schemas.SummaryBatchResponse)
async def generate_all_summaries(
    request: schemas.SummaryGenerateAllRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate all 5 summary types concurrently for a note.

    Existing summaries for the note will be replaced. Returns successful
    summaries along with a list of any types that failed.
    """
    transcript_text = _get_transcript_text(request.note_id, current_user.id, db)

    service = _get_summary_service()
    start_time = time.monotonic()

    try:
        results = await service.generate_all_summaries(
            transcript_text=transcript_text,
            provider_name=request.provider,
            model=request.model,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    total_generation_time_ms = (time.monotonic() - start_time) * 1000

    # Determine which types succeeded and which failed
    succeeded_types = {r.summary_type.value for r in results}
    all_types = {t.value for t in SummaryType}
    failed_types = sorted(all_types - succeeded_types)

    # Delete existing summaries for succeeded types, then bulk insert
    for result in results:
        existing = db.query(StructuredSummary).filter(
            StructuredSummary.note_id == request.note_id,
            StructuredSummary.summary_type == result.summary_type.value,
        ).first()
        if existing:
            db.delete(existing)

    db.flush()

    db_summaries = []
    for result in results:
        db_summary = _result_to_db_model(result, request.note_id)
        db.add(db_summary)
        db_summaries.append(db_summary)

    db.commit()
    for s in db_summaries:
        db.refresh(s)
    background_tasks.add_task(SearchService.update_summary_embedding, db, request.note_id)

    # Trigger knowledge base indexing
    from app.services.knowledge_service import KnowledgeService
    background_tasks.add_task(KnowledgeService.index_note_artifacts, db, request.note_id)

    return schemas.SummaryBatchResponse(
        summaries=[_model_to_response(s) for s in db_summaries],
        total_generation_time_ms=round(total_generation_time_ms, 2),
        failed_types=failed_types,
    )


@router.get("/{note_id}", response_model=List[schemas.StructuredSummaryResponse])
def get_summaries(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all AI-generated summaries for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    summaries = db.query(StructuredSummary).filter(
        StructuredSummary.note_id == note_id
    ).order_by(StructuredSummary.created_at.desc()).all()

    return [_model_to_response(s) for s in summaries]


@router.get("/{note_id}/{summary_type}", response_model=schemas.StructuredSummaryResponse)
def get_summary_by_type(
    note_id: str,
    summary_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific summary type for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Validate summary type
    try:
        SummaryType(summary_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid summary type: {summary_type}. Must be one of: executive, detailed, bullet, action_items, follow_ups"
        )

    summary = db.query(StructuredSummary).filter(
        StructuredSummary.note_id == note_id,
        StructuredSummary.summary_type == summary_type,
    ).first()

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No '{summary_type}' summary found for this note"
        )

    return _model_to_response(summary)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_summaries(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all summaries for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    db.query(StructuredSummary).filter(
        StructuredSummary.note_id == note_id
    ).delete(synchronize_session=False)
    db.commit()


@router.delete("/{note_id}/{summary_type}", status_code=status.HTTP_204_NO_CONTENT)
def delete_summary_by_type(
    note_id: str,
    summary_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific summary type for a note."""
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    deleted = db.query(StructuredSummary).filter(
        StructuredSummary.note_id == note_id,
        StructuredSummary.summary_type == summary_type,
    ).delete(synchronize_session=False)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No '{summary_type}' summary found for this note"
        )

    db.commit()
