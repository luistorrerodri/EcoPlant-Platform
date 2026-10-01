"""mas categorias y plantas comunes de interior en el catalogo

Revision ID: c3a7e9f12b5d
Revises: b7e3f1a9c2d4
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a7e9f12b5d'
down_revision: Union[str, None] = 'b7e3f1a9c2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # El catalogo crecio de 15 a 42 tipos - "planta"/"arbol" se queda corto
    # para un selector usable. Se reclasifica en 6 categorias (las usa
    # Luis mismo al pedir esta ampliacion): planta (general/huerto),
    # hoja_grande, colgante, crasa, palmera, arbol. Solo cambia el
    # agrupado del selector de la app - ningun calculo de riego lee esta
    # columna.
    op.execute("UPDATE plant_types SET category = 'crasa' WHERE slug = 'suculenta-cactus'")

    # Mismo metodo que el resto del catalogo: default_tasa_secado_max_pct_h
    # = (humedad_max - humedad_min) / horas tipicas entre riegos segun
    # guias de cultivo en maceta reales para cada especie - heuristicas de
    # arranque, no datos medidos, a ajustar con uso real. Se omiten
    # deliberadamente Monstera, Poto y Limonero por ya estar en el
    # catalogo (desde el principio y desde ayer respectivamente).
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
        # ---------------------------------------------- arboles y arbustos
        {'id': '2f4b6f0a-0000-4000-8000-000000000016', 'slug': 'ficus-lyrata', 'name': 'Ficus lyrata (higuera hoja de violín)', 'category': 'arbol',
         'default_humedad_min': 35, 'default_humedad_max': 58, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 10000, 'default_tasa_secado_max_pct_h': 0.24},
        {'id': '2f4b6f0a-0000-4000-8000-000000000017', 'slug': 'pachira-aquatica', 'name': 'Pachira aquatica (árbol del dinero)', 'category': 'arbol',
         'default_humedad_min': 38, 'default_humedad_max': 60, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 9000, 'default_tasa_secado_max_pct_h': 0.23},
        {'id': '2f4b6f0a-0000-4000-8000-000000000018', 'slug': 'ficus-elastica', 'name': 'Ficus elastica (árbol del caucho)', 'category': 'arbol',
         'default_humedad_min': 30, 'default_humedad_max': 55, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 9000, 'default_tasa_secado_max_pct_h': 0.21},
        {'id': '2f4b6f0a-0000-4000-8000-000000000019', 'slug': 'pata-elefante', 'name': 'Beaucarnea recurvata (pata de elefante)', 'category': 'arbol',
         'default_humedad_min': 15, 'default_humedad_max': 35, 'default_hora_inicio': 9, 'default_hora_fin': 19, 'default_duracion_riego_ms': 5000, 'default_tasa_secado_max_pct_h': 0.12},
        {'id': '2f4b6f0a-0000-4000-8000-000000000020', 'slug': 'ficus-benjamina', 'name': 'Ficus benjamina', 'category': 'arbol',
         'default_humedad_min': 35, 'default_humedad_max': 58, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 9000, 'default_tasa_secado_max_pct_h': 0.27},
        {'id': '2f4b6f0a-0000-4000-8000-000000000021', 'slug': 'tronco-brasil', 'name': 'Dracaena fragrans (tronco de Brasil)', 'category': 'arbol',
         'default_humedad_min': 28, 'default_humedad_max': 52, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.20},
        {'id': '2f4b6f0a-0000-4000-8000-000000000022', 'slug': 'cheflera', 'name': 'Schefflera arboricola (cheflera)', 'category': 'arbol',
         'default_humedad_min': 32, 'default_humedad_max': 55, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.24},
        {'id': '2f4b6f0a-0000-4000-8000-000000000023', 'slug': 'aralia', 'name': 'Polyscias fruticosa (aralia de interior)', 'category': 'arbol',
         'default_humedad_min': 38, 'default_humedad_max': 60, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 7000, 'default_tasa_secado_max_pct_h': 0.26},
        {'id': '2f4b6f0a-0000-4000-8000-000000000024', 'slug': 'yuca', 'name': 'Yucca elephantipes', 'category': 'arbol',
         'default_humedad_min': 18, 'default_humedad_max': 40, 'default_hora_inicio': 9, 'default_hora_fin': 19, 'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.13},
        # --------------------------------------------------------- palmeras
        {'id': '2f4b6f0a-0000-4000-8000-000000000025', 'slug': 'palmera-areca', 'name': 'Dypsis lutescens (palmera areca)', 'category': 'palmera',
         'default_humedad_min': 42, 'default_humedad_max': 65, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 9000, 'default_tasa_secado_max_pct_h': 0.32},
        {'id': '2f4b6f0a-0000-4000-8000-000000000026', 'slug': 'palmera-salon', 'name': 'Chamaedorea elegans (palmera de salón)', 'category': 'palmera',
         'default_humedad_min': 35, 'default_humedad_max': 58, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 6000, 'default_tasa_secado_max_pct_h': 0.24},
        {'id': '2f4b6f0a-0000-4000-8000-000000000027', 'slug': 'palmera-kentia', 'name': 'Howea forsteriana (palmera kentia)', 'category': 'palmera',
         'default_humedad_min': 32, 'default_humedad_max': 55, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.19},
        {'id': '2f4b6f0a-0000-4000-8000-000000000028', 'slug': 'palmera-fortuna', 'name': 'Rhapis excelsa (palmera de la fortuna)', 'category': 'palmera',
         'default_humedad_min': 38, 'default_humedad_max': 60, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.23},
        # ------------------------------------------- hoja grande y frondosas
        {'id': '2f4b6f0a-0000-4000-8000-000000000029', 'slug': 'lirio-paz', 'name': 'Spathiphyllum (lirio de la paz)', 'category': 'hoja_grande',
         'default_humedad_min': 45, 'default_humedad_max': 68, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 8000, 'default_tasa_secado_max_pct_h': 0.32},
        {'id': '2f4b6f0a-0000-4000-8000-000000000030', 'slug': 'calathea', 'name': 'Calathea makoyana (planta pavo real)', 'category': 'hoja_grande',
         'default_humedad_min': 48, 'default_humedad_max': 70, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 6000, 'default_tasa_secado_max_pct_h': 0.37},
        {'id': '2f4b6f0a-0000-4000-8000-000000000031', 'slug': 'planta-zz', 'name': 'Zamioculcas zamiifolia (planta ZZ)', 'category': 'hoja_grande',
         'default_humedad_min': 15, 'default_humedad_max': 38, 'default_hora_inicio': 9, 'default_hora_fin': 19, 'default_duracion_riego_ms': 5000, 'default_tasa_secado_max_pct_h': 0.14},
        {'id': '2f4b6f0a-0000-4000-8000-000000000032', 'slug': 'aglaonema', 'name': 'Aglaonema commutatum', 'category': 'hoja_grande',
         'default_humedad_min': 35, 'default_humedad_max': 58, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 6000, 'default_tasa_secado_max_pct_h': 0.24},
        {'id': '2f4b6f0a-0000-4000-8000-000000000033', 'slug': 'alocasia', 'name': 'Alocasia amazonica (oreja de elefante)', 'category': 'hoja_grande',
         'default_humedad_min': 42, 'default_humedad_max': 65, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 6000, 'default_tasa_secado_max_pct_h': 0.32},
        {'id': '2f4b6f0a-0000-4000-8000-000000000034', 'slug': 'pilistra', 'name': 'Aspidistra elatior (pilistra)', 'category': 'hoja_grande',
         'default_humedad_min': 25, 'default_humedad_max': 50, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 7000, 'default_tasa_secado_max_pct_h': 0.17},
        # -------------------------------------------- colgantes y trepadoras
        {'id': '2f4b6f0a-0000-4000-8000-000000000035', 'slug': 'cinta', 'name': 'Chlorophytum comosum (cinta o malamadre)', 'category': 'colgante',
         'default_humedad_min': 32, 'default_humedad_max': 55, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 5000, 'default_tasa_secado_max_pct_h': 0.24},
        {'id': '2f4b6f0a-0000-4000-8000-000000000036', 'slug': 'hiedra', 'name': 'Hedera helix (hiedra de interior)', 'category': 'colgante',
         'default_humedad_min': 38, 'default_humedad_max': 60, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 5000, 'default_tasa_secado_max_pct_h': 0.26},
        {'id': '2f4b6f0a-0000-4000-8000-000000000037', 'slug': 'filodendro', 'name': 'Philodendron hederaceum (hoja de corazón)', 'category': 'colgante',
         'default_humedad_min': 30, 'default_humedad_max': 55, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 5000, 'default_tasa_secado_max_pct_h': 0.26},
        {'id': '2f4b6f0a-0000-4000-8000-000000000038', 'slug': 'amor-hombre', 'name': 'Tradescantia zebrina (amor de hombre)', 'category': 'colgante',
         'default_humedad_min': 38, 'default_humedad_max': 62, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 4000, 'default_tasa_secado_max_pct_h': 0.33},
        {'id': '2f4b6f0a-0000-4000-8000-000000000039', 'slug': 'cadena-corazones', 'name': 'Ceropegia woodii (cadena de corazones)', 'category': 'colgante',
         'default_humedad_min': 15, 'default_humedad_max': 35, 'default_hora_inicio': 9, 'default_hora_fin': 19, 'default_duracion_riego_ms': 3000, 'default_tasa_secado_max_pct_h': 0.14},
        # ----------------------------------------- crasas y cuidados minimos
        {'id': '2f4b6f0a-0000-4000-8000-000000000040', 'slug': 'lengua-suegra', 'name': 'Sansevieria trifasciata (lengua de suegra)', 'category': 'crasa',
         'default_humedad_min': 12, 'default_humedad_max': 32, 'default_hora_inicio': 9, 'default_hora_fin': 19, 'default_duracion_riego_ms': 4000, 'default_tasa_secado_max_pct_h': 0.12},
        {'id': '2f4b6f0a-0000-4000-8000-000000000041', 'slug': 'aloe-vera', 'name': 'Aloe vera', 'category': 'crasa',
         'default_humedad_min': 12, 'default_humedad_max': 30, 'default_hora_inicio': 9, 'default_hora_fin': 19, 'default_duracion_riego_ms': 3000, 'default_tasa_secado_max_pct_h': 0.11},
        {'id': '2f4b6f0a-0000-4000-8000-000000000042', 'slug': 'cacto-navidad', 'name': 'Schlumbergera (cacto de Navidad)', 'category': 'crasa',
         'default_humedad_min': 32, 'default_humedad_max': 55, 'default_hora_inicio': 8, 'default_hora_fin': 20, 'default_duracion_riego_ms': 4000, 'default_tasa_secado_max_pct_h': 0.24},
    ])


def downgrade() -> None:
    op.execute("""
        DELETE FROM plant_types WHERE slug IN (
            'ficus-lyrata', 'pachira-aquatica', 'ficus-elastica', 'pata-elefante', 'ficus-benjamina',
            'tronco-brasil', 'cheflera', 'aralia', 'yuca',
            'palmera-areca', 'palmera-salon', 'palmera-kentia', 'palmera-fortuna',
            'lirio-paz', 'calathea', 'planta-zz', 'aglaonema', 'alocasia', 'pilistra',
            'cinta', 'hiedra', 'filodendro', 'amor-hombre', 'cadena-corazones',
            'lengua-suegra', 'aloe-vera', 'cacto-navidad'
        )
    """)
    op.execute("UPDATE plant_types SET category = 'planta' WHERE slug = 'suculenta-cactus'")
