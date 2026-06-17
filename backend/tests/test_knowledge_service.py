"""Tests for the Unified Knowledge Intelligence Engine.

Covers parsing, chunking, indexing, relationship graph extraction, hybrid search retrieval,
conversational citation chats (streaming & non-streaming), and HTTP endpoints.
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.models import (
    User,
    Note,
    Transcript,
    StructuredSummary,
    MeetingMinutes,
    KnowledgeCollection,
    KnowledgeSource,
    KnowledgeChunk,
    KnowledgeEmbedding,
    KnowledgeRelationship,
    KnowledgeTag,
)
from app.services.document_parser import DocumentParser, DocumentParserError
from app.services.knowledge_service import KnowledgeService, DEFAULT_COLLECTIONS
from app.services.knowledge_retrieval import KnowledgeRetrievalService
from app.services.knowledge_chat import KnowledgeChatService
from app.services.llm_providers import LLMResponse


# ---------------------------------------------------------------------------
# 1. Document Parser Tests
# ---------------------------------------------------------------------------

def test_document_parser_txt_md():
    content = b"Hello, this is a plain text file content."
    parsed = DocumentParser.parse_txt(content)
    assert parsed == "Hello, this is a plain text file content."

    parsed_md = DocumentParser.parse_md(content)
    assert parsed_md == "Hello, this is a plain text file content."

    # Unicode decode fallback
    content_latin = "Hello \xbfQué tal?".encode("latin-1")
    parsed_latin = DocumentParser.parse_txt(content_latin)
    assert "Qué tal" in parsed_latin


def test_document_parser_unsupported_and_empty():
    # Pass None to force an AttributeError in decode, raising DocumentParserError
    with pytest.raises(DocumentParserError):
        DocumentParser.parse_document("test.xyz", None)


@patch("app.services.document_parser.PdfReader")
def test_document_parser_pdf(mock_pdf_reader):
    # Mock PDF Pages
    mock_page_1 = MagicMock()
    mock_page_1.extract_text.return_value = "Page 1 content."
    mock_page_2 = MagicMock()
    mock_page_2.extract_text.return_value = "Page 2 content."

    mock_reader_instance = MagicMock()
    mock_reader_instance.pages = [mock_page_1, mock_page_2]
    mock_pdf_reader.return_value = mock_reader_instance

    parsed = DocumentParser.parse_pdf(b"dummy pdf bytes")
    assert parsed == "Page 1 content.\nPage 2 content."


@patch("app.services.document_parser.Document")
def test_document_parser_docx(mock_docx_doc):
    # Mock Paragraphs and Tables
    mock_para_1 = MagicMock()
    mock_para_1.text = "Paragraph 1 text."
    mock_para_2 = MagicMock()
    mock_para_2.text = "Paragraph 2 text."

    mock_cell_1 = MagicMock()
    mock_cell_1.text = "Cell A"
    mock_cell_2 = MagicMock()
    mock_cell_2.text = "Cell B"
    mock_row = MagicMock()
    mock_row.cells = [mock_cell_1, mock_cell_2]
    mock_table = MagicMock()
    mock_table.rows = [mock_row]

    mock_doc_instance = MagicMock()
    mock_doc_instance.paragraphs = [mock_para_1, mock_para_2]
    mock_doc_instance.tables = [mock_table]
    mock_docx_doc.return_value = mock_doc_instance

    parsed = DocumentParser.parse_docx(b"dummy docx bytes")
    assert "Paragraph 1 text." in parsed
    assert "Cell A | Cell B" in parsed


# ---------------------------------------------------------------------------
# 2. Chunking & Seeding Tests
# ---------------------------------------------------------------------------

def test_chunk_text():
    # Empty text
    assert KnowledgeService.chunk_text("") == []
    assert KnowledgeService.chunk_text("   ") == []

    # Small text
    text_short = "Hello Antigravity."
    chunks_short = KnowledgeService.chunk_text(text_short, max_chars=50, overlap=10)
    assert chunks_short == ["Hello Antigravity."]

    # Longer text with sentence boundaries
    text_long = (
        "The Unified Knowledge Intelligence Engine is designed to index all artifacts. "
        "It supports voice notes, transcripts, structured summaries, and minutes. "
        "By doing hybrid search and RRF, the LLM retrieves high quality citations."
    )
    # Force splitting by keeping max_chars small
    chunks_long = KnowledgeService.chunk_text(text_long, max_chars=80, overlap=15)
    assert len(chunks_long) > 1
    # Check that chunks are not empty
    for chunk in chunks_long:
        assert len(chunk.strip()) > 0


def test_ensure_default_collections(db: Session):
    user_id = "test_user_uuid"
    collections = KnowledgeService.ensure_default_collections(db, user_id)
    assert len(collections) == len(DEFAULT_COLLECTIONS)
    
    names = [c.name for c in collections]
    assert "Personal" in names
    assert "Work" in names
    assert "Meetings" in names

    # Call again - should return the same without duplicating
    collections_again = KnowledgeService.ensure_default_collections(db, user_id)
    assert len(collections_again) == len(DEFAULT_COLLECTIONS)


# ---------------------------------------------------------------------------
# 3. Indexing & Relationship Graph Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.knowledge_service.embedding_service.get_embedding")
async def test_index_content_without_relations(mock_get_embedding, db: Session):
    # Setup mock embedding (768 dim)
    mock_get_embedding.return_value = [0.1] * 768
    user_id = "test_user"

    # Index document content
    source = await KnowledgeService.index_content(
        db=db,
        title="Antigravity Pitch",
        source_type="markdown",
        content="AI Coding Assistant named Antigravity will make pair programming extremely fun.",
        user_id=user_id,
        collection_name="Research",
    )

    assert source.id is not None
    assert source.title == "Antigravity Pitch"
    assert source.source_type == "markdown"
    assert len(source.chunks) == 1
    assert source.chunks[0].content == "AI Coding Assistant named Antigravity will make pair programming extremely fun."

    # Validate db objects
    chunk_id = source.chunks[0].id
    emb_record = db.query(KnowledgeEmbedding).filter(KnowledgeEmbedding.chunk_id == chunk_id).first()
    assert emb_record is not None
    assert len(emb_record.vector) == 768


@pytest.mark.asyncio
@patch("app.services.knowledge_service.embedding_service.get_embedding")
@patch("app.services.knowledge_service.get_provider")
async def test_extract_relationships_and_tags(mock_get_provider, mock_get_embedding, db: Session):
    mock_get_embedding.return_value = [0.0] * 768

    # Mock LLM provider returns JSON string representing relationships/tags
    mock_llm_response = LLMResponse(
        content=json.dumps({
            "tags": ["antigravity", "agent"],
            "relationships": [
                {
                    "target_name": "Project Gemini",
                    "target_type": "project",
                    "relationship_type": "member_of",
                    "description": "Antigravity is a key part of Project Gemini workspace."
                }
            ]
        }),
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    
    mock_provider_instance = AsyncMock()
    mock_provider_instance.generate.return_value = mock_llm_response
    mock_provider_instance.close.return_value = None
    mock_get_provider.return_value = mock_provider_instance

    user_id = "user_relation_test"
    source = await KnowledgeService.index_content(
        db=db,
        title="Antigravity System Details",
        source_type="text",
        content="Antigravity assistant is part of Project Gemini. It automates coding tasks.",
        user_id=user_id,
        collection_name="Work"
    )

    # Verify tags and relationships got written
    tags = db.query(KnowledgeTag).filter(KnowledgeTag.source_id == source.id).all()
    assert len(tags) == 2
    assert {t.tag for t in tags} == {"antigravity", "agent"}

    relationships = db.query(KnowledgeRelationship).filter(KnowledgeRelationship.source_id == source.id).all()
    assert len(relationships) == 1
    assert relationships[0].relationship_type == "member_of"

    # Verify placeholder entity source was generated
    target_source = db.query(KnowledgeSource).filter(KnowledgeSource.id == relationships[0].target_source_id).first()
    assert target_source is not None
    assert target_source.title == "Project Gemini"
    assert target_source.source_type == "project"


@pytest.mark.asyncio
@patch("app.services.knowledge_service.embedding_service.get_embedding")
async def test_index_note_artifacts(mock_get_embedding, db: Session):
    mock_get_embedding.return_value = [0.05] * 768
    user_id = "note_artifacts_user"

    # 1. Create a Note
    note = Note(title="Sprint 45 Retrospective", file_path="retro.wav", user_id=user_id)
    db.add(note)
    db.commit()
    db.refresh(note)

    # 2. Add transcript
    transcript = Transcript(note_id=note.id, text="We finished the offline synchronization sync loop.")
    # 3. Add summary
    summary = StructuredSummary(
        note_id=note.id,
        summary_type="executive",
        structured_data='{"summary": "Sprint completed successfully with sync loop."}',
        provider="openai",
        model="gpt-4",
    )
    # 4. Add meeting minutes (including all required NOT NULL string fields)
    minutes = MeetingMinutes(
        note_id=note.id,
        overview="Retro overview.",
        agenda="[]",
        discussion_points="[]",
        decisions="[]",
        risks="[]",
        action_items="[]",
        provider="openai",
        model="gpt-4",
    )

    db.add_all([transcript, summary, minutes])
    db.commit()

    # Trigger indexing of all artifacts combined
    await KnowledgeService.index_note_artifacts(db, note.id)

    # Assert source gets created
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.note_id == note.id,
        KnowledgeSource.user_id == user_id
    ).first()
    
    assert source is not None
    assert source.title == "Sprint 45 Retrospective"
    assert "Sprint completed successfully" in source.raw_content
    assert "Retro overview" in source.raw_content


# ---------------------------------------------------------------------------
# 4. Hybrid Lexical + Vector Retrieval Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.services.knowledge_retrieval.embedding_service.get_embedding")
async def test_hybrid_retrieval_and_context(mock_get_embedding, db: Session):
    user_id = "search_user"
    
    # Mock embedding matching chunk content query
    mock_get_embedding.return_value = [0.1] * 768

    # Create dummy collections and source
    col = KnowledgeCollection(name="Meetings", user_id=user_id)
    db.add(col)
    db.flush()

    source = KnowledgeSource(
        title="Weekly Sprint Retrospective",
        source_type="meeting",
        user_id=user_id,
        collection_id=col.id,
    )
    db.add(source)
    db.flush()

    chunk1 = KnowledgeChunk(source_id=source.id, chunk_index=0, content="Antigravity is a coding assistant.")
    chunk2 = KnowledgeChunk(source_id=source.id, chunk_index=1, content="We use SQLite as local fallback database.")
    db.add_all([chunk1, chunk2])
    db.flush()

    emb1 = KnowledgeEmbedding(chunk_id=chunk1.id, vector=[0.1] * 768)
    emb2 = KnowledgeEmbedding(chunk_id=chunk2.id, vector=[-0.1] * 768)
    db.add_all([emb1, emb2])
    db.commit()

    # Test Lexical search (SQLite Fallback substring match)
    lex_res = await KnowledgeRetrievalService.search_lexical(db, "SQLite", user_id)
    assert len(lex_res) == 1
    assert lex_res[0][0].id == chunk2.id

    # Test Semantic search (only chunk1 matches because similarity threshold > 0.1)
    sem_res = await KnowledgeRetrievalService.search_semantic(db, "assistant", user_id)
    assert len(sem_res) == 1
    assert sem_res[0][0].id == chunk1.id

    # Test Hybrid RRF Search
    hybrid_res = await KnowledgeRetrievalService.search_hybrid(db, "SQLite", user_id)
    assert len(hybrid_res) == 2

    # Test Build Context
    context, citations = await KnowledgeRetrievalService.build_context(db, "coding", user_id)
    assert "Weekly Sprint Retrospective" in context
    assert len(citations) == 1
    assert citations[0]["title"] == "Weekly Sprint Retrospective"


# ---------------------------------------------------------------------------
# 5. AI Chat Service Tests (Conversational & SSE Streams)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_knowledge_chat_mock_fallback(db: Session):
    # No API keys configured - verify mock response logic is triggered gracefully
    user_id = "chat_user"
    res = await KnowledgeChatService.chat(
        db=db,
        message="Hello AI",
        user_id=user_id,
        provider_name="openai",
    )
    assert "mock conversational response" in res["response"]
    assert res["citations"] == []
    assert len(res["suggested_questions"]) > 0


@pytest.mark.asyncio
@patch("app.services.knowledge_chat.get_provider")
@patch("app.services.knowledge_chat.KnowledgeRetrievalService.build_context")
async def test_knowledge_chat_success(mock_build_context, mock_get_provider, db: Session):
    user_id = "chat_user_success"
    
    # 1. Mock context and citations
    citations = [{"id": "source_1", "index": 1, "title": "Dev Guide", "source_type": "text", "note_id": None}]
    mock_build_context.return_value = ("Antigravity guide contents.", citations)

    # 2. Mock LLM Response
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = LLMResponse(
        content="Antigravity is designed to assist you [1].",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    mock_provider.close.return_value = None
    mock_get_provider.return_value = mock_provider

    # Force simulated key detection
    with patch("app.core.config.settings.OPENAI_API_KEY", "sk-dummykey"):
        res = await KnowledgeChatService.chat(
            db=db,
            message="What is Antigravity?",
            user_id=user_id,
            provider_name="openai",
        )

    assert "assist you [1]" in res["response"]
    assert res["citations"] == citations
    assert len(res["suggested_questions"]) > 0


@pytest.mark.asyncio
async def test_knowledge_chat_stream_mock(db: Session):
    user_id = "chat_stream_user"
    
    # Generate mock stream generator
    stream = KnowledgeChatService.chat_stream(
        db=db,
        message="What is the local DB?",
        user_id=user_id,
        provider_name="openai",
    )

    chunks = []
    async for chunk_str in stream:
        chunk_data = json.loads(chunk_str.strip())
        chunks.append(chunk_data)

    # The mock stream yields content and metadata
    assert len(chunks) > 0
    assert chunks[-1]["type"] == "metadata"
    assert "citations" in chunks[-1]["data"]


# ---------------------------------------------------------------------------
# 6. HTTP Router Integration Endpoint Tests
# ---------------------------------------------------------------------------

def test_collections_api(client: TestClient, db: Session):
    # 1. Register/Login user
    email = "knowledge@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. GET /collections - seeds default collections
    res = client.get("/api/v1/knowledge/collections", headers=headers)
    assert res.status_code == 200
    collections = res.json()
    assert len(collections) == len(DEFAULT_COLLECTIONS)

    # 3. POST /collections - create a new custom collection
    res = client.post(
        "/api/v1/knowledge/collections",
        json={"name": "Custom Archive", "description": "Vault for old docs"},
        headers=headers,
    )
    assert res.status_code == 200
    new_col = res.json()
    assert new_col["name"] == "Custom Archive"
    assert new_col["description"] == "Vault for old docs"

    # Attempt duplicate - should fail
    res_dup = client.post(
        "/api/v1/knowledge/collections",
        json={"name": "Custom Archive"},
        headers=headers,
    )
    assert res_dup.status_code == 400

    # 4. DELETE /collections - delete the custom collection
    res_del = client.delete(f"/api/v1/knowledge/collections/{new_col['id']}", headers=headers)
    assert res_del.status_code == 200

    # Try deleting a seeded default - should fail
    personal_col = next(c for c in collections if c["name"] == "Personal")
    res_del_default = client.delete(f"/api/v1/knowledge/collections/{personal_col['id']}", headers=headers)
    assert res_del_default.status_code == 400


@patch("app.services.knowledge_chat.get_provider")
@patch("app.services.knowledge_service.embedding_service.get_embedding")
def test_sources_and_search_api(mock_get_embedding, mock_get_provider, client: TestClient, db: Session):
    mock_get_embedding.return_value = [0.01] * 768

    # Mock LLM provider for the chat endpoint
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = LLMResponse(
        content="Antigravity is designed to assist you.",
        model="gpt-4o-mini",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    mock_provider.close.return_value = None
    mock_get_provider.return_value = mock_provider

    # 1. Auth Setup
    email = "source_api@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Seed default collections
    client.get("/api/v1/knowledge/collections", headers=headers)

    # 2. POST /sources/upload - Upload mock text file
    file_content = b"Welcome to the VoiceMind AI Assistant. It supports notes and transcripts."
    res = client.post(
        "/api/v1/knowledge/sources/upload",
        files={"file": ("guide.txt", file_content, "text/plain")},
        headers=headers,
    )
    assert res.status_code == 200
    source = res.json()
    assert source["title"] == "guide.txt"
    assert source["source_type"] == "text"

    # 3. GET /sources - retrieve indexed sources
    res_get = client.get("/api/v1/knowledge/sources", headers=headers)
    assert res_get.status_code == 200
    sources = res_get.json()
    assert len(sources) == 1
    assert sources[0]["id"] == source["id"]

    # 4. POST /search - search using hybrid engine
    res_search = client.post(
        "/api/v1/knowledge/search",
        json={"query": "VoiceMind", "limit": 5},
        headers=headers,
    )
    assert res_search.status_code == 200
    search_results = res_search.json()
    assert len(search_results) == 1
    assert search_results[0]["source_title"] == "guide.txt"
    assert "VoiceMind" in search_results[0]["content"]

    # 5. POST /chat - conversational query
    # Force simulated key detection so it hits our mocked provider
    with patch("app.core.config.settings.OPENAI_API_KEY", "sk-dummykey"):
        res_chat = client.post(
            "/api/v1/knowledge/chat",
            json={"message": "What does VoiceMind support?"},
            headers=headers,
        )
    assert res_chat.status_code == 200
    chat_resp = res_chat.json()
    assert "response" in chat_resp
    assert "citations" in chat_resp
    assert len(chat_resp["suggested_questions"]) > 0

    # 6. DELETE /sources/{source_id} - clean up source
    res_del = client.delete(f"/api/v1/knowledge/sources/{source['id']}", headers=headers)
    assert res_del.status_code == 200
