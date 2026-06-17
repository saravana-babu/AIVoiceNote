from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User
from app.schemas import schemas
from app.services.search_service import SearchService

router = APIRouter()

@router.get("/", response_model=List[schemas.SearchResultSchema])
async def search_notes(
    q: str = Query(..., description="Search query string"),
    type: str = Query("hybrid", description="Search type (semantic, fts, hybrid)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = await SearchService.search(db, query=q, user_id=current_user.id, search_type=type, limit=limit)
    
    response_results = []
    for note, score, match_type in results:
        tag_list = [t.tag for t in note.tags]
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
        response_results.append({
            "note": note_dict,
            "score": score,
            "match_type": match_type
        })
    return response_results
