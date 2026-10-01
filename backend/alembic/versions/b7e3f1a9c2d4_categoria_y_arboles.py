"""categoria (planta/arbol) en plant_types y tres arboles de maceta nuevos

Revision ID: b7e3f1a9c2d4
Revises: a1c9d4f82b6e
Create Date: 2026-10-01 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3f1a9c2d4'
down_revision: Union[str, None] = 'a1c9d4f82b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default 'planta': los 12 tipos existentes son todos plantas,
    # no arboles - anadir la columna no les cambia nada. Solo agrupa el
    # selector de la app (submenu "Plantas"/"Arboles"), no afecta a ningun
    # calculo de riego.
    op.add_column('plant_types', sa.Column('category', sa.String(length=20), server_default='planta', nullable=False))

    # Tres arboles pensados para maceta/version enana en interior-exterior,
    # no para plantacion en tierra. Mismo metodo que el resto del catalogo:
    # default_tasa_secado_max_pct_h = (humedad_max - humedad_min) / horas
    # tipicas entre riegos segun guias de cultivo en maceta reales -
    # heuristicas de arranque, no datos medidos, a ajustar con uso real.
    #
    # Aguacate: muy sensible tanto a sequia como a encharcamiento (raiz
    # propensa a podrirse) - rango medio-alto, riego a fondo cada ~2.5
    # dias en crecimiento activo.
    # Manzano (enano): similar al rosal en exigencia de humedad constante
    # durante la fructificacion, algo mas tolerante a la sequia que el
    # aguacate - cada ~3-4 dias.
    # Limonero: los citricos prefieren secarse mas entre riegos que las
    # plantas de hoja tropicales, muy sensible a encharcamiento (amarillea
    # y pudre raiz) - cada ~5 dias.
    plant_types = sa.table('plant_types',
        sa.column('id', sa.UUID()),
        sa.column('slug', sa.String()),
        sa.column('name', sa.String()),
        sa.column('category', sa.String()),
        sa.column('default_humedad_min', sa.Integer()),
        sa.column('default_humedad_max', sa.Integer()),
        sa.column('default_hora_inicio', sa.Integer()),
        sa.column('default_hora_fin', sa.Integer()),
        sa.column('default_duracion_riego_ms', sa.Integer()),
        sa.column('default_tasa_secado_max_pct_h', sa.Float()),
    )
    op.bulk_insert(plant_types, [
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000013',
            'slug': 'aguacate', 'name': 'Aguacate', 'category': 'arbol',
            'default_humedad_min': 42, 'default_humedad_max': 62,
            'default_hora_inicio': 7, 'default_hora_fin': 20,
            'default_duracion_riego_ms': 11000, 'default_tasa_secado_max_pct_h': 0.33,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000014',
            'slug': 'manzano', 'name': 'Manzano (enano)', 'category': 'arbol',
            'default_humedad_min': 40, 'default_humedad_max': 64,
            'default_hora_inicio': 7, 'default_hora_fin': 20,
            'default_duracion_riego_ms': 10000, 'default_tasa_secado_max_pct_h': 0.30,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000015',
            'slug': 'limonero', 'name': 'Limonero', 'category': 'arbol',
            'default_humedad_min': 30, 'default_humedad_max': 55,
            'default_hora_inicio': 8, 'default_hora_fin': 20,
            'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.21,
        },
    ])


def downgrade() -> None:
    op.execute("DELETE FROM plant_types WHERE slug IN ('aguacate', 'manzano', 'limonero')")
    op.drop_column('plant_types', 'category')
