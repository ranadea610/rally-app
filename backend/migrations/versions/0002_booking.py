"""Training catalog, equipment, and conflict-protected reservations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist')
    op.create_table('training_types', sa.Column('id', sa.String(32), primary_key=True), sa.Column('name', sa.String(80), nullable=False))
    op.create_table('equipment', sa.Column('id', sa.String(32), primary_key=True), sa.Column('name', sa.String(80), nullable=False))
    op.create_table('training_requirements',
        sa.Column('training_type_id', sa.String(32), sa.ForeignKey('training_types.id'), primary_key=True),
        sa.Column('equipment_id', sa.String(32), sa.ForeignKey('equipment.id'), primary_key=True))
    op.create_table('reservations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('coach_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('player_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('availability_id', sa.String(36), sa.ForeignKey('availability.id', ondelete='SET NULL'), nullable=True),
        sa.Column('training_type_id', sa.String(32), sa.ForeignKey('training_types.id'), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(12), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active','canceled')", name='ck_reservation_status'),
        sa.CheckConstraint("ends_at = starts_at + interval '15 minutes'", name='ck_reservation_duration'),
        sa.CheckConstraint('coach_id <> player_id', name='ck_reservation_not_self'),
        ExcludeConstraint(('coach_id', '='), (sa.func.tstzrange(sa.text('starts_at'), sa.text('ends_at'), '[)'), '&&'), where=sa.text("status = 'active'"), name='ex_reservation_coach', using='gist'),
        ExcludeConstraint(('player_id', '='), (sa.func.tstzrange(sa.text('starts_at'), sa.text('ends_at'), '[)'), '&&'), where=sa.text("status = 'active'"), name='ex_reservation_player', using='gist'))
    op.create_table('equipment_allocations',
        sa.Column('reservation_id', sa.String(36), sa.ForeignKey('reservations.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('equipment_id', sa.String(32), sa.ForeignKey('equipment.id'), primary_key=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.CheckConstraint('ends_at > starts_at', name='ck_allocation_interval'),
        ExcludeConstraint(('equipment_id', '='), (sa.func.tstzrange(sa.text('starts_at'), sa.text('ends_at'), '[)'), '&&'), where=sa.text('active'), name='ex_allocation_equipment', using='gist'))
    training = sa.table('training_types', sa.column('id'), sa.column('name'))
    op.bulk_insert(training, [
        {'id':'rally', 'name':'Rally (recommended for beginners)'},
        {'id':'multi-ball', 'name':'Multi-ball'},
        {'id':'serve-practice', 'name':'Serve practice'},
        {'id':'receive-practice', 'name':'Receive practice'},
        {'id':'serve-receive', 'name':'Serve/receive'},
        {'id':'short-game', 'name':'Short game (pushes)'},
    ])
    equipment = sa.table('equipment', sa.column('id'), sa.column('name'))
    op.bulk_insert(equipment, [{'id':'training-balls','name':'Training balls'}, {'id':'ball-catcher','name':'Ball catcher'}])
    requirements = sa.table('training_requirements', sa.column('training_type_id'), sa.column('equipment_id'))
    op.bulk_insert(requirements, [{'training_type_id':t,'equipment_id':e}
        for t in ['multi-ball','serve-practice','receive-practice','serve-receive']
        for e in ['training-balls','ball-catcher']])


def downgrade():
    op.drop_table('equipment_allocations')
    op.drop_table('reservations')
    op.drop_table('training_requirements')
    op.drop_table('equipment')
    op.drop_table('training_types')
    # btree_gist may be shared by unrelated tables; leave the extension installed.
