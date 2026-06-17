"""Gemini Service.

Exposes high-level unified functions for summarization, meeting minutes,
note enhancements, and chatbot queries using the LLM provider abstraction layer.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.services.summary_service import SummaryService, SummaryResult
from app.services.minutes_service import MeetingMinutesService, MinutesResult
from app.services.enhancement_service import EnhancementService, EnhancementResult
from app.services.knowledge_chat import KnowledgeChatService
from app.services.prompt_templates import SummaryType
from app.services.enhancement_prompts import EnhancementType

class GeminiService:
    @staticmethod
    async def generate_summary(
        transcript_text: str,
        summary_type: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> SummaryResult:
        """Generate a structured summary from transcript text using Gemini."""
        service = SummaryService(
            default_provider="gemini",
            default_temperature=temperature or 0.3,
            default_max_tokens=max_tokens or 4096,
        )
        
        # Convert string type to enum if necessary
        s_type = SummaryType(summary_type) if isinstance(summary_type, str) else summary_type
        
        return await service.generate_summary(
            transcript_text=transcript_text,
            summary_type=s_type,
            provider_name="gemini",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    @staticmethod
    async def generate_meeting_minutes(
        transcript_text: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> MinutesResult:
        """Generate meeting minutes from transcript text using Gemini."""
        service = MeetingMinutesService(
            default_provider="gemini",
            default_temperature=temperature or 0.3,
            default_max_tokens=max_tokens or 4096,
        )
        return await service.generate_minutes(
            transcript_text=transcript_text,
            provider_name="gemini",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    @staticmethod
    async def enhance_notes(
        text: str,
        enhancement_type: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> EnhancementResult:
        """Enhance notes text using Gemini."""
        service = EnhancementService(
            default_provider="gemini",
            default_temperature=temperature or 0.3,
            default_max_tokens=max_tokens or 4096,
        )
        
        e_type = EnhancementType(enhancement_type) if isinstance(enhancement_type, str) else enhancement_type
        
        return await service.generate_enhancement(
            text=text,
            enhancement_type=e_type,
            provider_name="gemini",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

    @staticmethod
    async def knowledge_chat(
        db: Session,
        message: str,
        user_id: str,
        collection_id: Optional[str] = None,
        source_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform a conversational query on the knowledge collection using Gemini."""
        return await KnowledgeChatService.chat(
            db=db,
            message=message,
            user_id=user_id,
            collection_id=collection_id,
            source_id=source_id,
            chat_history=chat_history,
            provider_name="gemini",
            model=model
        )

    # camelCase aliases for front-end/external invocation compatibility
    generateSummary = generate_summary
    generateMeetingMinutes = generate_meeting_minutes
    enhanceNotes = enhance_notes
    knowledgeChat = knowledge_chat
