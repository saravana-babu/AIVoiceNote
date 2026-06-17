"""Prompt templates for AI-powered transcript summarisation.

Provides structured prompt templates for different summary styles,
each with a validated JSON schema describing the expected output shape.
"""

from dataclasses import dataclass
from enum import Enum


class SummaryType(str, Enum):
    """Supported summary output styles."""

    EXECUTIVE = "executive"
    DETAILED = "detailed"
    BULLET = "bullet"
    ACTION_ITEMS = "action_items"
    FOLLOW_UPS = "follow_ups"


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Immutable container for a single summarisation prompt.

    Attributes:
        summary_type: The style of summary this template produces.
        system_prompt: Instructions sent as the system / developer message.
        user_prompt_template: User-turn template containing a ``{transcript}``
            placeholder that is filled at render time.
        json_schema: JSON-Schema dict describing the expected output shape.
    """

    summary_type: SummaryType
    system_prompt: str
    user_prompt_template: str
    json_schema: dict


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

_EXECUTIVE_TEMPLATE = PromptTemplate(
    summary_type=SummaryType.EXECUTIVE,
    system_prompt=(
        "You are an expert meeting and note summariser specialising in "
        "executive-level communication. Your sole task is to distil a "
        "transcript into a concise executive summary that a busy leader can "
        "absorb in under two minutes.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema the "
        "user provides. Do NOT wrap the JSON in markdown code fences, "
        "backticks, or any other formatting.\n"
        "2. The 'title' must be a short, descriptive headline (≤12 words).\n"
        "3. The 'summary' must be 2-3 concise paragraphs capturing the "
        "essence of the discussion — decisions made, outcomes, and context.\n"
        "4. 'key_points' must list 3-7 of the most important insights or "
        "decisions, each as a single clear sentence.\n"
        "5. 'sentiment' must be exactly one of: positive, negative, neutral, "
        "mixed.\n"
        "6. Be thorough but concise — prefer clarity over verbosity."
    ),
    user_prompt_template=(
        "Given the following transcript, generate an executive summary that "
        "captures the most critical information a senior stakeholder needs to "
        "know.\n\n"
        "Transcript:\n{transcript}\n\n"
        'Output the result as JSON with this schema:\n'
        '{{\n'
        '  "title": "string - concise title (≤12 words)",\n'
        '  "summary": "string - 2-3 paragraph executive summary",\n'
        '  "key_points": ["string - key insight or decision"],\n'
        '  "sentiment": "string - overall sentiment: positive/negative/neutral/mixed"\n'
        '}}'
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "mixed"],
            },
        },
        "required": ["title", "summary", "key_points", "sentiment"],
        "additionalProperties": False,
    },
)

_DETAILED_TEMPLATE = PromptTemplate(
    summary_type=SummaryType.DETAILED,
    system_prompt=(
        "You are an expert meeting and note summariser. Your task is to "
        "produce a detailed, well-structured summary organised into logical "
        "sections so that a reader who missed the original discussion can "
        "fully understand what was covered.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema the "
        "user provides. Do NOT wrap the JSON in markdown code fences, "
        "backticks, or any other formatting.\n"
        "2. The 'title' must be a descriptive headline (≤15 words).\n"
        "3. The 'overview' must be a single paragraph (3-5 sentences) giving "
        "a high-level snapshot of the entire transcript.\n"
        "4. 'sections' must contain 2-6 logically grouped sections. Each "
        "section needs a clear 'heading' and a multi-sentence 'content' "
        "paragraph that thoroughly covers that topic.\n"
        "5. The 'conclusion' must be 1-2 sentences summarising the final "
        "outcome or next steps.\n"
        "6. Be thorough but concise — prefer clarity over verbosity."
    ),
    user_prompt_template=(
        "Given the following transcript, generate a detailed sectioned "
        "summary that organises the content into logical topics.\n\n"
        "Transcript:\n{transcript}\n\n"
        'Output the result as JSON with this schema:\n'
        '{{\n'
        '  "title": "string - descriptive title",\n'
        '  "overview": "string - high-level overview paragraph",\n'
        '  "sections": [\n'
        '    {{\n'
        '      "heading": "string - section heading",\n'
        '      "content": "string - detailed section content"\n'
        '    }}\n'
        '  ],\n'
        '  "conclusion": "string - concluding remarks or next steps"\n'
        '}}'
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "overview": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["heading", "content"],
                    "additionalProperties": False,
                },
            },
            "conclusion": {"type": "string"},
        },
        "required": ["title", "overview", "sections", "conclusion"],
        "additionalProperties": False,
    },
)

_BULLET_TEMPLATE = PromptTemplate(
    summary_type=SummaryType.BULLET,
    system_prompt=(
        "You are an expert meeting and note summariser. Your task is to "
        "extract the key information from a transcript and organise it into "
        "categorised bullet points for quick scanning.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema the "
        "user provides. Do NOT wrap the JSON in markdown code fences, "
        "backticks, or any other formatting.\n"
        "2. The 'title' must be a concise headline (≤12 words).\n"
        "3. Group bullets into 2-6 meaningful categories (e.g., Decisions, "
        "Discussion Points, Open Questions, Updates).\n"
        "4. Each category must contain 1-8 bullet items, each expressed as a "
        "single clear sentence.\n"
        "5. Ensure no important point from the transcript is omitted.\n"
        "6. Be thorough but concise — prefer clarity over verbosity."
    ),
    user_prompt_template=(
        "Given the following transcript, extract the key information and "
        "organise it into categorised bullet points.\n\n"
        "Transcript:\n{transcript}\n\n"
        'Output the result as JSON with this schema:\n'
        '{{\n'
        '  "title": "string - concise title",\n'
        '  "bullets": [\n'
        '    {{\n'
        '      "category": "string - category name",\n'
        '      "items": ["string - bullet point"]\n'
        '    }}\n'
        '  ]\n'
        '}}'
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "bullets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["category", "items"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["title", "bullets"],
        "additionalProperties": False,
    },
)

_ACTION_ITEMS_TEMPLATE = PromptTemplate(
    summary_type=SummaryType.ACTION_ITEMS,
    system_prompt=(
        "You are an expert meeting and note summariser specialising in "
        "extracting actionable tasks. Your sole task is to identify every "
        "action item, commitment, and to-do mentioned or implied in the "
        "transcript.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema the "
        "user provides. Do NOT wrap the JSON in markdown code fences, "
        "backticks, or any other formatting.\n"
        "2. Each 'action' must be a clear, imperative statement describing "
        "the task (e.g., 'Send the revised proposal to the client').\n"
        "3. 'assignee' must be the person responsible if mentioned, or null "
        "if not explicitly stated.\n"
        "4. 'priority' must be exactly one of: high, medium, low — inferred "
        "from urgency cues, deadlines, and emphasis in the transcript.\n"
        "5. 'deadline' must be the stated or implied due date as a string "
        "(e.g., '2026-06-20', 'end of week', 'ASAP'), or null if none is "
        "mentioned.\n"
        "6. Do NOT fabricate action items that are not supported by the "
        "transcript. Only extract what is genuinely discussed.\n"
        "7. Be thorough — capture every task, even minor ones."
    ),
    user_prompt_template=(
        "Given the following transcript, extract all action items, tasks, "
        "and commitments. For each item identify who is responsible (if "
        "stated), the priority level, and any deadline mentioned.\n\n"
        "Transcript:\n{transcript}\n\n"
        'Output the result as JSON with this schema:\n'
        '{{\n'
        '  "items": [\n'
        '    {{\n'
        '      "action": "string - clear description of the task",\n'
        '      "assignee": "string or null - person responsible",\n'
        '      "priority": "string - high/medium/low",\n'
        '      "deadline": "string or null - due date if mentioned"\n'
        '    }}\n'
        '  ]\n'
        '}}'
    ),
    json_schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "assignee": {"type": ["string", "null"]},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "deadline": {"type": ["string", "null"]},
                    },
                    "required": ["action", "assignee", "priority", "deadline"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    },
)

_FOLLOW_UPS_TEMPLATE = PromptTemplate(
    summary_type=SummaryType.FOLLOW_UPS,
    system_prompt=(
        "You are an expert meeting and note summariser specialising in "
        "identifying follow-up topics. Your task is to surface every topic "
        "that requires further discussion, research, or a subsequent meeting "
        "based on the transcript.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema the "
        "user provides. Do NOT wrap the JSON in markdown code fences, "
        "backticks, or any other formatting.\n"
        "2. 'topic' must be a brief label for the follow-up (≤10 words).\n"
        "3. 'description' must explain why this needs follow-up and what "
        "should be addressed (1-3 sentences).\n"
        "4. 'participants' must list the names of people who should be "
        "involved. Use an empty array if no specific people are mentioned.\n"
        "5. 'suggested_date' must be a date string if one is mentioned or "
        "implied, or null otherwise.\n"
        "6. Do NOT fabricate follow-ups that are not supported by the "
        "transcript. Only extract what is genuinely discussed or implied.\n"
        "7. Be thorough — capture every follow-up, even minor ones."
    ),
    user_prompt_template=(
        "Given the following transcript, identify all topics that require "
        "follow-up discussion, further research, or a subsequent meeting. "
        "For each, note the relevant participants and any suggested "
        "timeline.\n\n"
        "Transcript:\n{transcript}\n\n"
        'Output the result as JSON with this schema:\n'
        '{{\n'
        '  "items": [\n'
        '    {{\n'
        '      "topic": "string - brief follow-up topic label",\n'
        '      "description": "string - why this needs follow-up",\n'
        '      "participants": ["string - person involved"],\n'
        '      "suggested_date": "string or null - suggested date"\n'
        '    }}\n'
        '  ]\n'
        '}}'
    ),
    json_schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "description": {"type": "string"},
                        "participants": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "suggested_date": {"type": ["string", "null"]},
                    },
                    "required": [
                        "topic",
                        "description",
                        "participants",
                        "suggested_date",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

SUMMARY_TEMPLATES: dict[SummaryType, PromptTemplate] = {
    SummaryType.EXECUTIVE: _EXECUTIVE_TEMPLATE,
    SummaryType.DETAILED: _DETAILED_TEMPLATE,
    SummaryType.BULLET: _BULLET_TEMPLATE,
    SummaryType.ACTION_ITEMS: _ACTION_ITEMS_TEMPLATE,
    SummaryType.FOLLOW_UPS: _FOLLOW_UPS_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def render_prompt(
    summary_type: SummaryType,
    transcript: str,
) -> tuple[str, str]:
    """Render the system and user prompts for the given summary type.

    Args:
        summary_type: The desired summary style.
        transcript: The raw transcript text to embed in the user prompt.

    Returns:
        A ``(system_prompt, user_prompt)`` tuple ready to be sent to an LLM.

    Raises:
        KeyError: If *summary_type* is not a recognised ``SummaryType``.
    """
    template = SUMMARY_TEMPLATES[summary_type]
    user_prompt = template.user_prompt_template.format(transcript=transcript)
    return template.system_prompt, user_prompt
