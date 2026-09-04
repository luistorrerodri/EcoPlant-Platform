"""lat/long en locations

Revision ID: 7c32955724a5
Revises: 8f25444aa69f
Create Date: 2026-09-04 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c32955724a5'
down_revision: Union[str, None] = '8f25444aa69f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('locations', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('locations', sa.Column('longitude', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('locations', 'longitude')
    op.drop_column('locations', 'latitude')
