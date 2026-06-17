import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Note, Transcript, StructuredSummary, Tag, DeletedRecord
from app.schemas import sync as schemas

router = APIRouter()
logger = logging.getLogger("voicemind.sync")

@router.post("/", response_model=schemas.SyncResponse)
def synchronize(
    request: schemas.SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    processed_client_task_ids = []
    
    # 1. Process client changes
    for change in request.client_changes:
        try:
            if change.table_name != "notes":
                # Currently we only sync the "notes" table, which contains nested transcripts/summaries/tags
                processed_client_task_ids.append(change.id)
                continue
                
            if change.action == "DELETE":
                db_note = db.query(Note).filter(Note.id == change.record_id, Note.user_id == current_user.id).first()
                if db_note:
                    db.delete(db_note)
                    # Log delete for other devices
                    del_rec = DeletedRecord(
                        table_name="notes",
                        record_id=change.record_id,
                        deleted_at=change.created_at
                    )
                    db.add(del_rec)
                    db.commit()
                processed_client_task_ids.append(change.id)
                
            elif change.action in ["CREATE", "UPDATE"]:
                if not change.payload:
                    processed_client_task_ids.append(change.id)
                    continue
                    
                payload = json.loads(change.payload)
                db_note = db.query(Note).filter(Note.id == change.record_id, Note.user_id == current_user.id).first()
                
                # Check for conflict resolution
                client_newer = True
                if db_note:
                    task_time = change.created_at.replace(tzinfo=None)
                    server_time = db_note.updated_at.replace(tzinfo=None)
                    if task_time <= server_time:
                        client_newer = False
                        logger.info(f"Conflict detected for Note {change.record_id}. Server is newer or equal. Server wins.")
                
                if client_newer:
                    if not db_note:
                        db_note = Note(
                            id=change.record_id,
                            title=payload.get("title", ""),
                            duration_sec=payload.get("durationSec", 0),
                            file_path=payload.get("filePath", ""),
                            status=payload.get("status", "completed"),
                            workspace_id=payload.get("workspace_id"),
                            user_id=current_user.id,
                            created_at=change.created_at.replace(tzinfo=None),
                            updated_at=change.created_at.replace(tzinfo=None)
                        )
                        db.add(db_note)
                    else:
                        db_note.title = payload.get("title", db_note.title)
                        db_note.duration_sec = payload.get("durationSec", db_note.duration_sec)
                        db_note.file_path = payload.get("filePath", db_note.file_path)
                        db_note.status = payload.get("status", db_note.status)
                        db_note.workspace_id = payload.get("workspace_id", db_note.workspace_id)
                        db_note.updated_at = change.created_at.replace(tzinfo=None)
                    
                    db.commit()
                    
                    # Update transcript
                    transcript_text = payload.get("transcription")
                    if transcript_text:
                        db_trans = db.query(Transcript).filter(Transcript.note_id == db_note.id).first()
                        if db_trans:
                            db_trans.text = transcript_text
                        else:
                            db_trans = Transcript(note_id=db_note.id, text=transcript_text)
                            db.add(db_trans)
                    
                    # Update summary (backward-compatible: store as executive type)
                    summary_text = payload.get("summary")
                    if summary_text:
                        db_sum = db.query(StructuredSummary).filter(
                            StructuredSummary.note_id == db_note.id,
                            StructuredSummary.summary_type == "executive"
                        ).first()
                        if db_sum:
                            db_sum.structured_data = json.dumps({"summary": summary_text})
                        else:
                            db_sum = StructuredSummary(
                                note_id=db_note.id,
                                summary_type="executive",
                                structured_data=json.dumps({"summary": summary_text}),
                                provider="sync",
                                model="sync"
                            )
                            db.add(db_sum)
                    
                    # Update tags
                    tags_list = payload.get("tags", [])
                    if tags_list is not None:
                        db.query(Tag).filter(Tag.note_id == db_note.id).delete()
                        for tag_str in tags_list:
                            db.add(Tag(note_id=db_note.id, tag=tag_str))
                    
                    db.commit()
                
                processed_client_task_ids.append(change.id)
        except Exception as e:
            logger.error(f"Failed to process client change task {change.id}: {e}", exc_info=True)
            continue
            
    # 2. Get server changes since last_sync_timestamp
    from datetime import timezone
    server_timestamp = datetime.now(timezone.utc)
    server_changes = []
    deleted_record_ids = []
    
    last_sync = request.last_sync_timestamp
    if last_sync:
        last_sync = last_sync.replace(tzinfo=None)
        
        # Get updated notes
        notes = db.query(Note).filter(Note.user_id == current_user.id, Note.updated_at > last_sync).all()
        for note in notes:
            tag_list = [t.tag for t in note.tags]
            trans = db.query(Transcript).filter(Transcript.note_id == note.id).first()
            summary = db.query(StructuredSummary).filter(StructuredSummary.note_id == note.id).first()
            summary_text = None
            if summary:
                try:
                    data = json.loads(summary.structured_data) if isinstance(summary.structured_data, str) else summary.structured_data
                    summary_text = data.get("summary", json.dumps(data))
                except (json.JSONDecodeError, TypeError):
                    summary_text = str(summary.structured_data)
            
            server_changes.append(
                schemas.ServerNoteDelta(
                    id=note.id,
                    title=note.title,
                    duration_sec=note.duration_sec,
                    file_path=note.file_path,
                    status=note.status,
                    workspace_id=note.workspace_id,
                    user_id=note.user_id,
                    created_at=note.created_at,
                    updated_at=note.updated_at,
                    transcription=trans.text if trans else None,
                    summary=summary_text,
                    tags=tag_list
                )
            )
            
        # Get deleted note records
        dels = db.query(DeletedRecord).filter(DeletedRecord.table_name == "notes", DeletedRecord.deleted_at > last_sync).all()
        deleted_record_ids = [d.record_id for d in dels]
    else:
        # Initial sync: pull all notes belonging to the user
        notes = db.query(Note).filter(Note.user_id == current_user.id).all()
        for note in notes:
            tag_list = [t.tag for t in note.tags]
            trans = db.query(Transcript).filter(Transcript.note_id == note.id).first()
            summary = db.query(StructuredSummary).filter(StructuredSummary.note_id == note.id).first()
            summary_text = None
            if summary:
                try:
                    data = json.loads(summary.structured_data) if isinstance(summary.structured_data, str) else summary.structured_data
                    summary_text = data.get("summary", json.dumps(data))
                except (json.JSONDecodeError, TypeError):
                    summary_text = str(summary.structured_data)
            
            server_changes.append(
                schemas.ServerNoteDelta(
                    id=note.id,
                    title=note.title,
                    duration_sec=note.duration_sec,
                    file_path=note.file_path,
                    status=note.status,
                    workspace_id=note.workspace_id,
                    user_id=note.user_id,
                    created_at=note.created_at,
                    updated_at=note.updated_at,
                    transcription=trans.text if trans else None,
                    summary=summary_text,
                    tags=tag_list
                )
            )
            
    return schemas.SyncResponse(
        server_changes=server_changes,
        deleted_record_ids=deleted_record_ids,
        server_timestamp=server_timestamp,
        processed_client_task_ids=processed_client_task_ids
    )
