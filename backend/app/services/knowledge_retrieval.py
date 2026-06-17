"""Knowledge Retrieval Service.

Implements lexical (FTS), semantic (vector), and hybrid search (RRF) with recency
boosting and collection/source filtering.
"""

import logging
import json
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, or_, func, text
from sqlalchemy.orm import Session

from app.models.models import (
    KnowledgeSource,
    KnowledgeChunk,
    KnowledgeEmbedding,
    KnowledgeCollection,
    KnowledgeRelationship,
)
from app.services.embedding_service import embedding_service
from app.services.search_service import cosine_similarity

logger = logging.getLogger(__name__)


class KnowledgeRetrievalService:
    @staticmethod
    async def search_lexical(
        db: Session,
        query: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """Perform full-text or substring keyword search on chunks."""
        if not query:
            return []

        # Join Chunk -> Source
        stmt = (
            select(KnowledgeChunk)
            .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
            .where(KnowledgeSource.user_id == user_id)
        )

        if collection_id:
            stmt = stmt.where(KnowledgeSource.collection_id == collection_id)
        if source_id:
            stmt = stmt.where(KnowledgeSource.id == source_id)

        # Handle DB engine differences
        if db.bind.dialect.name == "postgresql":
            # PostgreSQL full-text search
            ts_vector = func.to_tsvector('english', KnowledgeChunk.content)
            ts_query = func.plainto_tsquery('english', query)
            stmt = (
                stmt.where(ts_vector.op("@@")(ts_query))
                .order_by(text("rank DESC"))
            )
            # Add rank select
            stmt = stmt.add_columns(func.ts_rank(ts_vector, ts_query).label("rank"))
            results = db.execute(stmt).all()
            return [(row[0], float(row[1])) for row in results[:limit]]
        else:
            # SQLite case-insensitive fallback substring search
            stmt = stmt.where(KnowledgeChunk.content.ilike(f"%{query}%"))
            chunks = db.execute(stmt).scalars().all()
            
            # Simple keyword frequency score
            scored = []
            q_words = query.lower().split()
            for chunk in chunks:
                score = 0.0
                content_lower = chunk.content.lower()
                for word in q_words:
                    score += content_lower.count(word) * 1.0
                if score > 0.0:
                    scored.append((chunk, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:limit]

    @staticmethod
    async def search_semantic(
        db: Session,
        query: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """Perform semantic search using vector distance."""
        if not query:
            return []

        query_vector = await embedding_service.get_embedding(query)

        # Base statement
        stmt = (
            select(KnowledgeChunk)
            .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
            .join(KnowledgeEmbedding, KnowledgeChunk.id == KnowledgeEmbedding.chunk_id)
            .where(KnowledgeSource.user_id == user_id)
        )

        if collection_id:
            stmt = stmt.where(KnowledgeSource.collection_id == collection_id)
        if source_id:
            stmt = stmt.where(KnowledgeSource.id == source_id)

        if db.bind.dialect.name == "postgresql":
            # pgvector cosine similarity
            pg_similarity = 1.0 - KnowledgeEmbedding.vector.op('<=>')(query_vector)
            stmt = (
                stmt.add_columns(pg_similarity.label("similarity"))
                .order_by(text("similarity DESC"))
            )
            results = db.execute(stmt).all()
            return [(row[0], float(row[1])) for row in results[:limit]]
        else:
            # SQLite mock vector search loaded in python
            stmt = stmt.add_columns(KnowledgeEmbedding.vector)
            db_results = db.execute(stmt).all()
            
            scored = []
            for chunk, vec_data in db_results:
                # vec_data is list or json string
                if isinstance(vec_data, str):
                    try:
                        vector = json.loads(vec_data)
                    except Exception:
                        continue
                else:
                    vector = vec_data
                
                sim = cosine_similarity(vector, query_vector)
                if sim > 0.1:  # threshold
                    scored.append((chunk, sim))
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:limit]

    @staticmethod
    async def search_hybrid(
        db: Session,
        query: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """Merge lexical and semantic search ranks using RRF and apply recency boost."""
        lexical_res = await KnowledgeRetrievalService.search_lexical(
            db, query, user_id, collection_id, source_id, limit=limit * 2
        )
        semantic_res = await KnowledgeRetrievalService.search_semantic(
            db, query, user_id, collection_id, source_id, limit=limit * 2
        )

        # Reciprocal Rank Fusion (RRF)
        k = 60
        rrf_scores = {}  # chunk_id -> (chunk, rrf_score)

        for rank, (chunk, _) in enumerate(lexical_res, start=1):
            rrf_scores[chunk.id] = [chunk, 1.0 / (k + rank)]

        for rank, (chunk, _) in enumerate(semantic_res, start=1):
            if chunk.id not in rrf_scores:
                rrf_scores[chunk.id] = [chunk, 0.0]
            rrf_scores[chunk.id][1] += 1.0 / (k + rank)

        # Apply recency boost
        now = datetime.utcnow()
        sorted_results = []
        
        for chunk_id, (chunk, rrf_score) in rrf_scores.items():
            # Get parent source
            source = db.query(KnowledgeSource).filter(KnowledgeSource.id == chunk.source_id).first()
            if not source:
                continue

            # Boost factor: recent files (within last 30 days) get a higher boost
            days_old = (now - source.created_at).days
            if days_old < 0:
                days_old = 0
            
            # Recency boost scales from 1.0 (recent) down to 0.7 (very old)
            recency_boost = 0.7 + (0.3 / (1.0 + (days_old * 0.03)))
            final_score = rrf_score * recency_boost
            sorted_results.append((chunk, final_score))

        sorted_results.sort(key=lambda x: x[1], reverse=True)
        return sorted_results[:limit]

    @staticmethod
    async def build_context(
        db: Session,
        query: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        max_tokens: int = 4000,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Retrieve relevant chunks, merge action items, and compile a compressed context."""
        # Retrieve top 8 chunks using hybrid search
        results = await KnowledgeRetrievalService.search_hybrid(
            db, query, user_id, collection_id, source_id, limit=8
        )

        if not results:
            return "", []

        citations = []
        citation_map = {}  # source_id -> citation_index
        context_parts = []
        total_chars = 0
        char_limit = max_tokens * 3  # rough estimate (1 token ~ 3-4 chars)

        # Header for the context block
        context_parts.append("# Retrieved Knowledge Context\n")

        for idx, (chunk, score) in enumerate(results):
            # Fetch source details
            source = db.query(KnowledgeSource).filter(KnowledgeSource.id == chunk.source_id).first()
            if not source:
                continue

            # Assign citation index
            if source.id not in citation_map:
                cit_idx = len(citations) + 1
                citation_map[source.id] = cit_idx
                citations.append({
                    "id": source.id,
                    "index": cit_idx,
                    "title": source.title,
                    "source_type": source.source_type,
                    "note_id": source.note_id,
                })
            else:
                cit_idx = citation_map[source.id]

            # Build markdown block for the chunk
            chunk_header = f"## [{cit_idx}] {source.title} (Type: {source.source_type})\n"
            chunk_body = f"{chunk.content}\n"
            
            # Check length limit
            block_len = len(chunk_header) + len(chunk_body)
            if total_chars + block_len > char_limit:
                # If we're full, skip lower ranking items
                break

            context_parts.append(chunk_header + chunk_body)
            total_chars += block_len

        # Also pull linked relationship context (e.g. Project or Client descriptions if matches exist)
        # Scan retrieved citations for any relationships
        for cit in list(citations):
            source_id = cit["id"]
            rels = db.query(KnowledgeRelationship).filter(
                or_(
                    KnowledgeRelationship.source_id == source_id,
                    KnowledgeRelationship.target_source_id == source_id
                )
            ).all()
            
            for rel in rels:
                # Fetch target source description
                target_id = rel.target_source_id if rel.source_id == source_id else rel.source_id
                if target_id in citation_map:
                    continue  # already cited

                target_source = db.query(KnowledgeSource).filter(KnowledgeSource.id == target_id).first()
                if target_source and target_source.raw_content and len(target_source.raw_content) < 1000:
                    cit_idx = len(citations) + 1
                    citation_map[target_source.id] = cit_idx
                    citations.append({
                        "id": target_source.id,
                        "index": cit_idx,
                        "title": target_source.title,
                        "source_type": target_source.source_type,
                        "note_id": target_source.note_id,
                    })
                    
                    rel_header = f"## [{cit_idx}] Related Entity: {target_source.title} (Type: {target_source.source_type})\n"
                    rel_body = f"Context: This is linked via relationship '{rel.relationship_type}'. Details:\n{target_source.raw_content}\n"
                    context_parts.append(rel_header + rel_body)

        compiled_context = "\n".join(context_parts)
        return compiled_context, citations
