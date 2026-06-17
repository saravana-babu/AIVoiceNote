"""LLM Provider Abstraction Layer for VoiceMind.

Provides a unified interface for interacting with multiple LLM providers
(OpenAI, Anthropic, Google Gemini) through a common abstract base class.
Each provider adapter handles authentication, request formatting, and
response parsing specific to its API.

Usage:
    provider = get_provider("openai")
    response = await provider.generate("Summarize this note...")
    await provider.close()
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Structured response returned by every LLM provider.

    Attributes:
        content: The generated text content from the model.
        model: The specific model identifier used for generation.
        provider: Name of the provider that produced this response.
        prompt_tokens: Number of tokens in the input prompt.
        completion_tokens: Number of tokens in the generated output.
        total_tokens: Combined prompt and completion token count.
    """

    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMProviderError(Exception):
    """Raised when an LLM provider returns a non-successful response.

    Attributes:
        provider: Name of the provider that raised the error.
        status_code: HTTP status code from the provider API, or ``None``
            if the error occurred before a response was received.
        message: Human-readable error description.
    """

    def __init__(
        self,
        provider: str,
        status_code: int | None,
        message: str,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        self.message = message
        super().__init__(
            f"[{provider}] (HTTP {status_code}): {message}"
        )


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract base class that every LLM provider adapter must implement.

    Subclasses are responsible for:
    * Configuring an ``httpx.AsyncClient`` with the correct base URL and
      authentication headers.
    * Formatting request bodies according to the provider's API spec.
    * Parsing provider-specific response payloads into a unified
      :class:`LLMResponse`.
    """

    provider_name: str

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a completion from the language model.

        Args:
            prompt: The user-facing input text to send to the model.
            system_prompt: Optional system-level instructions that guide
                the model's behaviour and output format.
            temperature: Sampling temperature (0.0–2.0). Lower values
                produce more deterministic output.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            An :class:`LLMResponse` containing the generated text and
            associated usage metadata.

        Raises:
            LLMProviderError: If the provider API returns a non-200 status
                code or an otherwise unusable response.
        """
        ...

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources.

        Safe to call multiple times. Subclasses that override this method
        should call ``super().close()`` to ensure proper cleanup.
        """


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Google Gemini adapter
# ---------------------------------------------------------------------------


class GeminiProvider(LLMProvider):
    """Adapter for the Google Gemini (Generative Language) API.

    Uses ``httpx.AsyncClient`` to send requests to
    ``https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent``.
    The API key is passed as a query parameter rather than a header.
    Responses are requested with ``responseMimeType: application/json``
    so the model output is structured JSON.

    Args:
        api_key: Google API key.
        model: Model identifier. Defaults to ``gemini-2.0-flash``.
        timeout: HTTP request timeout in seconds. Defaults to ``120.0``.
    """

    provider_name: str = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com",
            timeout=timeout,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a content generation request to Google Gemini.

        The system prompt is provided via the ``systemInstruction`` field.
        Token counts are extracted from the ``usageMetadata`` block
        (``promptTokenCount`` / ``candidatesTokenCount`` /
        ``totalTokenCount``).

        Raises:
            LLMProviderError: On any non-200 HTTP response.
        """

        url = (
            f"/v1beta/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )

        body: dict = {
            "contents": [
                {"parts": [{"text": prompt}]},
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if "json" in system_prompt.lower() or "json" in prompt.lower():
            body["generationConfig"]["responseMimeType"] = "application/json"

        import time
        from app.core.metrics import track_ai_processing
        
        start_time = time.time()
        response = await self._client.post(url, json=body)
        duration = time.time() - start_time
        track_ai_processing(duration)

        if response.status_code != 200:
            raise LLMProviderError(
                provider=self.provider_name,
                status_code=response.status_code,
                message=response.text,
            )

        data = response.json()
        usage = data.get("usageMetadata", {})

        return LLMResponse(
            content=data["candidates"][0]["content"]["parts"][0]["text"],
            model=self._model,
            provider=self.provider_name,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
        )

    async def close(self) -> None:
        """Close the underlying ``httpx.AsyncClient``."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "gemini": GeminiProvider,
}

_ENV_KEY_MAP: dict[str, str] = {
    "gemini": "GOOGLE_API_KEY",
}


def get_provider(
    name: str,
    *,
    model: str | None = None,
    timeout: float = 120.0,
) -> LLMProvider:
    """Create and return an LLM provider instance by name.

    Reads the required API key from the corresponding environment
    variable and instantiates the appropriate provider adapter.

    Args:
        name: Provider name — one of ``"gemini"`` (case-insensitive).
        model: Optional model identifier override. When ``None``, each
            provider falls back to its own default model.
        timeout: HTTP request timeout in seconds passed through to the
            underlying ``httpx.AsyncClient``. Defaults to ``120.0``.

    Returns:
        A fully configured :class:`LLMProvider` instance ready for use.

    Raises:
        ValueError: If the provider name is unrecognised or the
            required API key environment variable is not set.

    Example::

        provider = get_provider("gemini", model="gemini-2.0-flash")
        response = await provider.generate("Hello!")
        await provider.close()
    """

    name_lower = name.lower().strip()

    if name_lower not in _PROVIDER_REGISTRY:
        supported = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(
            f"Unknown LLM provider '{name}'. "
            f"Supported providers: {supported}"
        )

    env_var = _ENV_KEY_MAP[name_lower]
    api_key = os.environ.get(env_var)

    if not api_key:
        raise ValueError(
            f"Missing required environment variable '{env_var}' "
            f"for provider '{name_lower}'. "
            f"Set it before calling get_provider()."
        )

    provider_cls = _PROVIDER_REGISTRY[name_lower]

    kwargs: dict = {"api_key": api_key, "timeout": timeout}
    if model is not None:
        kwargs["model"] = model

    return provider_cls(**kwargs)
