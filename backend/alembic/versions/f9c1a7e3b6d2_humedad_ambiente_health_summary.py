"""humedad ambiente media en health_summaries

Revision ID: f9c1a7e3b6d2
Revises: e2b5c8a41f7d
Create Date: 2026-10-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9c1a7e3b6d2'
down_revision: Union[str, None] = 'e2b5c8a41f7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Media de humedad_ambiente en la ventana del informe. NULL para
    # dispositivos sin sensor de humedad de ambiente (p.ej. macetero01,
    # BMP280 sin higrometro) - mismo patron nullable que temp_aire_min/max,
    # nunca un 0 fabricado.
    op.add_column('health_summaries', sa.Column('humedad_ambiente_avg', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('health_summaries', 'humedad_ambiente_avg')
