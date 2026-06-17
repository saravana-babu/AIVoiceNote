import pytest
import json
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.models import User, Note, Transcript, StructuredSummary, Tag, NoteEmbedding
from app.services.embedding_service import embedding_service
from app.services.search_service import SearchService

def test_mock_embedding():
    text = "Hello world"
    vec1 = embedding_service.generate_mock_embedding(text)
    vec2 = embedding_service.generate_mock_embedding(text)
    vec3 = embedding_service.generate_mock_embedding("Different text")
    
    assert len(vec1) == 768
    assert vec1 == vec2
    assert vec1 != vec3
    norm = sum(x*x for x in vec1) ** 0.5
    assert abs(norm - 1.0) < 1e-5

@pytest.mark.asyncio
async def test_search_service_and_api(client: TestClient, db: Session):
    # 1. Register and login to get headers
    email = "search@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user ID from database
    user = db.query(User).filter(User.email == email).first()
    assert user is not None

    # 2. Create notes
    note1 = Note(title="Project Launch Meeting Notes", file_path="path1.wav", user_id=user.id)
    note2 = Note(title="Weekly Sprint Update", file_path="path2.wav", user_id=user.id)
    db.add_all([note1, note2])
    db.commit()
    db.refresh(note1)
    db.refresh(note2)

    # Add tags
    tag1 = Tag(note_id=note1.id, tag="launch")
    tag2 = Tag(note_id=note1.id, tag="planning")
    tag3 = Tag(note_id=note2.id, tag="agile")
    db.add_all([tag1, tag2, tag3])
    db.commit()

    # Add transcripts
    tr1 = Transcript(note_id=note1.id, text="We are launching the antigravity AI assistant tomorrow. It will revolutionize pair programming.")
    tr2 = Transcript(note_id=note2.id, text="Every monday we update our team on the current sprint progress.")
    db.add_all([tr1, tr2])
    db.commit()

    # Add structured summaries
    sum1 = StructuredSummary(
        note_id=note1.id,
        summary_type="executive",
        structured_data='{"executive_summary": "Antigravity launch scheduled for tomorrow."}',
        provider="openai",
        model="gpt-4"
    )
    sum2 = StructuredSummary(
        note_id=note2.id,
        summary_type="executive",
        structured_data='{"executive_summary": "Routine weekly team synchronization."}',
        provider="openai",
        model="gpt-4"
    )
    db.add_all([sum1, sum2])
    db.commit()

    # Update embeddings manually for test
    await SearchService.update_note_embedding(db, note1.id)
    await SearchService.update_note_embedding(db, note2.id)
    await SearchService.update_transcript_embedding(db, note1.id)
    await SearchService.update_transcript_embedding(db, note2.id)
    await SearchService.update_summary_embedding(db, note1.id)
    await SearchService.update_summary_embedding(db, note2.id)

    # Assert NoteEmbedding records exist
    emb1 = db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note1.id).first()
    emb2 = db.query(NoteEmbedding).filter(NoteEmbedding.note_id == note2.id).first()
    assert emb1 is not None
    assert emb2 is not None
    assert emb1.note_vector is not None
    assert emb1.transcript_vector is not None
    assert emb1.summary_vector is not None

    # Test FTS / Lexical search service
    lex_res = await SearchService.search_lexical(db, "antigravity", user.id)
    assert len(lex_res) == 1
    assert lex_res[0][0].id == note1.id

    # Test Semantic search service
    sem_res = await SearchService.search_semantic(db, "AI assistant tomorrow", user.id)
    assert len(sem_res) > 0
    assert sem_res[0][0].id == note1.id

    # Test Hybrid search service
    hybrid_res = await SearchService.search_hybrid(db, "launch", user.id)
    assert len(hybrid_res) > 0
    assert hybrid_res[0][0].id == note1.id

    # 3. Test HTTP Endpoints
    # Lexical Search API
    res = client.get("/api/v1/search/?q=antigravity&type=fts", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["note"]["id"] == note1.id
    assert data[0]["match_type"] == "fts"

    # Semantic Search API
    res = client.get("/api/v1/search/?q=sprint progress&type=semantic", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0
    assert data[0]["note"]["id"] == note2.id
    assert data[0]["match_type"] == "semantic"

    # Hybrid Search API
    res = client.get("/api/v1/search/?q=planning launch&type=hybrid", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) > 0
    assert data[0]["note"]["id"] == note1.id
    assert data[0]["match_type"] == "hybrid"
