"""varios tokens de push por cuenta (tabla push_tokens)

Revision ID: e5b9c3a72d18
Revises: a8f2d6b41c93
Create Date: 2026-10-26 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5b9c3a72d18'
down_revision: Union[str, None] = 'a8f2d6b41c93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'push_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_push_tokens_user_id', 'push_tokens', ['user_id'])

    # El token unico que ya tenia cada usuario pasa a ser su primera fila
    # (gen_random_uuid() es nativo desde PostgreSQL 13).
    op.execute(
        "INSERT INTO push_tokens (id, user_id, token) "
        "SELECT gen_random_uuid(), id, push_token FROM users WHERE push_token IS NOT NULL"
    )
    op.drop_column('users', 'push_token')


def downgrade() -> None:
    op.add_column('users', sa.Column('push_token', sa.String(length=255), nullable=True))
    # Con varios tokens por usuario solo cabe uno en la columna antigua:
    # se conserva el mas reciente.
    op.execute(
        "UPDATE users SET push_token = ("
        "SELECT token FROM push_tokens WHERE push_tokens.user_id = users.id "
        "ORDER BY created_at DESC LIMIT 1)"
    )
    op.drop_index('ix_push_tokens_user_id', table_name='push_tokens')
    op.drop_table('push_tokens')
