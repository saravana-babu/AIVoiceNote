"""Tests for the Note Enhancement Generation System.

Tests cover:
- EnhancementService generation with mocked provider (success, retries, and errors)
- Note Enhancement API endpoints integration (generate, get all, delete)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.models import Note, Transcript, NoteEnhancement
from app.services.enhancement_service import EnhancementService, EnhancementGenerationError
from app.services.enhancement_prompts import EnhancementType
from app.services.llm_providers import LLMResponse, LLMProviderError


# ---------------------------------------------------------------------------
# Service Generation Tests
# ---------------------------------------------------------------------------

class TestEnhancementService:
    @pytest.fixture
    def mock_llm_response(self):
        content = {
            "title": "Improved Coding Notes",
            "content": "# Clean Code\nWrite expressive code and keep it simple."
        }
        return LLMResponse(
            content=json.dumps(content),
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=250,
            completion_tokens=120,
            total_tokens=370,
        )

    @pytest.fixture
    def service(self):
        return EnhancementService(default_provider="openai")

    @pytest.mark.asyncio
    async def test_generate_enhancement_success(self, service, mock_llm_response):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_llm_response)
        mock_provider.close = AsyncMock()

        with patch("app.services.enhancement_service.get_provider", return_value=mock_provider):
            result = await service.generate_enhancement(
                text="Write clean code. Keep things simple.",
                enhancement_type=EnhancementType.IMPROVED
            )

        assert result.structured_data["title"] == "Improved Coding Notes"
        assert result.structured_data["content"] == "# Clean Code\nWrite expressive code and keep it simple."
        assert result.provider == "openai"
        assert result.prompt_tokens == 250
        assert result.generation_time_ms >= 0
        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_enhancement_retries(self, service, mock_llm_response):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=[
                LLMProviderError("openai", 503, "Service Unavailable"),
                mock_llm_response,
            ]
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.enhancement_service.get_provider", return_value=mock_provider):
            result = await service.generate_enhancement(
                text="Write clean code.",
                enhancement_type=EnhancementType.IMPROVED
            )

        assert result.structured_data["title"] == "Improved Coding Notes"
        assert mock_provider.generate.call_count == 2
        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_enhancement_exhausts_retries(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=LLMProviderError("openai", 500, "Internal Server Error")
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.enhancement_service.get_provider", return_value=mock_provider):
            with pytest.raises(EnhancementGenerationError):
                await service.generate_enhancement(
                    text="Write clean code.",
                    enhancement_type=EnhancementType.IMPROVED
                )

        assert mock_provider.generate.call_count == 3
        mock_provider.close.assert_called_once()


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def test_user(db):
    from app.core.security import get_password_hash
    from app.models.models import User
    user = User(
        email="enhancementuser@example.com",
        hashed_password=get_password_hash("password123"),
        display_name="Enhancement User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def test_note(db, test_user):
    from app.models.models import Note
    note = Note(
        title="Enhanceable Note",
        duration_sec=60,
        file_path="file:///test-enh.m4a",
        status="completed",
        user_id=test_user.id
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

class TestEnhancementAPI:
    def test_generate_endpoint_success(self, client: TestClient, db, test_user, test_note):
        # 1. Create transcript for note
        transcript = Transcript(note_id=test_note.id, text="Let us build code templates.")
        db.add(transcript)
        db.commit()

        # 2. Setup mock LLM response
        content = {
            "title": "Professional Version",
            "content": "Let us proceed to build code templates today."
        }
        mock_response = LLMResponse(
            content=json.dumps(content),
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        )

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_response)
        mock_provider.close = AsyncMock()

        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.services.enhancement_service.get_provider", return_value=mock_provider):
            res = client.post(
                "/api/v1/enhancements/generate",
                json={"note_id": test_note.id, "enhancement_type": "professional"},
                headers=headers,
            )

        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["enhancement"]["enhancement_type"] == "professional"
        assert data["enhancement"]["structured_data"]["title"] == "Professional Version"

        # Check DB state
        db_enh = db.query(NoteEnhancement).filter(
            NoteEnhancement.note_id == test_note.id,
            NoteEnhancement.enhancement_type == "professional"
        ).first()
        assert db_enh is not None
        assert json.loads(db_enh.structured_data)["title"] == "Professional Version"

    def test_get_endpoint_empty(self, client: TestClient, db, test_user, test_note):
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = client.get(
            f"/api/v1/enhancements/note/{test_note.id}",
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == []

    def test_delete_endpoint_success(self, client: TestClient, db, test_user, test_note):
        # Insert mock enhancement
        enh = NoteEnhancement(
            note_id=test_note.id,
            enhancement_type="blog",
            structured_data=json.dumps({"title": "A Blog Post", "sections": [], "conclusion": ""}),
            provider="openai",
            model="gpt-4o-mini",
        )
        db.add(enh)
        db.commit()

        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = client.delete(
            f"/api/v1/enhancements/{enh.id}",
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["status"] == "success"

        # Verify deleted
        db_enh = db.query(NoteEnhancement).filter(NoteEnhancement.id == enh.id).first()
        assert db_enh is None
