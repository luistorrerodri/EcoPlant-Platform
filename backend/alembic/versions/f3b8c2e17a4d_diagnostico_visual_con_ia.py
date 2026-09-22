"""diagnostico visual de la planta con IA (foto + comparacion)

Revision ID: f3b8c2e17a4d
Revises: d1f4a7c39e6b
Create Date: 2026-09-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b8c2e17a4d'
down_revision: Union[str, None] = 'd1f4a7c39e6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Una fila por dispositivo (device_id como PK, no un id propio con
    # historico creciente) - se sobreescribe con cada foto nueva, no se
    # acumula. La foto vive en la propia fila (bytea) para poder
    # comparar la nueva contra la anterior antes de descartarla.
    op.create_table(
        'plant_photo_diagnoses',
        sa.Column('device_id', sa.String(length=100), nullable=False),
        sa.Column('photo', sa.LargeBinary(), nullable=False),
        sa.Column('photo_content_type', sa.String(length=50), nullable=False),
        sa.Column('verdict', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.device_id']),
        sa.PrimaryKeyConstraint('device_id'),
    )


def downgrade() -> None:
    op.drop_table('plant_photo_diagnoses')
