"""Knowledge API Endpoints.

Provides routing for Collections, Document Uploads, Hybrid Search, and AI Chatbot queries.
"""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, KnowledgeCollection, KnowledgeSource, KnowledgeChunk
from app.schemas import schemas
from app.services.document_parser import DocumentParser, DocumentParserError
from app.services.knowledge_service import KnowledgeService
from app.services.knowledge_retrieval import KnowledgeRetrievalService
from app.services.knowledge_chat import KnowledgeChatService

logger = logging.getLogger(__name__)

router = APIRouter()


# --- COLLECTIONS ---

@router.get("/collections", response_model=List[schemas.KnowledgeCollectionResponse])
def get_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all collections for the user, seeding defaults if empty."""
    collections = KnowledgeService.ensure_default_collections(db, current_user.id)
    return collections


@router.post("/collections", response_model=schemas.KnowledgeCollectionResponse)
def create_collection(
    request: schemas.KnowledgeCollectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom knowledge collection."""
    # Check if duplicate name
    existing = db.query(KnowledgeCollection).filter(
        KnowledgeCollection.name.ilike(request.name.strip()),
        KnowledgeCollection.user_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Collection with this name already exists"
        )

    col = KnowledgeCollection(
        name=request.name.strip(),
        description=request.description,
        user_id=current_user.id,
    )
    db.add(col)
    db.commit()
    db.refresh(col)
    return col


@router.delete("/collections/{collection_id}", status_code=status.HTTP_200_OK)
def delete_collection(
    collection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom collection."""
    col = db.query(KnowledgeCollection).filter(
        KnowledgeCollection.id == collection_id,
        KnowledgeCollection.user_id == current_user.id
    ).first()
    if not col:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )

    # Prevent deleting seeded defaults
    default_names = [d.name.lower() for d in KnowledgeService.ensure_default_collections(db, current_user.id)[:7]]
    if col.name.lower() in default_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default seeded collections cannot be deleted"
        )

    db.delete(col)
    db.commit()
    return {"status": "success", "message": "Collection deleted successfully"}


# --- SOURCES ---

@router.get("/sources", response_model=List[schemas.KnowledgeSourceResponse])
def get_sources(
    collection_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all indexed knowledge sources for the user."""
    stmt = db.query(KnowledgeSource).filter(KnowledgeSource.user_id == current_user.id)
    if collection_id:
        stmt = stmt.filter(KnowledgeSource.collection_id == collection_id)
    return stmt.all()


@router.post("/sources/upload", response_model=schemas.KnowledgeSourceResponse)
async def upload_source_file(
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document (PDF, DOCX, MD, TXT), parse it, chunk it, and index it into a collection."""
    # Verify collection if provided
    collection_name = None
    if collection_id:
        col = db.query(KnowledgeCollection).filter(
            KnowledgeCollection.id == collection_id,
            KnowledgeCollection.user_id == current_user.id
        ).first()
        if not col:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target collection not found"
            )
        collection_name = col.name

    try:
        content = await file.read()
        
        # Upload raw document to Cloudflare R2
        import uuid
        file_id = str(uuid.uuid4())
        file_extension = os.path.splitext(file.filename or "")[1] or ".txt"
        key = f"knowledge/{current_user.id}/{file_id}{file_extension}"
        
        from app.core.r2 import r2_client
        r2_client.upload_file_bytes(
            key=key,
            data=content,
            content_type=file.content_type
        )
        
        parsed_text = DocumentParser.parse_document(file.filename, content)
    except DocumentParserError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        from app.core.metrics import track_upload_failure
        track_upload_failure()
        logger.exception("Failed to parse uploaded document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected parsing error occurred: {str(e)}"
        )

    if not parsed_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parsed text content is empty. Cannot index empty documents."
        )

    # Run indexing
    source = await KnowledgeService.index_content(
        db=db,
        title=file.filename,
        source_type="pdf" if file.filename.endswith(".pdf") else "docx" if file.filename.endswith(".docx") else "markdown" if file.filename.endswith(".md") else "text",
        content=parsed_text,
        user_id=current_user.id,
        collection_name=collection_name or "Research",  # default fallback
        file_path=key,  # R2 object key
    )
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_200_OK)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an indexed knowledge source and its chunks."""
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.user_id == current_user.id
    ).first()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found"
        )

    db.delete(source)
    db.commit()
    return {"status": "success", "message": "Source deleted successfully"}


# --- SEARCH ---

@router.post("/search", response_model=List[schemas.KnowledgeSearchResultResponse])
async def search_knowledge(
    request: schemas.KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search knowledge chunks using hybrid RRF lexical + semantic search."""
    results = await KnowledgeRetrievalService.search_hybrid(
        db=db,
        query=request.query,
        user_id=current_user.id,
        collection_id=request.collection_id,
        source_id=request.source_id,
        limit=request.limit or 20,
    )

    response_data = []
    for chunk, score in results:
        source = db.query(KnowledgeSource).filter(KnowledgeSource.id == chunk.source_id).first()
        if source:
            response_data.append(schemas.KnowledgeSearchResultResponse(
                chunk_id=chunk.id,
                source_id=source.id,
                source_title=source.title,
                source_type=source.source_type,
                content=chunk.content,
                score=score,
            ))
            
    return response_data


# --- CHAT ---

@router.post("/chat")
async def chat_knowledge(
    request: schemas.KnowledgeChatRequest,
    stream: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI chat with conversational knowledge context.
    
    If stream=true is passed, returns a server-sent events line-delimited stream.
    Otherwise returns a single JSON object.
    """
    if stream:
        async def stream_generator():
            async for chunk in KnowledgeChatService.chat_stream(
                db=db,
                message=request.message,
                user_id=current_user.id,
                collection_id=request.collection_id,
                source_id=request.source_id,
                chat_history=request.chat_history,
                provider_name=request.provider,
                model=request.model,
            ):
                yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )
    else:
        try:
            res = await KnowledgeChatService.chat(
                db=db,
                message=request.message,
                user_id=current_user.id,
                collection_id=request.collection_id,
                source_id=request.source_id,
                chat_history=request.chat_history,
                provider_name=request.provider,
                model=request.model,
            )
            return schemas.KnowledgeChatResponse(
                response=res["response"],
                citations=[schemas.KnowledgeChatCitation(**c) for c in res["citations"]],
                suggested_questions=res["suggested_questions"],
                provider=res["provider"],
                model=res["model"],
            )
        except Exception as e:
            logger.exception("AI Chat failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI Chatbot failed to respond: {str(e)}"
            )
