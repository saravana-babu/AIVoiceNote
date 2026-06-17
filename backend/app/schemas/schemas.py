from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from datetime import datetime

# --- USER SCHEMAS ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class OAuthRequest(BaseModel):
    token: str
    display_name: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

# --- WORKSPACE SCHEMAS ---
class WorkspaceBase(BaseModel):
    name: str

class WorkspaceCreate(WorkspaceBase):
    pass

class WorkspaceResponse(WorkspaceBase):
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- NOTE SCHEMAS ---
class NoteBase(BaseModel):
    title: str
    duration_sec: int = 0
    file_path: str
    status: str = "completed"
    workspace_id: Optional[str] = None

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    duration_sec: Optional[int] = None
    file_path: Optional[str] = None
    status: Optional[str] = None
    workspace_id: Optional[str] = None

class NoteResponse(NoteBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    tags: List[str] = []

    class Config:
        from_attributes = True

# --- RECORDING SCHEMAS ---
class RecordingBase(BaseModel):
    note_id: str
    local_uri: str
    is_uploaded: bool = False

class RecordingCreate(RecordingBase):
    pass

class RecordingResponse(RecordingBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- TRANSCRIPT SCHEMAS ---
class TranscriptBase(BaseModel):
    text: str
    confidence: Optional[float] = None

class TranscriptCreate(TranscriptBase):
    note_id: str

class TranscriptResponse(TranscriptBase):
    note_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- SUMMARY SCHEMAS ---
class SummaryGenerateRequest(BaseModel):
    """Request to generate a single AI summary for a note."""
    note_id: str
    summary_type: str = Field(
        ...,
        description="Type of summary to generate",
        pattern="^(executive|detailed|bullet|action_items|follow_ups)$"
    )
    provider: Optional[str] = Field(
        None,
        description="LLM provider to use (openai, anthropic, gemini). Defaults to server config."
    )
    model: Optional[str] = Field(
        None,
        description="Override the default model for the chosen provider."
    )

class SummaryGenerateAllRequest(BaseModel):
    """Request to generate all summary types for a note."""
    note_id: str
    provider: Optional[str] = Field(
        None,
        description="LLM provider to use. Defaults to server config."
    )
    model: Optional[str] = Field(
        None,
        description="Override the default model for the chosen provider."
    )

class StructuredSummaryResponse(BaseModel):
    """Response containing a structured AI-generated summary."""
    id: str
    note_id: str
    summary_type: str
    structured_data: dict
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SummaryGenerateResponse(BaseModel):
    """Response for a single summary generation request."""
    summary: StructuredSummaryResponse
    generation_time_ms: float

class SummaryBatchResponse(BaseModel):
    """Response for batch summary generation."""
    summaries: List[StructuredSummaryResponse]
    total_generation_time_ms: float
    failed_types: List[str] = []

# --- MEETING MINUTES SCHEMAS ---
class DiscussionPointSchema(BaseModel):
    topic: str
    summary: str

class ActionItemSchema(BaseModel):
    task: str
    owner: str
    due_date: str

class MeetingMinutesBase(BaseModel):
    overview: str
    agenda: List[str]
    discussion_points: List[DiscussionPointSchema]
    decisions: List[str]
    risks: List[str]
    action_items: List[ActionItemSchema]

class MeetingMinutesGenerateRequest(BaseModel):
    note_id: str
    provider: Optional[str] = None
    model: Optional[str] = None

class MeetingMinutesResponse(MeetingMinutesBase):
    note_id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MeetingMinutesGenerateResponse(BaseModel):
    minutes: MeetingMinutesResponse
    generation_time_ms: float


# --- SEARCH SCHEMAS ---
class SearchResultSchema(BaseModel):
    note: NoteResponse
    score: float
    match_type: str  # semantic | fts | hybrid

    class Config:
        from_attributes = True


# --- EMAIL SCHEMAS ---
class EmailSendRequest(BaseModel):
    note_id: str
    recipient: EmailStr
    subject: str
    provider: str = "smtp"  # smtp | gmail
    include_transcript: bool = True
    include_summary: bool = True
    include_minutes: bool = True

class EmailScheduleRequest(BaseModel):
    note_id: str
    recipient: EmailStr
    subject: str
    provider: str = "smtp"  # smtp | gmail
    include_transcript: bool = True
    include_summary: bool = True
    include_minutes: bool = True
    scheduled_at: datetime

class ScheduledEmailResponse(BaseModel):
    id: str
    note_id: str
    user_id: str
    recipient: str
    subject: str
    email_type: str
    provider: str
    include_transcript: bool
    include_summary: bool
    include_minutes: bool
    status: str
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- NOTE ENHANCEMENT SCHEMAS ---
class NoteEnhancementGenerateRequest(BaseModel):
    note_id: str
    enhancement_type: str  # improved|professional|blog|executive_report|email|project_update
    provider: Optional[str] = None
    model: Optional[str] = None

class NoteEnhancementResponse(BaseModel):
    id: str
    note_id: str
    enhancement_type: str
    structured_data: dict
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NoteEnhancementGenerateResponse(BaseModel):
    enhancement: NoteEnhancementResponse
    generation_time_ms: float


# --- KNOWLEDGE HUB SCHEMAS ---
class KnowledgeCollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None

class KnowledgeCollectionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class KnowledgeSourceResponse(BaseModel):
    id: str
    title: str
    source_type: str
    file_path: Optional[str] = None
    note_id: Optional[str] = None
    collection_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class KnowledgeSearchRequest(BaseModel):
    query: str
    collection_id: Optional[str] = None
    source_id: Optional[str] = None
    limit: Optional[int] = 20

class KnowledgeSearchResultResponse(BaseModel):
    chunk_id: str
    source_id: str
    source_title: str
    source_type: str
    content: str
    score: float

class KnowledgeChatCitation(BaseModel):
    id: str
    index: int
    title: str
    source_type: str
    note_id: Optional[str] = None

class KnowledgeChatRequest(BaseModel):
    message: str
    collection_id: Optional[str] = None
    source_id: Optional[str] = None
    chat_history: Optional[List[Dict[str, str]]] = None
    provider: Optional[str] = None
    model: Optional[str] = None

class KnowledgeChatResponse(BaseModel):
    response: str
    citations: List[KnowledgeChatCitation]
    suggested_questions: List[str]
    provider: str
    model: str




