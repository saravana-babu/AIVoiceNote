"""Comprehensive tests for the AI Summary Generation System.

Tests cover:
- Prompt template rendering and validation
- JSON extraction from various LLM response formats
- LLM provider factory and error handling
- Summary service generation with mocked providers
- API endpoint integration tests with mocked LLM calls
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.prompt_templates import (
    SummaryType,
    PromptTemplate,
    SUMMARY_TEMPLATES,
    render_prompt,
)
from app.services.summary_service import (
    SummaryService,
    SummaryGenerationError,
    SummaryResult,
    _extract_json,
)
from app.services.llm_providers import (
    LLMResponse,
    LLMProviderError,
    GeminiProvider,
    get_provider,
)


# ---------------------------------------------------------------------------
# Prompt Template Tests
# ---------------------------------------------------------------------------


class TestPromptTemplates:
    """Tests for prompt template definitions and rendering."""

    def test_all_summary_types_have_templates(self):
        """Every SummaryType must have a corresponding template."""
        for st in SummaryType:
            assert st in SUMMARY_TEMPLATES, f"Missing template for {st.value}"

    def test_template_structure(self):
        """Each template must have all required fields populated."""
        for st, tmpl in SUMMARY_TEMPLATES.items():
            assert isinstance(tmpl, PromptTemplate)
            assert tmpl.summary_type == st
            assert len(tmpl.system_prompt) > 50, f"System prompt too short for {st.value}"
            assert "{transcript}" in tmpl.user_prompt_template, f"Missing {{transcript}} placeholder in {st.value}"
            assert isinstance(tmpl.json_schema, dict)
            assert "type" in tmpl.json_schema
            assert "properties" in tmpl.json_schema or "items" in tmpl.json_schema.get("properties", {})

    def test_render_prompt_returns_tuple(self):
        """render_prompt must return a (system_prompt, user_prompt) tuple."""
        transcript = "This is a test transcript about project updates."
        system_prompt, user_prompt = render_prompt(SummaryType.EXECUTIVE, transcript)
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        assert len(system_prompt) > 0
        assert transcript in user_prompt

    def test_render_prompt_all_types(self):
        """render_prompt must work for every summary type."""
        transcript = "Meeting notes about quarterly review."
        for st in SummaryType:
            system_prompt, user_prompt = render_prompt(st, transcript)
            assert transcript in user_prompt
            assert "JSON" in system_prompt  # All prompts mention JSON

    def test_render_prompt_invalid_type(self):
        """render_prompt must raise KeyError for invalid summary types."""
        with pytest.raises(KeyError):
            render_prompt("invalid_type", "transcript")

    def test_json_schema_has_required_fields(self):
        """Each template's json_schema must define required fields."""
        for st, tmpl in SUMMARY_TEMPLATES.items():
            assert "required" in tmpl.json_schema, f"Missing 'required' in schema for {st.value}"

    def test_executive_schema_structure(self):
        """Executive schema must include title, summary, key_points, sentiment."""
        schema = SUMMARY_TEMPLATES[SummaryType.EXECUTIVE].json_schema
        props = schema["properties"]
        assert "title" in props
        assert "summary" in props
        assert "key_points" in props
        assert "sentiment" in props

    def test_action_items_schema_structure(self):
        """Action items schema must include items with action, priority fields."""
        schema = SUMMARY_TEMPLATES[SummaryType.ACTION_ITEMS].json_schema
        item_props = schema["properties"]["items"]["items"]["properties"]
        assert "action" in item_props
        assert "priority" in item_props
        assert "assignee" in item_props


# ---------------------------------------------------------------------------
# JSON Extraction Tests
# ---------------------------------------------------------------------------


class TestJsonExtraction:
    """Tests for the _extract_json helper function."""

    def test_clean_json(self):
        """Directly valid JSON should parse without issues."""
        text = '{"title": "Test", "summary": "A test summary"}'
        result = _extract_json(text)
        assert result["title"] == "Test"
        assert result["summary"] == "A test summary"

    def test_json_with_code_fences(self):
        """JSON wrapped in markdown code fences should be extracted."""
        text = '```json\n{"title": "Fenced", "items": [1, 2, 3]}\n```'
        result = _extract_json(text)
        assert result["title"] == "Fenced"
        assert result["items"] == [1, 2, 3]

    def test_json_with_plain_fences(self):
        """JSON wrapped in plain (no language) code fences should be extracted."""
        text = '```\n{"key": "value"}\n```'
        result = _extract_json(text)
        assert result["key"] == "value"

    def test_json_with_surrounding_text(self):
        """JSON embedded in surrounding prose should be extracted via brace matching."""
        text = 'Here is the result:\n{"title": "Embedded", "count": 42}\nHope this helps!'
        result = _extract_json(text)
        assert result["title"] == "Embedded"
        assert result["count"] == 42

    def test_invalid_json_raises_error(self):
        """Completely invalid content should raise SummaryGenerationError."""
        with pytest.raises(SummaryGenerationError):
            _extract_json("This is not JSON at all")

    def test_empty_string_raises_error(self):
        """Empty string should raise SummaryGenerationError."""
        with pytest.raises(SummaryGenerationError):
            _extract_json("")

    def test_nested_json(self):
        """Deeply nested JSON should parse correctly."""
        data = {
            "sections": [
                {"heading": "Intro", "content": "Introduction text"},
                {"heading": "Body", "content": "Main content"},
            ],
            "metadata": {"count": 2},
        }
        text = json.dumps(data)
        result = _extract_json(text)
        assert len(result["sections"]) == 2
        assert result["metadata"]["count"] == 2


# ---------------------------------------------------------------------------
# LLM Provider Tests
# ---------------------------------------------------------------------------


class TestLLMProviderFactory:
    """Tests for the get_provider factory function."""

    def test_unknown_provider_raises_value_error(self):
        """Requesting an unknown provider must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider("nonexistent_provider")

    def test_missing_api_key_raises_value_error(self):
        """Missing API key for a valid provider must raise ValueError."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="Missing required environment variable"):
                get_provider("gemini")

    def test_gemini_provider_creation(self):
        """Gemini provider should be created with the correct API key."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "goog-test-key"}):
            provider = get_provider("gemini")
            assert isinstance(provider, GeminiProvider)
            assert provider.provider_name == "gemini"

    def test_case_insensitive_provider_name(self):
        """Provider names should be case-insensitive."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "goog-test-key"}):
            provider = get_provider("Gemini")
            assert isinstance(provider, GeminiProvider)

    def test_model_override(self):
        """Custom model should be passed to the provider."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "goog-test-key"}):
            provider = get_provider("gemini", model="gemini-1.5-pro")
            assert provider._model == "gemini-1.5-pro"


# ---------------------------------------------------------------------------
# Summary Service Tests
# ---------------------------------------------------------------------------


class TestSummaryService:
    """Tests for the SummaryService orchestration layer."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response with valid JSON content."""
        return LLMResponse(
            content=json.dumps({
                "title": "Test Meeting Summary",
                "summary": "This was a productive meeting about project milestones.",
                "key_points": ["Milestone 1 completed", "Budget approved"],
                "sentiment": "positive",
            }),
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
        )

    @pytest.fixture
    def service(self):
        """Create a SummaryService with defaults."""
        return SummaryService(
            default_provider="openai",
            default_temperature=0.3,
            default_max_tokens=4096,
        )

    @pytest.mark.asyncio
    async def test_generate_summary_success(self, service, mock_llm_response):
        """Successful single summary generation."""
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_llm_response)
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            result = await service.generate_summary(
                transcript_text="This is a test transcript.",
                summary_type=SummaryType.EXECUTIVE,
            )

        assert isinstance(result, SummaryResult)
        assert result.summary_type == SummaryType.EXECUTIVE
        assert result.structured_data["title"] == "Test Meeting Summary"
        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.prompt_tokens == 500
        assert result.completion_tokens == 200
        assert result.generation_time_ms >= 0
        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_summary_retries_on_provider_error(self, service):
        """Service should retry on LLMProviderError."""
        mock_provider = AsyncMock()
        good_response = LLMResponse(
            content='{"title":"Retry Success","summary":"Worked after retry","key_points":[],"sentiment":"neutral"}',
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        mock_provider.generate = AsyncMock(
            side_effect=[
                LLMProviderError("openai", 429, "Rate limited"),
                good_response,
            ]
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            result = await service.generate_summary(
                transcript_text="Test transcript",
                summary_type=SummaryType.EXECUTIVE,
            )

        assert result.structured_data["title"] == "Retry Success"
        assert mock_provider.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_summary_exhausts_retries(self, service):
        """Service should raise SummaryGenerationError after all retries."""
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=LLMProviderError("openai", 500, "Internal server error")
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            with pytest.raises(SummaryGenerationError):
                await service.generate_summary(
                    transcript_text="Test transcript",
                    summary_type=SummaryType.EXECUTIVE,
                )

        # Should have been called 3 times (1 initial + 2 retries)
        assert mock_provider.generate.call_count == 3
        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_summary_handles_code_fenced_json(self, service):
        """Service should handle JSON wrapped in markdown code fences."""
        fenced_response = LLMResponse(
            content='```json\n{"title":"Fenced","summary":"Works","key_points":["a"],"sentiment":"neutral"}\n```',
            model="gpt-4o-mini",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=fenced_response)
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            result = await service.generate_summary(
                transcript_text="Test transcript",
                summary_type=SummaryType.EXECUTIVE,
            )

        assert result.structured_data["title"] == "Fenced"

    @pytest.mark.asyncio
    async def test_generate_all_summaries(self, service, mock_llm_response):
        """Batch generation should produce results for all summary types."""
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_llm_response)
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            results = await service.generate_all_summaries(
                transcript_text="Test transcript for batch generation.",
            )

        assert len(results) == 5
        types_generated = {r.summary_type for r in results}
        assert types_generated == set(SummaryType)

    @pytest.mark.asyncio
    async def test_generate_all_summaries_partial_failure(self, service):
        """Batch generation should return successful results even if some fail."""
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise LLMProviderError("openai", 500, "Error")
            return LLMResponse(
                content='{"title":"OK","summary":"S","key_points":[],"sentiment":"neutral"}',
                model="gpt-4o-mini",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            )

        mock_provider = AsyncMock()
        mock_provider.generate = mock_generate
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            results = await service.generate_all_summaries(
                transcript_text="Test transcript",
            )

        # Some should succeed, some should fail
        assert len(results) > 0
        assert len(results) < 5

    @pytest.mark.asyncio
    async def test_generate_summary_provider_always_closed(self, service):
        """Provider.close() must always be called, even on error."""
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=LLMProviderError("openai", 500, "Error")
        )
        mock_provider.close = AsyncMock()

        with patch("app.services.summary_service.get_provider", return_value=mock_provider):
            with pytest.raises(SummaryGenerationError):
                await service.generate_summary(
                    transcript_text="Test",
                    summary_type=SummaryType.EXECUTIVE,
                )

        mock_provider.close.assert_called_once()


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------


class TestSummaryEndpoints:
    """Integration tests for summary API endpoints."""

    def _setup_user_and_note(self, client, db):
        """Helper to create a user, note, and transcript for testing."""
        email = "summary_test@example.com"
        password = "testpass123"
        client.post("/api/v1/auth/register", json={"email": email, "password": password})
        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create note
        note_res = client.post("/api/v1/notes/", json={
            "title": "Test Note",
            "duration_sec": 300,
            "file_path": "/test/audio.m4a",
        }, headers=headers)
        note_id = note_res.json()["id"]

        # Create transcript
        client.post("/api/v1/transcripts/", json={
            "note_id": note_id,
            "text": "This is a test meeting transcript about project deadlines and team updates.",
            "confidence": 0.95,
        }, headers=headers)

        return headers, note_id

    def test_get_summaries_empty(self, client, db):
        """GET /summaries/{note_id} should return empty list for note with no summaries."""
        headers, note_id = self._setup_user_and_note(client, db)
        res = client.get(f"/api/v1/summaries/{note_id}", headers=headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_get_summaries_not_found_note(self, client, db):
        """GET /summaries/{note_id} should return 404 for non-existent note."""
        email = "summary_notfound@example.com"
        client.post("/api/v1/auth/register", json={"email": email, "password": "testpass"})
        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = client.get("/api/v1/summaries/nonexistent-id", headers=headers)
        assert res.status_code == 404

    def test_get_summary_by_type_not_found(self, client, db):
        """GET /summaries/{note_id}/{type} should return 404 when no summary of that type exists."""
        headers, note_id = self._setup_user_and_note(client, db)
        res = client.get(f"/api/v1/summaries/{note_id}/executive", headers=headers)
        assert res.status_code == 404

    def test_get_summary_invalid_type(self, client, db):
        """GET /summaries/{note_id}/{type} should return 400 for invalid summary type."""
        headers, note_id = self._setup_user_and_note(client, db)
        res = client.get(f"/api/v1/summaries/{note_id}/invalid_type", headers=headers)
        assert res.status_code == 400

    def test_generate_summary_no_transcript(self, client, db):
        """POST /summaries/generate should return 400 if note has no transcript."""
        email = "summary_notrans@example.com"
        client.post("/api/v1/auth/register", json={"email": email, "password": "testpass"})
        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create note without transcript
        note_res = client.post("/api/v1/notes/", json={
            "title": "No Transcript Note",
            "duration_sec": 60,
            "file_path": "/test/notrans.m4a",
        }, headers=headers)
        note_id = note_res.json()["id"]

        res = client.post("/api/v1/summaries/generate", json={
            "note_id": note_id,
            "summary_type": "executive",
        }, headers=headers)
        assert res.status_code == 400

    def test_delete_summaries_empty(self, client, db):
        """DELETE /summaries/{note_id} should return 204 even with no summaries."""
        headers, note_id = self._setup_user_and_note(client, db)
        res = client.delete(f"/api/v1/summaries/{note_id}", headers=headers)
        assert res.status_code == 204

    def test_delete_summary_by_type_not_found(self, client, db):
        """DELETE /summaries/{note_id}/{type} should return 404 when no summary exists."""
        headers, note_id = self._setup_user_and_note(client, db)
        res = client.delete(f"/api/v1/summaries/{note_id}/executive", headers=headers)
        assert res.status_code == 404
