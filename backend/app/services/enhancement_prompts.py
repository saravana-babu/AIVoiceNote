from dataclasses import dataclass
from enum import Enum

class EnhancementType(str, Enum):
    IMPROVED = "improved"
    PROFESSIONAL = "professional"
    BLOG = "blog"
    EXECUTIVE_REPORT = "executive_report"
    EMAIL = "email"
    PROJECT_UPDATE = "project_update"

@dataclass(frozen=True, slots=True)
class EnhancementTemplate:
    enhancement_type: EnhancementType
    system_prompt: str
    user_prompt_template: str
    json_schema: dict

_IMPROVED_TEMPLATE = EnhancementTemplate(
    enhancement_type=EnhancementType.IMPROVED,
    system_prompt=(
        "You are an expert editor. Your task is to take a raw note or transcript "
        "and generate an improved version. Clean up grammar, fix typos, organize it "
        "with logical headers, and make it clear and highly readable while preserving "
        "all original facts and information.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema. Do NOT wrap the JSON in markdown code fences.\n"
        "2. The 'content' field must contain clean, well-formatted Markdown text."
    ),
    user_prompt_template=(
        "Please enhance the following note/transcript:\n\n{text}\n\n"
        "Output the result as JSON with this schema:\n"
        "{{\n"
        '  "title": "string - descriptive note title",\n'
        '  "content": "string - the improved note in structured Markdown format"\n'
        "}}"
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["title", "content"],
        "additionalProperties": False
    }
)

_PROFESSIONAL_TEMPLATE = EnhancementTemplate(
    enhancement_type=EnhancementType.PROFESSIONAL,
    system_prompt=(
        "You are a professional business writer. Your task is to transform "
        "a raw note or transcript into a professional version. Rephrase the text "
        "using formal business vocabulary, structured bullet points, and professional phrasing "
        "suitable for corporate distribution.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON that conforms exactly to the schema.\n"
        "2. The 'content' must use professional business English and Markdown formatting."
    ),
    user_prompt_template=(
        "Please convert the following notes into a professional version:\n\n{text}\n\n"
        "Output the result as JSON with this schema:\n"
        "{{\n"
        '  "title": "string - formal note title",\n'
        '  "content": "string - the professional note in structured Markdown format"\n'
        "}}"
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["title", "content"],
        "additionalProperties": False
    }
)

_BLOG_TEMPLATE = EnhancementTemplate(
    enhancement_type=EnhancementType.BLOG,
    system_prompt=(
        "You are a professional blog writer. Your task is to turn a note or transcript "
        "into an engaging blog post draft. Create a catchy headline, write structured "
        "body sections with headings that flow logically, incorporate storytelling, "
        "and end with a compelling call-to-action.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON.\n"
        "2. Make the tone conversational, engaging, and search-optimized."
    ),
    user_prompt_template=(
        "Please write a blog post draft based on the following notes:\n\n{text}\n\n"
        "Output the result as JSON with this schema:\n"
        "{{\n"
        '  "title": "string - catchy blog post headline",\n'
        '  "sections": [\n'
        '    {{\n'
        '      "heading": "string - section title",\n'
        '      "content": "string - section content paragraphs"\n'
        '    }}\n'
        '  ],\n'
        '  "conclusion": "string - blog post wrap-up and call-to-action"\n'
        "}}"
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "heading": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["heading", "content"]
                }
            },
            "conclusion": {"type": "string"}
        },
        "required": ["title", "sections", "conclusion"],
        "additionalProperties": False
    }
)

_EXECUTIVE_REPORT_TEMPLATE = EnhancementTemplate(
    enhancement_type=EnhancementType.EXECUTIVE_REPORT,
    system_prompt=(
        "You are an executive business consultant. Your task is to create a structured "
        "Executive Report based on the provided notes/transcript. Focus on formal reports, "
        "outlining the executive summary, background context, key findings, and recommendations.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON.\n"
        "2. Be concise, strategic, and professional."
    ),
    user_prompt_template=(
        "Please compile an executive report from the following notes:\n\n{text}\n\n"
        "Output the result as JSON with this schema:\n"
        "{{\n"
        '  "title": "string - report title",\n'
        '  "executive_summary": "string - concise executive overview",\n'
        '  "background": "string - background and objectives",\n'
        '  "key_findings": ["string - key finding or insight"],\n'
        '  "recommendations": ["string - actionable recommendation"]\n'
        "}}"
    ),
    json_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "executive_summary": {"type": "string"},
            "background": {"type": "string"},
            "key_findings": {
                "type": "array",
                "items": {"type": "string"}
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["title", "executive_summary", "background", "key_findings", "recommendations"],
        "additionalProperties": False
    }
)

_EMAIL_TEMPLATE = EnhancementTemplate(
    enhancement_type=EnhancementType.EMAIL,
    system_prompt=(
        "You are an assistant. Your task is to draft a business email based on "
        "the provided notes/transcript. Write a clear and compelling subject line, "
        "a polite greeting, clean formatted email body paragraphs, and a signature placeholder.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON."
    ),
    user_prompt_template=(
        "Please draft a professional email based on the following notes:\n\n{text}\n\n"
        "Output the result as JSON with this schema:\n"
        "{{\n"
        '  "subject": "string - email subject line",\n'
        '  "greeting": "string - greeting (e.g. Hi Team,)",\n'
        '  "body": "string - email body message",\n'
        '  "signature_placeholder": "string - closing (e.g. Best regards,\\n[Your Name])"\n'
        "}}"
    ),
    json_schema={
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "greeting": {"type": "string"},
            "body": {"type": "string"},
            "signature_placeholder": {"type": "string"}
        },
        "required": ["subject", "greeting", "body", "signature_placeholder"],
        "additionalProperties": False
    }
)

_PROJECT_UPDATE_TEMPLATE = EnhancementTemplate(
    enhancement_type=EnhancementType.PROJECT_UPDATE,
    system_prompt=(
        "You are an expert project manager. Your task is to synthesize raw notes/transcripts "
        "into a structured Project Update report. Determine project status, milestones completed, "
        "current blockers, and next steps.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON.\n"
        "2. The status_color MUST be exactly one of: 'green', 'yellow', or 'red'."
    ),
    user_prompt_template=(
        "Please generate a project update from the following notes:\n\n{text}\n\n"
        "Output the result as JSON with this schema:\n"
        "{{\n"
        '  "project_name": "string - name of the project",\n'
        '  "status_color": "string - exactly one of green|yellow|red",\n'
        '  "milestones_completed": ["string - milestone achieved"],\n'
        '  "current_blockers": ["string - blockers or delays"],\n'
        '  "next_steps": ["string - target tasks or next steps"]\n'
        "}}"
    ),
    json_schema={
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "status_color": {
                "type": "string",
                "enum": ["green", "yellow", "red"]
            },
            "milestones_completed": {
                "type": "array",
                "items": {"type": "string"}
            },
            "current_blockers": {
                "type": "array",
                "items": {"type": "string"}
            },
            "next_steps": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["project_name", "status_color", "milestones_completed", "current_blockers", "next_steps"],
        "additionalProperties": False
    }
)

ENHANCEMENT_TEMPLATES = {
    EnhancementType.IMPROVED: _IMPROVED_TEMPLATE,
    EnhancementType.PROFESSIONAL: _PROFESSIONAL_TEMPLATE,
    EnhancementType.BLOG: _BLOG_TEMPLATE,
    EnhancementType.EXECUTIVE_REPORT: _EXECUTIVE_REPORT_TEMPLATE,
    EnhancementType.EMAIL: _EMAIL_TEMPLATE,
    EnhancementType.PROJECT_UPDATE: _PROJECT_UPDATE_TEMPLATE,
}

def render_prompt(template: EnhancementTemplate, text: str) -> tuple[str, str]:
    user_prompt = template.user_prompt_template.format(text=text)
    return template.system_prompt, user_prompt
