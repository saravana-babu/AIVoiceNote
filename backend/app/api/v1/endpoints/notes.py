from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Note, Tag, DeletedRecord
from app.schemas import schemas
from app.services.search_service import SearchService

router = APIRouter()


@router.post("/", response_model=schemas.NoteResponse)
def create_note(
    note_in: schemas.NoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = Note(
        title=note_in.title,
        duration_sec=note_in.duration_sec,
        file_path=note_in.file_path,
        status=note_in.status,
        workspace_id=note_in.workspace_id,
        user_id=current_user.id
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    background_tasks.add_task(SearchService.update_note_embedding, db, note.id)
    return note

from sqlalchemy.orm import joinedload

@router.get("/", response_model=List[schemas.NoteResponse])
def get_notes(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Note).options(joinedload(Note.tags)).filter(Note.user_id == current_user.id)
    if workspace_id:
        query = query.filter(Note.workspace_id == workspace_id)
    notes = query.all()
    
    # Map tag relations into response
    response_notes = []
    for note in notes:
        tag_list = [t.tag for t in note.tags]
        # Assign attributes manually or return serialized dict
        note_dict = {
            "id": note.id,
            "title": note.title,
            "duration_sec": note.duration_sec,
            "file_path": note.file_path,
            "status": note.status,
            "workspace_id": note.workspace_id,
            "user_id": note.user_id,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "tags": tag_list
        }
        response_notes.append(note_dict)
    return response_notes


@router.get("/{note_id}", response_model=schemas.NoteResponse)
def get_note(
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
    return {
        "id": note.id,
        "title": note.title,
        "duration_sec": note.duration_sec,
        "file_path": note.file_path,
        "status": note.status,
        "workspace_id": note.workspace_id,
        "user_id": note.user_id,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "tags": [t.tag for t in note.tags]
    }

@router.put("/{note_id}", response_model=schemas.NoteResponse)
def update_note(
    note_id: str,
    note_in: schemas.NoteUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    update_data = note_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    
    db.commit()
    db.refresh(note)
    background_tasks.add_task(SearchService.update_note_embedding, db, note.id)
    return {
        "id": note.id,
        "title": note.title,
        "duration_sec": note.duration_sec,
        "file_path": note.file_path,
        "status": note.status,
        "workspace_id": note.workspace_id,
        "user_id": note.user_id,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "tags": [t.tag for t in note.tags]
    }

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
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
    db.delete(note)
    
    from datetime import timezone
    # Log delete for offline delta synchronization
    del_rec = DeletedRecord(
        table_name="notes",
        record_id=note_id,
        deleted_at=datetime.now(timezone.utc)
    )
    db.add(del_rec)
    db.commit()
    return None

@router.post("/{note_id}/tags", response_model=schemas.NoteResponse)
def add_note_tags(
    note_id: str,
    tags: List[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Remove old tags and add new ones
    db.query(Tag).filter(Tag.note_id == note_id).delete()
    for tag_str in tags:
        db.add(Tag(note_id=note_id, tag=tag_str))
    db.commit()
    db.refresh(note)
    background_tasks.add_task(SearchService.update_note_embedding, db, note.id)
    
    return {
        "id": note.id,
        "title": note.title,
        "duration_sec": note.duration_sec,
        "file_path": note.file_path,
        "status": note.status,
        "workspace_id": note.workspace_id,
        "user_id": note.user_id,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "tags": [t.tag for t in note.tags]
    }
