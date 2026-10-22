"""Accounts, server sessions, and dated coach availability."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('contact_method', sa.String(16), nullable=False),
        sa.Column('contact', sa.String(80), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('requested_role', sa.String(8), nullable=False),
        sa.Column('coach_approved', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('contact_method', 'contact', name='uq_user_contact'),
        sa.CheckConstraint("requested_role IN ('player','coach','both')", name='ck_user_role'),
        sa.CheckConstraint("contact_method IN ('instagram','discord','phone')", name='ck_contact_method'))
    op.create_table('login_sessions',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('csrf_token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_login_sessions_user_id', 'login_sessions', ['user_id'])
    op.create_index('ix_login_sessions_expires_at', 'login_sessions', ['expires_at'])
    op.create_table('availability',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('coach_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('ends_at > starts_at', name='ck_availability_interval'))
    op.create_index('ix_availability_coach_start', 'availability', ['coach_id', 'starts_at'])


def downgrade():
    op.drop_table('availability')
    op.drop_table('login_sessions')
    op.drop_table('users')
