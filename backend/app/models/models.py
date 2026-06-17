import uuid
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Float, Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

class SafeVector(TypeDecorator):
    impl = Text
    cache_ok = True

    def __init__(self, dim: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            if HAS_PGVECTOR:
                return dialect.type_descriptor(Vector(self.dim))
            else:
                return dialect.type_descriptor(Text())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            return value
        else:
            if isinstance(value, str):
                return value
            return json.dumps(list(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and HAS_PGVECTOR:
            if isinstance(value, str):
                try:
                    cleaned = value.strip('[]').split(',')
                    return [float(x) for x in cleaned if x.strip()]
                except Exception:
                    return value
            if hasattr(value, "tolist"):
                return value.tolist()
            return list(value)
        else:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    apple_id: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    refresh_tokens: Mapped[List["RefreshToken"]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    workspaces: Mapped[List["Workspace"]] = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")
    notes: Mapped[List["Note"]] = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    scheduled_emails: Mapped[List["ScheduledEmail"]] = relationship("ScheduledEmail", back_populates="user", cascade="all, delete-orphan")
    knowledge_collections: Mapped[List["KnowledgeCollection"]] = relationship("KnowledgeCollection", back_populates="user", cascade="all, delete-orphan")
    knowledge_sources: Mapped[List["KnowledgeSource"]] = relationship("KnowledgeSource", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="workspaces")
    notes: Mapped[List["Note"]] = relationship("Note", back_populates="workspace", cascade="all, delete-orphan")

class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="completed")
    workspace_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="notes")
    workspace: Mapped[Optional["Workspace"]] = relationship("Workspace", back_populates="notes")
    recordings: Mapped[List["Recording"]] = relationship("Recording", back_populates="note", cascade="all, delete-orphan")
    transcript: Mapped[Optional["Transcript"]] = relationship("Transcript", back_populates="note", cascade="all, delete-orphan")
    summaries: Mapped[List["StructuredSummary"]] = relationship("StructuredSummary", back_populates="note", cascade="all, delete-orphan")
    tags: Mapped[List["Tag"]] = relationship("Tag", back_populates="note", cascade="all, delete-orphan")
    meeting_minutes: Mapped[Optional["MeetingMinutes"]] = relationship("MeetingMinutes", back_populates="note", cascade="all, delete-orphan", uselist=False)
    embedding: Mapped[Optional["NoteEmbedding"]] = relationship("NoteEmbedding", back_populates="note", cascade="all, delete-orphan", uselist=False)
    scheduled_emails: Mapped[List["ScheduledEmail"]] = relationship("ScheduledEmail", back_populates="note", cascade="all, delete-orphan")
    enhancements: Mapped[List["NoteEnhancement"]] = relationship("NoteEnhancement", back_populates="note", cascade="all, delete-orphan")
    knowledge_sources: Mapped[List["KnowledgeSource"]] = relationship("KnowledgeSource", back_populates="note", cascade="all, delete-orphan")


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    local_uri: Mapped[str] = mapped_column(String, nullable=False)
    is_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="recordings")

class Transcript(Base):
    __tablename__ = "transcripts"

    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="transcript")

class StructuredSummary(Base):
    """AI-generated structured summary with provider metadata."""
    __tablename__ = "structured_summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_type: Mapped[str] = mapped_column(String, nullable=False)  # executive|detailed|bullet|action_items|follow_ups
    structured_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    provider: Mapped[str] = mapped_column(String, nullable=False)  # openai|anthropic|gemini
    model: Mapped[str] = mapped_column(String, nullable=False)  # actual model name used
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="summaries")

class Tag(Base):
    __tablename__ = "tags"

    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="tags")

class MeetingMinutes(Base):
    __tablename__ = "meeting_minutes"

    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    agenda: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of strings
    discussion_points: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of objects
    decisions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of strings
    risks: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of strings
    action_items: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of objects (task, owner, due_date)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="meeting_minutes")

class DeletedRecord(Base):
    __tablename__ = "deleted_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    record_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NoteEmbedding(Base):
    __tablename__ = "note_embeddings"

    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True)
    note_vector: Mapped[Optional[List[float]]] = mapped_column(SafeVector(768), nullable=True)
    transcript_vector: Mapped[Optional[List[float]]] = mapped_column(SafeVector(768), nullable=True)
    summary_vector: Mapped[Optional[List[float]]] = mapped_column(SafeVector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="embedding")

class ScheduledEmail(Base):
    __tablename__ = "scheduled_emails"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    email_type: Mapped[str] = mapped_column(String, nullable=False)  # transcript|summary|minutes|all
    provider: Mapped[str] = mapped_column(String, default="smtp")  # smtp|gmail
    include_transcript: Mapped[bool] = mapped_column(Boolean, default=True)
    include_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    include_minutes: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|sent|failed
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="scheduled_emails")
    user: Mapped["User"] = relationship("User", back_populates="scheduled_emails")

class NoteEnhancement(Base):
    __tablename__ = "note_enhancements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id: Mapped[str] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    enhancement_type: Mapped[str] = mapped_column(String, nullable=False)  # improved|professional|blog|executive_report|email|project_update
    structured_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string containing structured output
    provider: Mapped[str] = mapped_column(String, nullable=False)  # openai|anthropic|gemini
    model: Mapped[str] = mapped_column(String, nullable=False)  # model name
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped["Note"] = relationship("Note", back_populates="enhancements")


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="knowledge_collections")
    sources: Mapped[List["KnowledgeSource"]] = relationship("KnowledgeSource", back_populates="collection")


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # voice_note|meeting|pdf|docx|markdown|text|email|attachment|project|client|person
    file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("knowledge_collections.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    note: Mapped[Optional["Note"]] = relationship("Note", back_populates="knowledge_sources")
    user: Mapped["User"] = relationship("User", back_populates="knowledge_sources")
    collection: Mapped[Optional["KnowledgeCollection"]] = relationship("KnowledgeCollection", back_populates="sources")
    chunks: Mapped[List["KnowledgeChunk"]] = relationship("KnowledgeChunk", back_populates="source", cascade="all, delete-orphan")
    tags: Mapped[List["KnowledgeTag"]] = relationship("KnowledgeTag", back_populates="source", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["KnowledgeSource"] = relationship("KnowledgeSource", back_populates="chunks")
    embedding: Mapped[Optional["KnowledgeEmbedding"]] = relationship("KnowledgeEmbedding", back_populates="chunk", cascade="all, delete-orphan", uselist=False)


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"

    chunk_id: Mapped[str] = mapped_column(String, ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), primary_key=True)
    vector: Mapped[List[float]] = mapped_column(SafeVector(768), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chunk: Mapped["KnowledgeChunk"] = relationship("KnowledgeChunk", back_populates="embedding")


class KnowledgeRelationship(Base):
    __tablename__ = "knowledge_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    target_source_id: Mapped[str] = mapped_column(String, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)  # references|discusses|follows_up|member_of
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["KnowledgeSource"] = relationship("KnowledgeSource", foreign_keys=[source_id])
    target_source: Mapped["KnowledgeSource"] = relationship("KnowledgeSource", foreign_keys=[target_source_id])


class KnowledgeTag(Base):
    __tablename__ = "knowledge_tags"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    tag: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source: Mapped["KnowledgeSource"] = relationship("KnowledgeSource", back_populates="tags")




