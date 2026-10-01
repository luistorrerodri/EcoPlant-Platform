"""quita los nombres cientificos del catalogo, solo nombre comun

Revision ID: d8f4b61a93ce
Revises: c3a7e9f12b5d
Create Date: 2026-10-01 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f4b61a93ce'
down_revision: Union[str, None] = 'c3a7e9f12b5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (slug, nombre_anterior, nombre_nuevo) - solo para el downgrade, que
# revierte a lo que habia exactamente.
NOMBRES = [
    ('potos', 'Potos (Epipremnum)', 'Potos'),
    ('ficus-lyrata', 'Ficus lyrata (higuera hoja de violín)', 'Higuera hoja de violín'),
    ('pachira-aquatica', 'Pachira aquatica (árbol del dinero)', 'Árbol del dinero'),
    ('ficus-elastica', 'Ficus elastica (árbol del caucho)', 'Árbol del caucho'),
    ('pata-elefante', 'Beaucarnea recurvata (pata de elefante)', 'Pata de elefante'),
    ('tronco-brasil', 'Dracaena fragrans (tronco de Brasil)', 'Tronco de Brasil'),
    ('cheflera', 'Schefflera arboricola (cheflera)', 'Cheflera'),
    ('aralia', 'Polyscias fruticosa (aralia de interior)', 'Aralia de interior'),
    ('palmera-areca', 'Dypsis lutescens (palmera areca)', 'Palmera areca'),
    ('palmera-salon', 'Chamaedorea elegans (palmera de salón)', 'Palmera de salón'),
    ('palmera-kentia', 'Howea forsteriana (palmera kentia)', 'Palmera kentia'),
    ('palmera-fortuna', 'Rhapis excelsa (palmera de la fortuna)', 'Palmera de la fortuna'),
    ('lirio-paz', 'Spathiphyllum (lirio de la paz)', 'Lirio de la paz'),
    ('calathea', 'Calathea makoyana (planta pavo real)', 'Planta pavo real'),
    ('planta-zz', 'Zamioculcas zamiifolia (planta ZZ)', 'Planta ZZ'),
    ('aglaonema', 'Aglaonema commutatum', 'Aglaonema'),
    ('alocasia', 'Alocasia amazonica (oreja de elefante)', 'Oreja de elefante'),
    ('pilistra', 'Aspidistra elatior (pilistra)', 'Pilistra'),
    ('cinta', 'Chlorophytum comosum (cinta o malamadre)', 'Cinta'),
    ('hiedra', 'Hedera helix (hiedra de interior)', 'Hiedra de interior'),
    ('filodendro', 'Philodendron hederaceum (hoja de corazón)', 'Filodendro'),
    ('amor-hombre', 'Tradescantia zebrina (amor de hombre)', 'Amor de hombre'),
    ('cadena-corazones', 'Ceropegia woodii (cadena de corazones)', 'Cadena de corazones'),
    ('lengua-suegra', 'Sansevieria trifasciata (lengua de suegra)', 'Lengua de suegra'),
    ('cacto-navidad', 'Schlumbergera (cacto de Navidad)', 'Cacto de Navidad'),
]


def upgrade() -> None:
    # Pedido por Luis al revisar el catalogo en la app: el nombre cientifico
    # ("Ficus lyrata", "Beaucarnea recurvata"...) no aporta nada al usuario
    # normal y es mala UX - un nombre impronunciable que no se entiende
    # hasta leer el resto. Se deja solo el nombre comun ("de la calle").
    plant_types = sa.table('plant_types', sa.column('slug', sa.String()), sa.column('name', sa.String()))
    conn = op.get_bind()
    for slug, _antes, despues in NOMBRES:
        conn.execute(plant_types.update().where(plant_types.c.slug == slug).values(name=despues))


def downgrade() -> None:
    plant_types = sa.table('plant_types', sa.column('slug', sa.String()), sa.column('name', sa.String()))
    conn = op.get_bind()
    for slug, antes, _despues in NOMBRES:
        conn.execute(plant_types.update().where(plant_types.c.slug == slug).values(name=antes))
