from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Note, Transcript
from app.schemas import schemas
from app.services.search_service import SearchService

router = APIRouter()

@router.post("/", response_model=schemas.TranscriptResponse)
def create_or_replace_transcript(
    transcript_in: schemas.TranscriptCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == transcript_in.note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    transcript = db.query(Transcript).filter(Transcript.note_id == transcript_in.note_id).first()
    if transcript:
        transcript.text = transcript_in.text
        transcript.confidence = transcript_in.confidence
    else:
        transcript = Transcript(
            note_id=transcript_in.note_id,
            text=transcript_in.text,
            confidence=transcript_in.confidence
        )
        db.add(transcript)

    db.commit()
    db.refresh(transcript)
    background_tasks.add_task(SearchService.update_transcript_embedding, db, transcript.note_id)
    
    # Trigger knowledge base indexing
    from app.services.knowledge_service import KnowledgeService
    background_tasks.add_task(KnowledgeService.index_note_artifacts, db, transcript.note_id)
    
    return transcript

@router.get("/{note_id}", response_model=schemas.TranscriptResponse)
def get_transcript(
    note_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    transcript = db.query(Transcript).filter(Transcript.note_id == note_id).first()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found"
        )
    return transcript
