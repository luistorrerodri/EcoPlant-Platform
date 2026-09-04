"""interior/exterior en devices

Revision ID: 8f25444aa69f
Revises: cd15063a2c75
Create Date: 2026-09-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f25444aa69f'
down_revision: Union[str, None] = 'cd15063a2c75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('devices', sa.Column('environment', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('devices', 'environment')
