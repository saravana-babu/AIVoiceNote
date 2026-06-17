"""optimize for production

Revision ID: 2a3b4c5d6e7f
Revises: 23cf72707bdb
Create Date: 2026-06-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a3b4c5d6e7f'
down_revision: Union[str, Sequence[str], None] = '23cf72707bdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Enable pgvector extension if we are on PostgreSQL
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Downsize vector columns from 1536 to 768 dimensions for Gemini embeddings
        op.execute("ALTER TABLE note_embeddings ALTER COLUMN note_vector TYPE vector(768)")
        op.execute("ALTER TABLE note_embeddings ALTER COLUMN transcript_vector TYPE vector(768)")
        op.execute("ALTER TABLE note_embeddings ALTER COLUMN summary_vector TYPE vector(768)")
        op.execute("ALTER TABLE knowledge_embeddings ALTER COLUMN vector TYPE vector(768)")

        # Create HNSW vector search indexes for optimized VPS performance
        op.execute("CREATE INDEX IF NOT EXISTS idx_note_embeddings_note_vector_hnsw ON note_embeddings USING hnsw (note_vector vector_cosine_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_note_embeddings_transcript_vector_hnsw ON note_embeddings USING hnsw (transcript_vector vector_cosine_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_note_embeddings_summary_vector_hnsw ON note_embeddings USING hnsw (summary_vector vector_cosine_ops)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_vector_hnsw ON knowledge_embeddings USING hnsw (vector vector_cosine_ops)")

        # Create functional GIN indexes for fast full-text/transcript searches
        op.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_text_gin ON transcripts USING gin (to_tsvector('english', text))")
        op.execute("CREATE INDEX IF NOT EXISTS idx_notes_title_gin ON notes USING gin (to_tsvector('english', title))")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Drop indexes
        op.execute("DROP INDEX IF EXISTS idx_note_embeddings_note_vector_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_note_embeddings_transcript_vector_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_note_embeddings_summary_vector_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_knowledge_embeddings_vector_hnsw")
        op.execute("DROP INDEX IF EXISTS idx_transcripts_text_gin")
        op.execute("DROP INDEX IF EXISTS idx_notes_title_gin")

        # Revert vector columns to 1536 dimensions
        op.execute("ALTER TABLE note_embeddings ALTER COLUMN note_vector TYPE vector(1536)")
        op.execute("ALTER TABLE note_embeddings ALTER COLUMN transcript_vector TYPE vector(1536)")
        op.execute("ALTER TABLE note_embeddings ALTER COLUMN summary_vector TYPE vector(1536)")
        op.execute("ALTER TABLE knowledge_embeddings ALTER COLUMN vector TYPE vector(1536)")
