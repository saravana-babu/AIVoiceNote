"""Summary generation service.

Orchestrates AI-powered transcript summarisation by coordinating
LLM providers and prompt templates.  Supports single and concurrent
batch generation with automatic retries and robust JSON extraction.
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
from app.services.prompt_templates import (
    SUMMARY_TEMPLATES,
    SummaryType,
    render_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SummaryGenerationError(Exception):
    """Raised when summary generation fails after exhausting retries."""

    def __init__(
        self,
        summary_type: str,
        provider: str,
        message: str,
        cause: Exception | None = None,
    ) -> None:
        self.summary_type = summary_type
        self.provider = provider
        self.cause = cause
        super().__init__(
            f"[{provider}/{summary_type}] {message}"
        )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SummaryResult:
    """Container for a successfully generated summary."""

    summary_type: SummaryType
    structured_data: dict  # parsed JSON returned by the LLM
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    generation_time_ms: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from *text*, tolerating common LLM quirks.

    Attempts three strategies in order:
    1. Parse the full text as JSON directly.
    2. Extract content from markdown code fences and parse.
    3. Locate the first ``{`` and last ``}`` and parse the substring.

    Raises:
        SummaryGenerationError: If no valid JSON object can be extracted.
    """
    # Strategy 1 – raw text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2 – markdown code fence
    match = _CODE_FENCE_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3 – first `{` … last `}`
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(text[first : last + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    raise SummaryGenerationError(
        summary_type="unknown",
        provider="unknown",
        message=f"Failed to extract valid JSON from LLM response: {text[:200]!r}",
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SummaryService:
    """High-level service for generating transcript summaries.

    Parameters:
        default_provider:   Name of the LLM provider to use when none is
                            specified per-call (e.g. ``"openai"``).
        default_temperature: Sampling temperature for generation.
        default_max_tokens:  Maximum number of tokens for the completion.
    """

    _MAX_RETRIES: int = 2

    def __init__(
        self,
        default_provider: str = "gemini",
        default_temperature: float = 0.3,
        default_max_tokens: int = 4096,
    ) -> None:
        self.default_provider = default_provider
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

    # ------------------------------------------------------------------
    # Single summary
    # ------------------------------------------------------------------

    async def generate_summary(
        self,
        transcript_text: str,
        summary_type: SummaryType,
        provider_name: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SummaryResult:
        """Generate a single summary for *transcript_text*.

        The call includes retry logic: up to ``_MAX_RETRIES`` additional
        attempts are made on recoverable errors (``LLMProviderError``,
        ``json.JSONDecodeError``), with exponential back-off between
        attempts.

        Args:
            transcript_text: Raw transcript to summarise.
            summary_type:    The kind of summary to produce.
            provider_name:   LLM provider override (defaults to instance default).
            model:           Model override (provider chooses its own default
                             when ``None``).
            temperature:     Sampling temperature override.
            max_tokens:      Max completion tokens override.

        Returns:
            A ``SummaryResult`` containing the parsed structured data and
            associated metadata.

        Raises:
            SummaryGenerationError: If generation fails after all retries.
        """
        resolved_provider = provider_name or self.default_provider
        resolved_temperature = temperature if temperature is not None else self.default_temperature
        resolved_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        provider: LLMProvider = get_provider(resolved_provider, model=model)

        try:
            system_prompt, user_prompt = render_prompt(summary_type, transcript_text)

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

                    structured_data = _extract_json(response.content)

                    return SummaryResult(
                        summary_type=summary_type,
                        structured_data=structured_data,
                        provider=resolved_provider,
                        model=response.model,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                        generation_time_ms=round(elapsed_ms, 2),
                    )

                except (LLMProviderError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt < self._MAX_RETRIES:
                        delay = 2 ** attempt
                        logger.warning(
                            "Retry %d/%d for %s (%s): %s – backing off %.1fs",
                            attempt + 1,
                            self._MAX_RETRIES,
                            summary_type.value if hasattr(summary_type, "value") else summary_type,
                            resolved_provider,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "All retries exhausted for %s (%s): %s",
                            summary_type.value if hasattr(summary_type, "value") else summary_type,
                            resolved_provider,
                            exc,
                        )

            # All retries exhausted
            raise SummaryGenerationError(
                summary_type=summary_type.value if hasattr(summary_type, "value") else str(summary_type),
                provider=resolved_provider,
                message=f"Failed after {self._MAX_RETRIES + 1} attempts",
                cause=last_error,
            )

        finally:
            await provider.close()

    # ------------------------------------------------------------------
    # Batch (all types)
    # ------------------------------------------------------------------

    async def generate_all_summaries(
        self,
        transcript_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> list[SummaryResult]:
        """Generate all summary types concurrently.

        Each ``SummaryType`` is processed in its own task via
        ``asyncio.gather``.  Individual failures are logged but do **not**
        prevent other summaries from completing.

        Args:
            transcript_text: Raw transcript to summarise.
            provider_name:   LLM provider override.
            model:           Model override.

        Returns:
            A list of ``SummaryResult`` objects for every summary type
            that completed successfully.
        """
        tasks = [
            self.generate_summary(
                transcript_text=transcript_text,
                summary_type=st,
                provider_name=provider_name,
                model=model,
            )
            for st in SummaryType
        ]

        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[SummaryResult] = []
        for outcome, st in zip(outcomes, SummaryType, strict=False):
            if isinstance(outcome, Exception):
                logger.error(
                    "Summary generation failed for type %s: %s",
                    st.value if hasattr(st, "value") else st,
                    outcome,
                )
            else:
                results.append(outcome)

        logger.info(
            "Batch summary generation complete: %d/%d succeeded",
            len(results),
            len(list(SummaryType)),
        )

        return results
