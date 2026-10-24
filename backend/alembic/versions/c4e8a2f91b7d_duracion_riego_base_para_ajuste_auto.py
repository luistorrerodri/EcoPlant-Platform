"""duracion_riego_base_ms para el ajuste automatico de riego

Revision ID: c4e8a2f91b7d
Revises: f9c1a7e3b6d2
Create Date: 2026-10-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a2f91b7d'
down_revision: Union[str, None] = 'f9c1a7e3b6d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default a 9000 para dispositivos nuevos (coincide con el de
    # duracion_riego_ms), pero los dispositivos EXISTENTES deben arrancar
    # con su propio duracion_riego_ms actual como base, no con 9000 a
    # ciegas - si no, un dispositivo que ya tenia una duracion distinta
    # (por tipo de planta o ajuste manual) perderia ese punto de
    # referencia real al aplicar esta migracion.
    op.add_column('devices', sa.Column('duracion_riego_base_ms', sa.Integer(), nullable=True))
    op.execute('UPDATE devices SET duracion_riego_base_ms = duracion_riego_ms')
    op.alter_column('devices', 'duracion_riego_base_ms', nullable=False, server_default='9000')


def downgrade() -> None:
    op.drop_column('devices', 'duracion_riego_base_ms')
