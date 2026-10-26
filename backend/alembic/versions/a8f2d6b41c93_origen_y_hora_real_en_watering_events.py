"""origen del riego y corregir la hora guardada en watering_events

Revision ID: a8f2d6b41c93
Revises: c4e8a2f91b7d
Create Date: 2026-10-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f2d6b41c93'
down_revision: Union[str, None] = 'c4e8a2f91b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL para los riegos que ya existen: no se puede saber a posteriori
    # si fueron manuales o automaticos, y no se inventa.
    op.add_column('watering_events', sa.Column('origen', sa.String(length=20), nullable=True))

    # Los timestamps ya guardados son la hora de pared de Madrid
    # etiquetada como UTC (el RTC del ESP32 guarda hora local pero
    # unixtime() la presenta como UTC) - ver docs/troubleshooting.md #39.
    # timestamptz AT TIME ZONE 'UTC' devuelve esa hora de pared sin zona;
    # interpretada como hora de Madrid da el instante real. Una sola vez,
    # junto con el cambio de codigo que ya guarda bien los nuevos.
    op.execute(
        "UPDATE watering_events "
        "SET timestamp = ((timestamp AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Madrid')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE watering_events "
        "SET timestamp = ((timestamp AT TIME ZONE 'Europe/Madrid') AT TIME ZONE 'UTC')"
    )
    op.drop_column('watering_events', 'origen')
