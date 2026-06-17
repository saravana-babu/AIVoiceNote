"""Note enhancement generation service.

Orchestrates AI-powered note enhancement by coordinating LLM providers and
structured prompt templates. Supports OpenAI, Anthropic, and Gemini.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

from app.services.llm_providers import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    get_provider,
)
from app.services.enhancement_prompts import (
    ENHANCEMENT_TEMPLATES,
    EnhancementType,
    render_prompt,
    EnhancementTemplate,
)
from app.services.minutes_service import extract_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EnhancementGenerationError(Exception):
    """Raised when note enhancement generation fails after exhausting retries."""

    def __init__(
        self,
        enhancement_type: str,
        provider: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        self.enhancement_type = enhancement_type
        self.provider = provider
        self.cause = cause
        super().__init__(f"[{provider}/{enhancement_type}] Note enhancement generation failed: {message}")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EnhancementResult:
    """Container for successfully generated note enhancement."""

    enhancement_type: EnhancementType
    structured_data: dict  # parsed JSON returned by the LLM
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    generation_time_ms: float


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class EnhancementService:
    """Orchestrates AI-powered note enhancement generation."""

    _MAX_RETRIES = 2

    def __init__(
        self,
        default_provider: str = "gemini",
        default_temperature: float = 0.3,
        default_max_tokens: int = 4096,
    ) -> None:
        self.default_provider = default_provider
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    async def generate_enhancement(
        self,
        text: str,
        enhancement_type: EnhancementType,
        provider_name: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> EnhancementResult:
        """Generate enhanced note content of a specific type.

        Args:
            text: Raw note or transcript text.
            enhancement_type: The enhancement style to produce.
            provider_name: Override default LLM provider.
            model: Override default model.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            An EnhancementResult containing structured data and metadata.
        """
        resolved_provider = provider_name or self.default_provider
        resolved_temperature = temperature if temperature is not None else self.default_temperature
        resolved_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        # Verify type has template
        template: EnhancementTemplate | None = ENHANCEMENT_TEMPLATES.get(enhancement_type)
        if not template:
            raise ValueError(f"Unsupported enhancement type: {enhancement_type}")

        provider: LLMProvider = get_provider(resolved_provider, model=model)

        try:
            system_prompt, user_prompt = render_prompt(template, text)
            last_error: Exception | None = None

            for attempt in range(self._MAX_RETRIES + 1):
                try:
                    start = time.monotonic()

                    response: LLMResponse = await provider.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=resolved_temperature,
                        max_tokens=resolved_max_tokens,
                    )

                    elapsed_ms = (time.monotonic() - start) * 1000
                    structured_data = extract_json(response.content)

                    # Basic schema verification
                    self._validate_schema(enhancement_type, structured_data)

                    return EnhancementResult(
                        enhancement_type=enhancement_type,
                        structured_data=structured_data,
                        provider=resolved_provider,
                        model=response.model,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                        generation_time_ms=round(elapsed_ms, 2),
                    )

                except (LLMProviderError, ValueError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt < self._MAX_RETRIES:
                        delay = 2 ** attempt
                        logger.warning(
                            "Retry %d/%d for enhancement %s (%s): %s – backing off %.1fs",
                            attempt + 1,
                            self._MAX_RETRIES,
                            enhancement_type.value,
                            resolved_provider,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "All retries exhausted for enhancement %s (%s): %s",
                            enhancement_type.value,
                            resolved_provider,
                            exc,
                        )

            raise EnhancementGenerationError(
                enhancement_type=enhancement_type.value,
                provider=resolved_provider,
                message=f"Failed after {self._MAX_RETRIES + 1} attempts",
                cause=last_error,
            )

        finally:
            await provider.close()

    def _validate_schema(self, enhancement_type: EnhancementType, data: dict) -> None:
        """Ensure the parsed JSON dict contains expected structure/keys to prevent UI crashes."""
        if enhancement_type in (EnhancementType.IMPROVED, EnhancementType.PROFESSIONAL):
            if "title" not in data or "content" not in data:
                # set defaults if missing
                data.setdefault("title", "Enhanced Note")
                data.setdefault("content", "")
        elif enhancement_type == EnhancementType.BLOG:
            data.setdefault("title", "Blog Post Draft")
            data.setdefault("sections", [])
            data.setdefault("conclusion", "")
        elif enhancement_type == EnhancementType.EXECUTIVE_REPORT:
            data.setdefault("title", "Executive Report")
            data.setdefault("executive_summary", "")
            data.setdefault("background", "")
            data.setdefault("key_findings", [])
            data.setdefault("recommendations", [])
        elif enhancement_type == EnhancementType.EMAIL:
            data.setdefault("subject", "Subject")
            data.setdefault("greeting", "Hello,")
            data.setdefault("body", "")
            data.setdefault("signature_placeholder", "Best regards,\n[Your Name]")
        elif enhancement_type == EnhancementType.PROJECT_UPDATE:
            data.setdefault("project_name", "Project Update")
            # Enforce status_color must be green, yellow, or red
            color = data.get("status_color")
            if color not in ("green", "yellow", "red"):
                data["status_color"] = "green"
            data.setdefault("milestones_completed", [])
            data.setdefault("current_blockers", [])
            data.setdefault("next_steps", [])
