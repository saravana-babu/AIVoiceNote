"""Meeting minutes generation service.

Orchestrates AI-powered meeting minutes generation by coordinating
LLM providers and structured prompt templates. Includes transient error retries.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

from app.services.llm_providers import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    get_provider,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MinutesGenerationError(Exception):
    """Raised when meeting minutes generation fails after exhausting retries."""

    def __init__(
        self,
        provider: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        self.provider = provider
        self.cause = cause
        super().__init__(f"[{provider}] Meeting Minutes generation failed: {message}")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MinutesResult:
    """Container for successfully generated meeting minutes."""

    structured_data: dict  # parsed JSON returned by the LLM
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    generation_time_ms: float


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an expert meeting assistant specialising in producing clear, professional meeting minutes.\n"
    "Your task is to compile a detailed, well-structured record of the meeting based on the provided transcript.\n"
    "The output must be formatted as a valid JSON object conforming exactly to the schema.\n\n"
    "Rules:\n"
    "1. Output ONLY valid JSON. Do NOT wrap the JSON in markdown code fences, backticks, or any other formatting.\n"
    "2. The 'overview' must capture the general purpose, attendees (if mentioned), and general mood of the meeting.\n"
    "3. The 'agenda' must list scheduled topics.\n"
    "4. The 'discussion_points' must list primary topics discussed, with a summary of views or consensus reached.\n"
    "5. The 'decisions' must capture any concrete approvals, conclusions, or choices.\n"
    "6. The 'risks' must list potential issues, obstacles, or concerns that need monitoring.\n"
    "7. The 'action_items' must list concrete tasks with task description, owner (person/team), and due date (YYYY-MM-DD or relative/TBD)."
)

USER_PROMPT_TEMPLATE = (
    "Given the following transcript, generate the meeting minutes conforming to the schema.\n\n"
    "Transcript:\n{transcript}\n\n"
    "Output the result as JSON with this schema:\n"
    "{{\n"
    "  \"overview\": \"string - overall meeting summary\",\n"
    "  \"agenda\": [\"string - scheduled agenda item\"],\n"
    "  \"discussion_points\": [\n"
    "    {{\n"
    "      \"topic\": \"string - discussion topic\",\n"
    "      \"summary\": \"string - summary of what was discussed\"\n"
    "    }}\n"
    "  ],\n"
    "  \"decisions\": [\"string - decision made\"],\n"
    "  \"risks\": [\"string - risk, issue, or concern raised\"],\n"
    "  \"action_items\": [\n"
    "    {{\n"
    "      \"task\": \"string - action item description\",\n"
    "      \"owner\": \"string - owner name or role\",\n"
    "      \"due_date\": \"string - due date (YYYY-MM-DD or relative/TBD)\"\n"
    "    }}\n"
    "  ]\n"
    "}}"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def extract_json(text: str) -> dict:
    """Extract a JSON object from text, tolerating LLM markdown fences."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    match = _CODE_FENCE_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError("No valid JSON object could be extracted from response")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class MinutesService:
    """Orchestrates AI-powered meeting minutes generation."""

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

    async def generate_minutes(
        self,
        transcript_text: str,
        provider_name: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> MinutesResult:
        """Generate meeting minutes from a transcript.

        Args:
            transcript_text: Raw text of the transcript.
            provider_name: Override default LLM provider.
            model: Override default model.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            A MinutesResult containing structured data and metadata.
        """
        resolved_provider = provider_name or self.default_provider
        resolved_temperature = temperature if temperature is not None else self.default_temperature
        resolved_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        provider: LLMProvider = get_provider(resolved_provider, model=model)

        try:
            user_prompt = USER_PROMPT_TEMPLATE.format(transcript=transcript_text)
            last_error: Exception | None = None

            for attempt in range(self._MAX_RETRIES + 1):
                try:
                    start = time.monotonic()

                    response: LLMResponse = await provider.generate(
                        prompt=user_prompt,
                        system_prompt=SYSTEM_PROMPT,
                        temperature=resolved_temperature,
                        max_tokens=resolved_max_tokens,
                    )

                    elapsed_ms = (time.monotonic() - start) * 1000
                    structured_data = extract_json(response.content)

                    # Validate basic keys
                    required_keys = ["overview", "agenda", "discussion_points", "decisions", "risks", "action_items"]
                    for key in required_keys:
                        if key not in structured_data:
                            structured_data[key] = [] if key != "overview" else ""

                    return MinutesResult(
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
                            "Retry %d/%d for meeting minutes (%s): %s – backing off %.1fs",
                            attempt + 1,
                            self._MAX_RETRIES,
                            resolved_provider,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "All retries exhausted for meeting minutes (%s): %s",
                            resolved_provider,
                            exc,
                        )

            raise MinutesGenerationError(
                provider=resolved_provider,
                message=f"Failed after {self._MAX_RETRIES + 1} attempts",
                cause=last_error,
            )

        finally:
            await provider.close()
