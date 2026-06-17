"""Tests for the Meeting Minutes Generation System.

Tests cover:
- JSON extraction
- MinutesService generation with mocked provider (success, retries, and errors)
- Meeting Minutes API endpoints integration
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.models.models import Note, Transcript, MeetingMinutes
from app.services.minutes_service import MinutesService, MinutesGenerationError, extract_json
from app.services.llm_providers import LLMResponse, LLMProviderError


# ---------------------------------------------------------------------------
# JSON Extraction Tests
# ---------------------------------------------------------------------------

class TestJsonExtraction:
    def test_clean_json(self):
        text = '{"overview": "Test overview", "agenda": ["Point 1"]}'
        result = extract_json(text)
        assert result["overview"] == "Test overview"
        assert result["agenda"] == ["Point 1"]

    def test_json_with_code_fences(self):
        text = '```json\n{"overview": "Fenced", "agenda": []}\n```'
        result = extract_json(text)
        assert result["overview"] == "Fenced"
        assert result["agenda"] == []

    def test_json_with_surrounding_text(self):
        text = 'Prose before\n{"overview": "Embedded", "agenda": ["Item 1"]}\nProse after'
        result = extract_json(text)
        assert result["overview"] == "Embedded"
        assert result["agenda"] == ["Item 1"]

    def test_invalid_json_raises_error(self):
        with pytest.raises(ValueError):
            extract_json("not json")


# ---------------------------------------------------------------------------
# Service Generation Tests
# ---------------------------------------------------------------------------

class TestMinutesService:
    @pytest.fixture
    def mock_llm_response(self):
        content = {
            "overview": "Summary of the team milestone review.",
            "agenda": ["Milestone check", "Next steps"],
            "discussion_points": [
                {"topic": "Milestone check", "summary": "All features are built on time."}
            ],
            "decisions": ["Deploy next Tuesday"],
            "risks": ["Potential Apple Store delays"],
            "action_items": [
                {"task": "Prepare release notes", "owner": "John", "due_date": "2026-06-20"}
            ]
        }
        return LLMResponse(
            content=json.dumps(content),
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=300,
            completion_tokens=150,
            total_tokens=450,
        )

    @pytest.fixture
    def service(self):
        return MinutesService(default_provider="openai")

    @pytest.mark.asyncio
    async def test_generate_minutes_success(self, service, mock_llm_response):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_llm_response)
        mock_provider.close = AsyncMock()

        with patch("app.services.minutes_service.get_provider", return_value=mock_provider):
            result = await service.generate_minutes(
                transcript_text="Test transcript text for milestones."
            )

        assert result.structured_data["overview"] == "Summary of the team milestone review."
        assert result.provider == "openai"
        assert result.prompt_tokens == 300
        assert result.generation_time_ms >= 0
        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_minutes_retries(self, service, mock_llm_response):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=[
                LLMProviderError("openai", 503, "Service Unavailable"),
                mock_llm_response,
            ]
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.minutes_service.get_provider", return_value=mock_provider):
            result = await service.generate_minutes(
                transcript_text="Test transcript text."
            )

        assert result.structured_data["overview"] == "Summary of the team milestone review."
        assert mock_provider.generate.call_count == 2
        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_minutes_exhausts_retries(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=LLMProviderError("openai", 500, "Internal Server Error")
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.minutes_service.get_provider", return_value=mock_provider):
            with pytest.raises(MinutesGenerationError):
                await service.generate_minutes(transcript_text="Test transcript.")

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
        email="testuser@example.com",
        hashed_password=get_password_hash("password123"),
        display_name="Test User",
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
        title="Test Note",
        duration_sec=60,
        file_path="file:///test.m4a",
        status="completed",
        user_id=test_user.id
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

class TestMinutesAPI:
    def test_generate_endpoint_success(self, client: TestClient, db, test_user, test_note):
        # 1. Create transcript for note
        transcript = Transcript(note_id=test_note.id, text="Let us build the minutes tool today.")
        db.add(transcript)
        db.commit()

        # 2. Setup mock LLM response
        content = {
            "overview": "Team aligned on building the minutes tool.",
            "agenda": ["Design", "Implementation"],
            "discussion_points": [
                {"topic": "Implementation", "summary": "We will create routes and schemas."}
            ],
            "decisions": ["Proceed today"],
            "risks": ["No significant risks"],
            "action_items": [
                {"task": "Build endpoints", "owner": "Dev", "due_date": "2026-06-18"}
            ]
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

        with patch("app.services.minutes_service.get_provider", return_value=mock_provider):
            res = client.post(
                "/api/v1/meeting-minutes/generate",
                json={"note_id": test_note.id},
                headers=headers,
            )

        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["minutes"]["overview"] == "Team aligned on building the minutes tool."
        assert data["minutes"]["decisions"] == ["Proceed today"]
        assert len(data["minutes"]["action_items"]) == 1
        assert data["minutes"]["action_items"][0]["owner"] == "Dev"

        # Check DB state
        db_minutes = db.query(MeetingMinutes).filter(MeetingMinutes.note_id == test_note.id).first()
        assert db_minutes is not None
        assert db_minutes.overview == "Team aligned on building the minutes tool."

    def test_get_endpoint_not_found(self, client: TestClient, db, test_user, test_note):
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = client.get(
            f"/api/v1/meeting-minutes/note/{test_note.id}",
            headers=headers,
        )
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert "No meeting minutes found" in res.json()["detail"]

    def test_delete_endpoint_success(self, client: TestClient, db, test_user, test_note):
        # Insert mock minutes
        minutes = MeetingMinutes(
            note_id=test_note.id,
            overview="Mock overview",
            agenda="[]",
            discussion_points="[]",
            decisions="[]",
            risks="[]",
            action_items="[]",
            provider="openai",
            model="gpt-4o-mini",
        )
        db.add(minutes)
        db.commit()

        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "password123"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = client.delete(
            f"/api/v1/meeting-minutes/note/{test_note.id}",
            headers=headers,
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["status"] == "success"

        # Verify deleted
        db_minutes = db.query(MeetingMinutes).filter(MeetingMinutes.note_id == test_note.id).first()
        assert db_minutes is None
