"""catalogo de tipos de planta y config de riego en devices

Revision ID: cd15063a2c75
Revises: 32dd032060ba
Create Date: 2026-09-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd15063a2c75'
down_revision: Union[str, None] = '32dd032060ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('plant_types',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('default_humedad_min', sa.Integer(), nullable=False),
    sa.Column('default_hora_inicio', sa.Integer(), nullable=False),
    sa.Column('default_hora_fin', sa.Integer(), nullable=False),
    sa.Column('default_duracion_riego_ms', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )

    op.add_column('devices', sa.Column('plant_type_id', sa.UUID(), nullable=True))
    op.add_column('devices', sa.Column('humedad_min', sa.Integer(), server_default='36', nullable=False))
    op.add_column('devices', sa.Column('hora_inicio', sa.Integer(), server_default='8', nullable=False))
    op.add_column('devices', sa.Column('hora_fin', sa.Integer(), server_default='21', nullable=False))
    op.add_column('devices', sa.Column('duracion_riego_ms', sa.Integer(), server_default='9000', nullable=False))
    op.create_foreign_key(
        'fk_devices_plant_type_id', 'devices', 'plant_types',
        ['plant_type_id'], ['id'], ondelete='SET NULL'
    )

    # Semilla del catalogo inicial. "personalizado" replica uno a uno los
    # server_default de devices.* de arriba: elegirlo desde la app no
    # cambia nada respecto al comportamiento actual en produccion. Los
    # demas valores son un punto de partida ilustrativo (especifico del
    # calibrado del sensor capacitivo de este proyecto, no un dato
    # agronomico validado), pensado para ajustarse con el uso real.
    plant_types = sa.table('plant_types',
        sa.column('id', sa.UUID()),
        sa.column('slug', sa.String()),
        sa.column('name', sa.String()),
        sa.column('default_humedad_min', sa.Integer()),
        sa.column('default_hora_inicio', sa.Integer()),
        sa.column('default_hora_fin', sa.Integer()),
        sa.column('default_duracion_riego_ms', sa.Integer()),
    )
    op.bulk_insert(plant_types, [
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000001',
            'slug': 'personalizado', 'name': 'Personalizado',
            'default_humedad_min': 36, 'default_hora_inicio': 8,
            'default_hora_fin': 21, 'default_duracion_riego_ms': 9000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000002',
            'slug': 'tomate', 'name': 'Tomate',
            'default_humedad_min': 45, 'default_hora_inicio': 7,
            'default_hora_fin': 20, 'default_duracion_riego_ms': 12000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000003',
            'slug': 'hierbas-aromaticas', 'name': 'Hierbas aromáticas',
            'default_humedad_min': 30, 'default_hora_inicio': 8,
            'default_hora_fin': 21, 'default_duracion_riego_ms': 6000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000004',
            'slug': 'hoja-verde', 'name': 'Hoja verde (lechuga, espinaca...)',
            'default_humedad_min': 50, 'default_hora_inicio': 7,
            'default_hora_fin': 20, 'default_duracion_riego_ms': 10000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000005',
            'slug': 'suculenta-cactus', 'name': 'Suculenta / cactus',
            'default_humedad_min': 15, 'default_hora_inicio': 9,
            'default_hora_fin': 19, 'default_duracion_riego_ms': 4000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000006',
            'slug': 'helecho', 'name': 'Helecho',
            'default_humedad_min': 55, 'default_hora_inicio': 8,
            'default_hora_fin': 21, 'default_duracion_riego_ms': 8000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000007',
            'slug': 'monstera', 'name': 'Monstera',
            'default_humedad_min': 40, 'default_hora_inicio': 8,
            'default_hora_fin': 20, 'default_duracion_riego_ms': 9000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000008',
            'slug': 'potos', 'name': 'Potos (Epipremnum)',
            'default_humedad_min': 25, 'default_hora_inicio': 8,
            'default_hora_fin': 20, 'default_duracion_riego_ms': 5000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000009',
            'slug': 'rosal', 'name': 'Rosal',
            'default_humedad_min': 42, 'default_hora_inicio': 7,
            'default_hora_fin': 20, 'default_duracion_riego_ms': 11000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000010',
            'slug': 'lavanda', 'name': 'Lavanda',
            'default_humedad_min': 18, 'default_hora_inicio': 9,
            'default_hora_fin': 19, 'default_duracion_riego_ms': 4000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000011',
            'slug': 'orquidea', 'name': 'Orquídea',
            'default_humedad_min': 35, 'default_hora_inicio': 8,
            'default_hora_fin': 19, 'default_duracion_riego_ms': 3000,
        },
        {
            'id': '2f4b6f0a-0000-4000-8000-000000000012',
            'slug': 'ficus', 'name': 'Ficus',
            'default_humedad_min': 38, 'default_hora_inicio': 8,
            'default_hora_fin': 20, 'default_duracion_riego_ms': 7000,
        },
    ])


def downgrade() -> None:
    op.drop_constraint('fk_devices_plant_type_id', 'devices', type_='foreignkey')
    op.drop_column('devices', 'duracion_riego_ms')
    op.drop_column('devices', 'hora_fin')
    op.drop_column('devices', 'hora_inicio')
    op.drop_column('devices', 'humedad_min')
    op.drop_column('devices', 'plant_type_id')
    op.drop_table('plant_types')
