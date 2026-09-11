"""calibracion del sensor de humedad de suelo por dispositivo

Revision ID: d1f4a7c39e6b
Revises: c8b4e29a17d3
Create Date: 2026-09-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f4a7c39e6b'
down_revision: Union[str, None] = 'c8b4e29a17d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default = las mismas constantes SOIL_DRY/SOIL_WET que el
    # firmware ya usaba a mano - anadir la columna no cambia nada hasta
    # que se recalibra de verdad desde la app (ver POST
    # /devices/{id}/calibrate). Por dispositivo, no por tipo de planta:
    # es una propiedad fisica del sensor/sustrato, no de la especie.
    op.add_column('devices', sa.Column('soil_dry_raw', sa.Integer(), server_default='2482', nullable=False))
    op.add_column('devices', sa.Column('soil_wet_raw', sa.Integer(), server_default='905', nullable=False))


def downgrade() -> None:
    op.drop_column('devices', 'soil_wet_raw')
    op.drop_column('devices', 'soil_dry_raw')
