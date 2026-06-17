"""Knowledge Chat Service.

Orchestrates interactive chat sessions powered by the retrieved knowledge context.
Supports streaming or non-streaming chat with source citations, suggested questions,
and provider abstraction.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.services.llm_providers import (
    get_provider,
    GeminiProvider,
    LLMResponse,
)
from app.services.knowledge_retrieval import KnowledgeRetrievalService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT_TEMPLATE = (
    "You are a helpful AI Knowledge Assistant for VoiceMind.\n"
    "Your goal is to answer the user's questions based ONLY on the provided knowledge context.\n"
    "Use clear, conversational formatting. If the context contains relevant information, "
    "cite the sources using their citation number in brackets, e.g. [1] or [2] in your sentences.\n"
    "Do NOT fabricate facts. If the answer cannot be found in the provided context, "
    "honestly reply: \"I cannot find this in your knowledge base.\"\n\n"
    "Here is the context:\n"
    "{context}"
)


class KnowledgeChatService:
    @staticmethod
    async def chat(
        db: Session,
        message: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform a standard non-streaming AI chat request with citations and suggested questions."""
        # 1. Build context and retrieve citations
        context, citations = await KnowledgeRetrievalService.build_context(
            db=db,
            query=message,
            user_id=user_id,
            collection_id=collection_id,
            source_id=source_id,
        )

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(context=context or "No relevant context found.")
        
        # 2. Get provider settings
        from app.core.config import settings
        resolved_provider = provider_name or settings.LLM_DEFAULT_PROVIDER

        # Check if the provider is enabled
        # If API keys are missing, we return a mock response for easy offline validation
        has_key = False
        if resolved_provider == "openai" and settings.OPENAI_API_KEY:
            has_key = True
        elif resolved_provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            has_key = True
        elif resolved_provider == "gemini" and settings.GOOGLE_API_KEY:
            has_key = True

        if not has_key:
            logger.info("LLM provider API key missing. Returning mock conversational response.")
            response_content = (
                f"This is a mock conversational response about: '{message}'."
            )
            if citations:
                response_content += f" I found relevant information in source [{citations[0]['index']}] '{citations[0]['title']}'."
            else:
                response_content += " I could not find any matching documents in your knowledge base."
            
            suggested = KnowledgeChatService._generate_suggested_questions(message, citations)
            return {
                "response": response_content,
                "citations": citations,
                "suggested_questions": suggested,
                "provider": resolved_provider,
                "model": "mock-model",
            }

        provider = get_provider(resolved_provider, model=model)

        try:
            # Format conversational prompt history if present
            formatted_prompt = ""
            if chat_history:
                for turn in chat_history:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    formatted_prompt += f"{role.upper()}: {content}\n"
            formatted_prompt += f"USER: {message}"

            response: LLMResponse = await provider.generate(
                prompt=formatted_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
            )
            
            suggested = KnowledgeChatService._generate_suggested_questions(message, citations)
            return {
                "response": response.content,
                "citations": citations,
                "suggested_questions": suggested,
                "provider": resolved_provider,
                "model": response.model,
            }
        finally:
            await provider.close()

    @staticmethod
    async def chat_stream(
        db: Session,
        message: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream conversational responses from providers and append metadata at the end."""
        # 1. Build context and retrieve citations
        context, citations = await KnowledgeRetrievalService.build_context(
            db=db,
            query=message,
            user_id=user_id,
            collection_id=collection_id,
            source_id=source_id,
        )

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(context=context or "No relevant context found.")
        
        # 2. Get provider settings
        from app.core.config import settings
        resolved_provider = provider_name or settings.LLM_DEFAULT_PROVIDER

        # Check if API keys are missing
        has_key = False
        if resolved_provider == "openai" and settings.OPENAI_API_KEY:
            has_key = True
        elif resolved_provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            has_key = True
        elif resolved_provider == "gemini" and settings.GOOGLE_API_KEY:
            has_key = True

        suggested = KnowledgeChatService._generate_suggested_questions(message, citations)
        metadata = {
            "citations": citations,
            "suggested_questions": suggested,
            "provider": resolved_provider,
        }

        if not has_key:
            # Stream a mock response chunk by chunk
            mock_text = f"Conversational mock stream answer for: '{message}'."
            if citations:
                mock_text += f" Found context in [{citations[0]['index']}] '{citations[0]['title']}'."
            else:
                mock_text += " I couldn't locate any matching documents in your collection."
            
            words = mock_text.split(" ")
            for word in words:
                yield json.dumps({"type": "content", "delta": word + " "}) + "\n"
                await asyncio.sleep(0.08)
            
            # Send citations metadata at the end
            yield json.dumps({"type": "metadata", "data": metadata}) + "\n"
            return

        provider = get_provider(resolved_provider, model=model)

        try:
            # Build history prompt
            formatted_prompt = ""
            if chat_history:
                for turn in chat_history:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    formatted_prompt += f"{role.upper()}: {content}\n"
            formatted_prompt += f"USER: {message}"

            # We use the provider client directly to perform standard Server-Sent Events (SSE) stream parsing
            # according to provider API specs.
            if isinstance(provider, GeminiProvider):
                url = f"/v1beta/models/{provider._model}:streamGenerateContent?key={provider._api_key}"
                body = {
                    "contents": [
                        {"parts": [{"text": formatted_prompt}]},
                    ],
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}],
                    },
                    "generationConfig": {
                        "temperature": 0.3,
                    },
                }
                
                async with provider._client.stream("POST", url, json=body) as response:
                    if response.status_code != 200:
                        yield json.dumps({"type": "error", "message": f"Gemini Stream Failed: {await response.aread()}"}) + "\n"
                        return
                    
                    async for line in response.iter_lines():
                        try:
                            # Gemini sends lines of JSON chunks in an array
                            line_cleaned = line.strip().rstrip(",").lstrip("[").rstrip("]")
                            if not line_cleaned:
                                continue
                            chunk_json = json.loads(line_cleaned)
                            delta = chunk_json["candidates"][0]["content"]["parts"][0].get("text", "")
                            if delta:
                                yield json.dumps({"type": "content", "delta": delta}) + "\n"
                        except Exception:
                            pass
            else:
                # Fallback to standard generate
                resp = await provider.generate(formatted_prompt, system_prompt)
                yield json.dumps({"type": "content", "delta": resp.content}) + "\n"

            # Yield citations metadata at the end
            yield json.dumps({"type": "metadata", "data": metadata}) + "\n"
        finally:
            await provider.close()

    @staticmethod
    def _generate_suggested_questions(query: str, citations: List[Dict[str, Any]]) -> List[str]:
        """Generate smart suggested follow-up questions based on query and context citations."""
        suggested = []
        if citations:
            suggested.append(f"Tell me more about '{citations[0]['title']}'")
            if len(citations) > 1:
                suggested.append(f"How does this relate to '{citations[1]['title']}'?")
        suggested.append("Can you summarize the action items?")
        return suggested[:3]
