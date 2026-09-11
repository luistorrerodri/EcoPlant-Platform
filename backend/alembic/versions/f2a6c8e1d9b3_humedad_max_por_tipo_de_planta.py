"""humedad_max por tipo de planta y en devices

Revision ID: f2a6c8e1d9b3
Revises: e19a7d5c3b4f
Create Date: 2026-09-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a6c8e1d9b3'
down_revision: Union[str, None] = 'e19a7d5c3b4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default = 65: el mismo techo que ya tenia macetero01 con los
    # umbrales fijos antiguos (25/36/65/80) - anadir la columna no cambia
    # nada por si sola hasta que se resiembra el catalogo y/o se elige un
    # tipo de planta.
    op.add_column('plant_types', sa.Column('default_humedad_max', sa.Integer(), server_default='65', nullable=False))
    op.add_column('devices', sa.Column('humedad_max', sa.Integer(), server_default='65', nullable=False))

    # Maximos reales por tipo de planta - ver justificacion de cada valor
    # en el plan de esta iteracion. Heuristicas de arranque, pensadas
    # para ajustarse con uso real, igual que ya se documento para
    # default_humedad_min en la migracion cd15063a2c75.
    plant_types = sa.table('plant_types',
        sa.column('slug', sa.String()),
        sa.column('default_humedad_max', sa.Integer()),
    )
    maximos = {
        'personalizado': 65,
        'tomate': 70,
        'hierbas-aromaticas': 52,
        'hoja-verde': 75,
        'suculenta-cactus': 32,
        'helecho': 80,
        'monstera': 62,
        'potos': 48,
        'rosal': 66,
        'lavanda': 35,
        'orquidea': 60,
        'ficus': 60,
    }
    conn = op.get_bind()
    for slug, maximo in maximos.items():
        conn.execute(
            plant_types.update().where(plant_types.c.slug == slug).values(default_humedad_max=maximo)
        )

    # Dispositivos que ya tienen un tipo de planta asignado: se les copia
    # el maximo real de su tipo, igual que humedad_min se copio en su
    # momento. Los que no tienen tipo asignado se quedan con el 65 del
    # server_default (equivalente a "Personalizado").
    op.execute("""
        UPDATE devices
        SET humedad_max = plant_types.default_humedad_max
        FROM plant_types
        WHERE devices.plant_type_id = plant_types.id
    """)


def downgrade() -> None:
    op.drop_column('devices', 'humedad_max')
    op.drop_column('plant_types', 'default_humedad_max')
