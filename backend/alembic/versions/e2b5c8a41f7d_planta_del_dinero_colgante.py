"""anade planta del dinero (Plectranthus verticillatus), colgante

Revision ID: e2b5c8a41f7d
Revises: d8f4b61a93ce
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b5c8a41f7d'
down_revision: Union[str, None] = 'd8f4b61a93ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Distinta de "arbol-del-dinero" (Pachira aquatica, ya en el catalogo):
    # Plectranthus verticillatus comparte el mismo apodo popular en
    # castellano pero es una planta completamente distinta - de la familia
    # de la menta (Lamiaceae), de habito colgante/rastrero, no un arbol.
    # Se nombra "Planta del dinero" (no "Árbol...") para que ambas convivan
    # sin confundirse en el selector.
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
        {'id': '2f4b6f0a-0000-4000-8000-000000000043', 'slug': 'planta-dinero-colgante', 'name': 'Planta del dinero', 'category': 'colgante',
         'default_humedad_min': 35, 'default_humedad_max': 60, 'default_hora_inicio': 8, 'default_hora_fin': 20,
         'default_duracion_riego_ms': 5000, 'default_tasa_secado_max_pct_h': 0.30},
    ])


def downgrade() -> None:
    op.execute("DELETE FROM plant_types WHERE slug = 'planta-dinero-colgante'")
