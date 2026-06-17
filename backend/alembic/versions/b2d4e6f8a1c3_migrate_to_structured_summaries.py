"""migrate_to_structured_summaries

Revision ID: b2d4e6f8a1c3
Revises: a1cc5570f74e
Create Date: 2026-06-16 17:27:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2d4e6f8a1c3'
down_revision: Union[str, None] = 'a1cc5570f74e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old simple summaries table
    op.drop_table('summaries')

    # Create the new structured_summaries table
    op.create_table(
        'structured_summaries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('note_id', sa.String(), nullable=False),
        sa.Column('summary_type', sa.String(), nullable=False),
        sa.Column('structured_data', sa.Text(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completion_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_structured_summaries_note_id'), 'structured_summaries', ['note_id'], unique=False)


def downgrade() -> None:
    # Drop the structured_summaries table
    op.drop_index(op.f('ix_structured_summaries_note_id'), table_name='structured_summaries')
    op.drop_table('structured_summaries')

    # Recreate the old summaries table
    op.create_table(
        'summaries',
        sa.Column('note_id', sa.String(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('note_id'),
    )
