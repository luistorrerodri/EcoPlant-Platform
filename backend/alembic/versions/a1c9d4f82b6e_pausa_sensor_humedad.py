"""pausa temporal del sensor de humedad en devices

Revision ID: a1c9d4f82b6e
Revises: f3b8c2e17a4d
Create Date: 2026-10-01 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9d4f82b6e'
down_revision: Union[str, None] = 'f3b8c2e17a4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = sin pausar (el valor por defecto, y el de todos los
    # dispositivos existentes). Mientras NOW() < sensor_pausado_hasta,
    # Node-RED no evalua riego automatico para ese dispositivo - ver
    # GET /api/internal/device-configs. Autoexpira por timestamp, sin
    # necesitar ningun scheduler.
    op.add_column('devices', sa.Column('sensor_pausado_hasta', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('devices', 'sensor_pausado_hasta')
