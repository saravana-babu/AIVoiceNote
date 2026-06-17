import logging
import json
from typing import List, Optional, Tuple
from sqlalchemy import select, or_, func, text
from sqlalchemy.orm import Session

from app.models.models import Note, NoteEmbedding, Transcript, StructuredSummary, Tag
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    norm_v1 = sum(x * x for x in v1) ** 0.5
    norm_v2 = sum(y * y for y in v2) ** 0.5
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

def extract_text_from_json(data) -> str:
    if isinstance(data, str):
        return data
    elif isinstance(data, list):
        return " ".join(extract_text_from_json(item) for item in data if item is not None)
    elif isinstance(data, dict):
        return " ".join(extract_text_from_json(val) for val in data.values() if val is not None)
    return ""

class SearchService:
    @staticmethod
    async def update_note_embedding(db: Session, note_id: str) -> None:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            logger.warning(f"Note {note_id} not found when updating note vector.")
            return
            
        tag_texts = [t.tag for t in note.tags]
        text_to_embed = note.title
        if tag_texts:
            text_to_embed += " " + " ".join(tag_texts)
            
        vector = await embedding_service.get_embedding(text_to_embed)
        
        emb = db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note_id).first()
        if not emb:
            emb = NoteEmbedding(note_id=note_id, note_vector=vector)
            db.add(emb)
        else:
            emb.note_vector = vector
        db.commit()

    @staticmethod
    async def update_transcript_embedding(db: Session, note_id: str) -> None:
        transcript = db.query(Transcript).filter(Transcript.note_id == note_id).first()
        if not transcript or not transcript.text:
            logger.warning(f"Transcript for note {note_id} not found when updating transcript vector.")
            return
            
        vector = await embedding_service.get_embedding(transcript.text)
        
        emb = db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note_id).first()
        if not emb:
            emb = NoteEmbedding(note_id=note_id, transcript_vector=vector)
            db.add(emb)
        else:
            emb.transcript_vector = vector
        db.commit()

    @staticmethod
    async def update_summary_embedding(db: Session, note_id: str) -> None:
        summaries = db.query(StructuredSummary).filter(StructuredSummary.note_id == note_id).all()
        if not summaries:
            logger.warning(f"Summaries for note {note_id} not found when updating summary vector.")
            return
            
        texts = []
        for s in summaries:
            try:
                data = json.loads(s.structured_data)
                texts.append(extract_text_from_json(data))
            except Exception:
                texts.append(s.structured_data)
                
        combined_text = " ".join(texts)
        if not combined_text.strip():
            return
            
        vector = await embedding_service.get_embedding(combined_text)
        
        emb = db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note_id).first()
        if not emb:
            emb = NoteEmbedding(note_id=note_id, summary_vector=vector)
            db.add(emb)
        else:
            emb.summary_vector = vector
        db.commit()

    @staticmethod
    async def search_lexical(db: Session, query: str, user_id: str, limit: int = 20) -> List[Tuple[Note, float]]:
        if not query:
            return []
            
        if db.bind.dialect.name == "postgresql":
            ts_vector = func.to_tsvector('english', 
                Note.title + " " + func.coalesce(Transcript.text, "")
            )
            ts_query = func.plainto_tsquery('english', query)
            
            stmt = (
                select(Note, func.ts_rank(ts_vector, ts_query).label("rank"))
                .outerjoin(Transcript, Note.id == Transcript.note_id)
                .where(Note.user_id == user_id)
                .where(ts_vector.op("@@")(ts_query))
                .order_by(text("rank DESC"))
                .limit(limit)
            )
            results = db.execute(stmt).all()
            return [(row[0], float(row[1])) for row in results]
        else:
            stmt = (
                select(Note)
                .outerjoin(Tag, Note.id == Tag.note_id)
                .outerjoin(Transcript, Note.id == Transcript.note_id)
                .outerjoin(StructuredSummary, Note.id == StructuredSummary.note_id)
                .where(Note.user_id == user_id)
                .where(
                    or_(
                        Note.title.ilike(f"%{query}%"),
                        Tag.tag.ilike(f"%{query}%"),
                        Transcript.text.ilike(f"%{query}%"),
                        StructuredSummary.structured_data.ilike(f"%{query}%")
                    )
                )
                .distinct()
            )
            notes = db.execute(stmt).scalars().all()
            
            scored_notes = []
            q_lower = query.lower()
            for note in notes:
                score = 0.0
                if q_lower in note.title.lower():
                    score += 1.0
                for tag in note.tags:
                    if q_lower in tag.tag.lower():
                        score += 0.8
                if note.transcript and q_lower in note.transcript.text.lower():
                    score += 0.5
                for summary in note.summaries:
                    if q_lower in summary.structured_data.lower():
                        score += 0.6
                scored_notes.append((note, score))
                
            scored_notes.sort(key=lambda x: x[1], reverse=True)
            return scored_notes[:limit]

    @staticmethod
    async def search_semantic(db: Session, query: str, user_id: str, limit: int = 20) -> List[Tuple[Note, float]]:
        if not query:
            return []
            
        query_vector = await embedding_service.get_embedding(query)
        
        if db.bind.dialect.name == "postgresql":
            pg_similarity = 1.0 - func.least(
                func.coalesce(NoteEmbedding.note_vector.op('<=>')(query_vector), 1.0),
                func.coalesce(NoteEmbedding.transcript_vector.op('<=>')(query_vector), 1.0),
                func.coalesce(NoteEmbedding.summary_vector.op('<=>')(query_vector), 1.0)
            )
            
            stmt = (
                select(Note, pg_similarity.label("similarity"))
                .join(NoteEmbedding, Note.id == NoteEmbedding.note_id)
                .where(Note.user_id == user_id)
                .order_by(text("similarity DESC"))
                .limit(limit)
            )
            results = db.execute(stmt).all()
            return [(row[0], float(row[1])) for row in results]
        else:
            stmt = (
                select(Note, NoteEmbedding)
                .join(NoteEmbedding, Note.id == NoteEmbedding.note_id)
                .where(Note.user_id == user_id)
            )
            db_results = db.execute(stmt).all()
            
            scored_notes = []
            for note, embedding in db_results:
                best_sim = 0.0
                for vec_attr in ["note_vector", "transcript_vector", "summary_vector"]:
                    vec = getattr(embedding, vec_attr)
                    if vec:
                        sim = cosine_similarity(vec, query_vector)
                        if sim > best_sim:
                            best_sim = sim
                if best_sim > 0.0:
                    scored_notes.append((note, best_sim))
            
            scored_notes.sort(key=lambda x: x[1], reverse=True)
            return scored_notes[:limit]

    @staticmethod
    async def search_hybrid(db: Session, query: str, user_id: str, limit: int = 20) -> List[Tuple[Note, float]]:
        fts_res = await SearchService.search_lexical(db, query, user_id, limit=limit * 2)
        semantic_res = await SearchService.search_semantic(db, query, user_id, limit=limit * 2)
        
        fts_notes = [note for note, _ in fts_res]
        semantic_notes = [note for note, _ in semantic_res]
        
        k = 60
        rrf_scores = {}
        
        for rank, note in enumerate(fts_notes, start=1):
            rrf_scores[note.id] = rrf_scores.get(note.id, [note, 0.0])
            rrf_scores[note.id][1] += 1.0 / (k + rank)
            
        for rank, note in enumerate(semantic_notes, start=1):
            rrf_scores[note.id] = rrf_scores.get(note.id, [note, 0.0])
            rrf_scores[note.id][1] += 1.0 / (k + rank)
            
        sorted_results = sorted(rrf_scores.values(), key=lambda x: x[1], reverse=True)
        return [(note, float(score)) for note, score in sorted_results[:limit]]

    @staticmethod
    async def search(db: Session, query: str, user_id: str, search_type: str = "hybrid", limit: int = 20) -> List[Tuple[Note, float, str]]:
        if search_type == "semantic":
            results = await SearchService.search_semantic(db, query, user_id, limit=limit)
            return [(note, score, "semantic") for note, score in results]
        elif search_type == "fts":
            results = await SearchService.search_lexical(db, query, user_id, limit=limit)
            return [(note, score, "fts") for note, score in results]
        else:
            results = await SearchService.search_hybrid(db, query, user_id, limit=limit)
            return [(note, score, "hybrid") for note, score in results]
