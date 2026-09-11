"""tasa de secado esperada por tipo de planta y metrica en health_summaries

Revision ID: c8b4e29a17d3
Revises: f2a6c8e1d9b3
Create Date: 2026-09-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b4e29a17d3'
down_revision: Union[str, None] = 'f2a6c8e1d9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Valor de referencia, no umbral de control: por eso solo vive en
    # plant_types (no hay columna equivalente en devices, ver el plan de
    # esta iteracion). server_default 0.17 = el valor de "Personalizado".
    op.add_column(
        'plant_types',
        sa.Column('default_tasa_secado_max_pct_h', sa.Float(), server_default='0.17', nullable=False),
    )

    # Metrica medida por resumen, nullable como el resto de columnas de
    # health_summaries - un resumen antiguo simplemente no la tiene.
    op.add_column('health_summaries', sa.Column('tasa_secado_pct_h', sa.Float(), nullable=True))

    # Ritmos "normales" estimados por tipo: (humedad_max - humedad_min de
    # cada tipo) / (intervalo de riego tipico segun guias de horticultura
    # reales, en horas). Heuristicas de arranque razonadas, no medidas -
    # ver el plan de esta iteracion para las fuentes y el detalle del
    # calculo por tipo. A ajustar con datos reales cuando haya histórico
    # suficiente, mismo criterio que default_humedad_max (f2a6c8e1d9b3).
    plant_types = sa.table('plant_types',
        sa.column('slug', sa.String()),
        sa.column('default_tasa_secado_max_pct_h', sa.Float()),
    )
    tasas = {
        'personalizado': 0.17,
        'tomate': 0.50,
        'hierbas-aromaticas': 0.35,
        'hoja-verde': 0.15,
        'suculenta-cactus': 0.06,
        'helecho': 0.20,
        'monstera': 0.12,
        'potos': 0.10,
        'rosal': 0.14,
        'lavanda': 0.06,
        'orquidea': 0.15,
        'ficus': 0.13,
    }
    conn = op.get_bind()
    for slug, tasa in tasas.items():
        conn.execute(
            plant_types.update().where(plant_types.c.slug == slug).values(default_tasa_secado_max_pct_h=tasa)
        )


def downgrade() -> None:
    op.drop_column('health_summaries', 'tasa_secado_pct_h')
    op.drop_column('plant_types', 'default_tasa_secado_max_pct_h')
