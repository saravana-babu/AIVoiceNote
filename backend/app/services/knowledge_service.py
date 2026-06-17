"""Knowledge service.

Manages collections, indexing sources, text chunking, embedding generation,
and extracting relationships/tags for the Unified Knowledge Intelligence Engine.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.models.models import (
    KnowledgeCollection,
    KnowledgeSource,
    KnowledgeChunk,
    KnowledgeEmbedding,
    KnowledgeRelationship,
    KnowledgeTag,
    Note,
    Transcript,
    StructuredSummary,
    MeetingMinutes,
)
from app.services.embedding_service import embedding_service
from app.services.llm_providers import get_provider, LLMResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_COLLECTIONS = [
    ("Personal", "Personal notes, logs, and thoughts"),
    ("Work", "Professional work documents, tasks, and communications"),
    ("Meetings", "Audio recordings, transcripts, and meeting minutes"),
    ("Projects", "Project briefs, tasks, and milestones"),
    ("Clients", "Client feedback, communications, and details"),
    ("Research", "Research materials, references, and studies"),
    ("Learning", "Tutorials, educational resources, and notes"),
]


class KnowledgeService:
    @staticmethod
    def ensure_default_collections(db: Session, user_id: str) -> List[KnowledgeCollection]:
        """Verify user has default collections, creating them if not present."""
        existing = db.query(KnowledgeCollection).filter(KnowledgeCollection.user_id == user_id).all()
        if existing:
            return existing

        created = []
        for name, desc in DEFAULT_COLLECTIONS:
            col = KnowledgeCollection(
                name=name,
                description=desc,
                user_id=user_id,
            )
            db.add(col)
            created.append(col)
        
        try:
            db.commit()
            for col in created:
                db.refresh(col)
            return created
        except Exception as e:
            db.rollback()
            logger.exception("Failed to seed default collections")
            # Return any that might have been successfully queryable now
            return db.query(KnowledgeCollection).filter(KnowledgeCollection.user_id == user_id).all()

    @staticmethod
    def chunk_text(text: str, max_chars: int = 700, overlap: int = 100) -> List[str]:
        """Split text into chunks with context overlap."""
        if not text or not text.strip():
            return []
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + max_chars
            if end >= text_len:
                chunks.append(text[start:])
                break
            
            # Try to find a space or newline near the boundary to avoid breaking words
            boundary = text.rfind(" ", start, end)
            if boundary != -1 and boundary > start + (max_chars // 2):
                end = boundary
            
            chunks.append(text[start:end])
            start = end - overlap
            if start < 0:
                start = 0
            
        return [c.strip() for c in chunks if c.strip()]

    @staticmethod
    async def index_content(
        db: Session,
        title: str,
        source_type: str,
        content: str,
        user_id: str,
        collection_name: Optional[str] = None,
        note_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> KnowledgeSource:
        """Parse text content, chunk it, create embeddings, and run relationship extraction."""
        # Ensure collections exist
        collections = KnowledgeService.ensure_default_collections(db, user_id)
        
        # Resolve collection ID
        collection_id = None
        if collection_name:
            col = next((c for c in collections if c.name.lower() == collection_name.lower()), None)
            if col:
                collection_id = col.id

        # Delete any existing source for the same voice note or file
        if note_id:
            existing = db.query(KnowledgeSource).filter(
                KnowledgeSource.note_id == note_id,
                KnowledgeSource.source_type == source_type
            ).first()
            if existing:
                db.delete(existing)
                db.flush()
        elif file_path:
            existing = db.query(KnowledgeSource).filter(
                KnowledgeSource.file_path == file_path,
                KnowledgeSource.user_id == user_id
            ).first()
            if existing:
                db.delete(existing)
                db.flush()

        # Create source record
        source = KnowledgeSource(
            title=title,
            source_type=source_type,
            file_path=file_path,
            raw_content=content,
            note_id=note_id,
            user_id=user_id,
            collection_id=collection_id,
        )
        db.add(source)
        db.flush()  # populate ID

        # Chunk text
        chunks = KnowledgeService.chunk_text(content)
        for idx, chunk_content in enumerate(chunks):
            # Save chunk
            chunk = KnowledgeChunk(
                source_id=source.id,
                chunk_index=idx,
                content=chunk_content,
                token_count=len(chunk_content) // 4,  # rough approximation
            )
            db.add(chunk)
            db.flush()

            # Create embedding
            vector = await embedding_service.get_embedding(chunk_content)
            embedding = KnowledgeEmbedding(
                chunk_id=chunk.id,
                vector=vector,
            )
            db.add(embedding)

        db.commit()

        # Async background relationship extraction
        # For simplicity and test consistency, run it inline
        try:
            await KnowledgeService.extract_relationships_and_tags(db, source)
        except Exception as e:
            logger.error(f"Failed to extract relationships/tags for source {source.id}: {e}")

        db.refresh(source)
        return source

    @staticmethod
    async def extract_relationships_and_tags(db: Session, source: KnowledgeSource) -> None:
        """Extract relationships and tags from content using an LLM call."""
        if not source.raw_content or len(source.raw_content.strip()) < 20:
            return

        # Prepare LLM extraction prompt
        system_prompt = (
            "You are a Knowledge Graph Analyzer. Analyze the provided text and identify:\n"
            "1. Relationships to entities mentioned in the text (Projects, Clients, People, Topics, Action Items).\n"
            "2. Relevant tags (keywords/topics discussed).\n"
            "Output ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "relationships": [\n'
            "    {\n"
            '      "target_name": "string - entity name",\n'
            '      "target_type": "string - one of: project|client|person|topic|action_item",\n'
            '      "relationship_type": "string - one of: references|discusses|follows_up|member_of",\n'
            '      "description": "string - brief context of why they are linked"\n'
            "    }\n"
            "  ],\n"
            '  "tags": ["string - keyword"]\n'
            "}"
        )
        
        user_prompt = f"Analyze this text:\n\n{source.raw_content[:4000]}"
        provider = get_provider(settings.LLM_DEFAULT_PROVIDER)
        
        try:
            response: LLMResponse = await provider.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1,
            )
            
            # Simple JSON parse tolerating markdown fences
            from app.services.minutes_service import extract_json
            data = extract_json(response.content)
            
            # Save tags
            tags = data.get("tags", [])
            for t in tags:
                clean_tag = t.strip().lower()
                if clean_tag:
                    db.add(KnowledgeTag(source_id=source.id, tag=clean_tag))
            
            # Process relationships
            relations = data.get("relationships", [])
            for rel in relations:
                target_name = rel.get("target_name")
                target_type = rel.get("target_type", "topic")
                rel_type = rel.get("relationship_type", "references")
                desc = rel.get("description", "")
                
                if not target_name:
                    continue
                
                # Search for existing entity matching the name
                target = db.query(KnowledgeSource).filter(
                    KnowledgeSource.title.ilike(target_name.strip()),
                    KnowledgeSource.user_id == source.user_id
                ).first()
                
                if not target:
                    # Create a placeholder entity source so we can map relationships to it
                    target = KnowledgeSource(
                        title=target_name.strip(),
                        source_type=target_type,
                        user_id=source.user_id,
                    )
                    db.add(target)
                    db.flush()
                
                # Check if relationship already exists
                existing_rel = db.query(KnowledgeRelationship).filter(
                    KnowledgeRelationship.source_id == source.id,
                    KnowledgeRelationship.target_source_id == target.id
                ).first()
                
                if not existing_rel:
                    db.add(KnowledgeRelationship(
                        source_id=source.id,
                        target_source_id=target.id,
                        relationship_type=rel_type,
                        description=desc,
                    ))
            
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to complete LLM relationship extraction: {e}")
        finally:
            await provider.close()

    @staticmethod
    async def index_note_artifacts(db: Session, note_id: str) -> None:
        """Collect all text from transcript, summaries, and minutes of a note and index them."""
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return

        combined_text_parts = []
        combined_text_parts.append(f"Note Title: {note.title}")
        
        # 1. Transcript
        transcript = db.query(Transcript).filter(Transcript.note_id == note_id).first()
        if transcript and transcript.text.strip():
            combined_text_parts.append(f"Audio Transcript:\n{transcript.text}")
            
        # 2. Summaries
        summaries = db.query(StructuredSummary).filter(StructuredSummary.note_id == note_id).all()
        for s in summaries:
            combined_text_parts.append(f"AI Summary ({s.summary_type}):\n{s.structured_data}")
            
        # 3. Minutes
        minutes = db.query(MeetingMinutes).filter(MeetingMinutes.note_id == note_id).first()
        if minutes:
            combined_text_parts.append(
                f"Meeting Minutes Overview:\n{minutes.overview}\n"
                f"Agenda: {minutes.agenda}\n"
                f"Decisions: {minutes.decisions}\n"
                f"Risks: {minutes.risks}\n"
                f"Action Items: {minutes.action_items}"
            )
            
        combined_content = "\n\n---\n\n".join(combined_text_parts)
        if len(combined_content.strip()) < 10:
            return
            
        # Determine target collection based on note contents
        is_meeting = minutes is not None or "meeting" in note.title.lower()
        col_name = "Meetings" if is_meeting else "Personal"
        
        await KnowledgeService.index_content(
            db=db,
            title=note.title,
            source_type="voice_note" if not is_meeting else "meeting",
            content=combined_content,
            user_id=note.user_id,
            collection_name=col_name,
            note_id=note.id,
        )
