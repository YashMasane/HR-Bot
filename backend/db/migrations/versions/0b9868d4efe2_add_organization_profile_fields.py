"""add organization profile fields

Revision ID: 0b9868d4efe2
Revises: 5509aff24a37
Create Date: 2026-09-13 12:47:27.462190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0b9868d4efe2'
down_revision: Union[str, Sequence[str], None] = '5509aff24a37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# op.add_column() with sa.Enum(...) does NOT create the backing Postgres
# type on its own - that only happens automatically as a side effect of
# create_table(). Standalone add_column needs the CREATE TYPE issued
# explicitly first, hence these three ENUM objects.
company_type_enum = postgresql.ENUM(
    'service_based', 'product_based', 'hybrid', name='company_type'
)
industry_enum = postgresql.ENUM(
    'it_software', 'finance_banking', 'healthcare', 'education', 'retail_ecommerce',
    'manufacturing', 'real_estate', 'hospitality_travel', 'media_entertainment',
    'telecommunications', 'logistics_transportation', 'construction', 'energy_utilities',
    'agriculture', 'government_public_sector', 'non_profit', 'consulting', 'legal', 'other',
    name='industry',
)
company_size_enum = postgresql.ENUM(
    '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+', name='company_size'
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    company_type_enum.create(bind, checkfirst=True)
    industry_enum.create(bind, checkfirst=True)
    company_size_enum.create(bind, checkfirst=True)

    op.add_column('organizations', sa.Column('company_type', company_type_enum, nullable=False))
    op.add_column('organizations', sa.Column('industry', industry_enum, nullable=False))
    op.add_column('organizations', sa.Column('company_size', company_size_enum, nullable=True))
    op.add_column('organizations', sa.Column('website', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('headquarters_location', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('organizations', sa.Column('logo_url', sa.String(length=500), nullable=True))
    op.add_column('organizations', sa.Column('contact_phone', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('organizations', 'contact_phone')
    op.drop_column('organizations', 'logo_url')
    op.drop_column('organizations', 'description')
    op.drop_column('organizations', 'headquarters_location')
    op.drop_column('organizations', 'website')
    op.drop_column('organizations', 'company_size')
    op.drop_column('organizations', 'industry')
    op.drop_column('organizations', 'company_type')

    bind = op.get_bind()
    company_size_enum.drop(bind, checkfirst=True)
    industry_enum.drop(bind, checkfirst=True)
    company_type_enum.drop(bind, checkfirst=True)
