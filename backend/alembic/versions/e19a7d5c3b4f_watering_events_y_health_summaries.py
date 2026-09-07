"""watering_events y health_summaries

Revision ID: e19a7d5c3b4f
Revises: cd15063a2c75
Create Date: 2026-09-07 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e19a7d5c3b4f'
down_revision: Union[str, None] = 'cd15063a2c75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('watering_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('device_id', sa.String(length=100), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.device_id']),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('health_summaries',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('device_id', sa.String(length=100), nullable=False),
    sa.Column('window_days', sa.Integer(), nullable=False),
    sa.Column('verdict', sa.String(length=30), nullable=False),
    sa.Column('message', sa.String(length=1000), nullable=False),
    sa.Column('pct_tiempo_bajo_minimo', sa.Float(), nullable=True),
    sa.Column('pct_tiempo_saturado', sa.Float(), nullable=True),
    sa.Column('num_riegos', sa.Integer(), nullable=True),
    sa.Column('tiempo_recuperacion_medio_h', sa.Float(), nullable=True),
    sa.Column('temp_suelo_min', sa.Float(), nullable=True),
    sa.Column('temp_suelo_max', sa.Float(), nullable=True),
    sa.Column('temp_aire_min', sa.Float(), nullable=True),
    sa.Column('temp_aire_max', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.device_id']),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('health_summaries')
    op.drop_table('watering_events')
