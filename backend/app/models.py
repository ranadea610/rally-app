from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def new_id():
    return str(uuid4())


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        UniqueConstraint('contact_method', 'contact', name='uq_user_contact'),
        CheckConstraint("requested_role IN ('player','coach','both')", name='ck_user_role'),
        CheckConstraint("contact_method IN ('instagram','discord','phone')", name='ck_contact_method'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(60))
    contact_method: Mapped[str] = mapped_column(String(16))
    contact: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    requested_role: Mapped[str] = mapped_column(String(8))
    coach_approved: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Availability(Base):
    __tablename__ = 'availability'
    __table_args__ = (
        CheckConstraint('ends_at > starts_at', name='ck_availability_interval'),
        Index('ix_availability_coach_start', 'coach_id', 'starts_at'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    coach_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrainingType(Base):
    __tablename__ = 'training_types'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class Equipment(Base):
    """Each row is one individually reservable resource with capacity one."""
    __tablename__ = 'equipment'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class TrainingRequirement(Base):
    __tablename__ = 'training_requirements'
    training_type_id: Mapped[str] = mapped_column(ForeignKey('training_types.id'), primary_key=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey('equipment.id'), primary_key=True)


class Reservation(Base):
    __tablename__ = 'reservations'
    __table_args__ = (
        CheckConstraint("status IN ('active','canceled')", name='ck_reservation_status'),
        CheckConstraint("ends_at = starts_at + interval '15 minutes'", name='ck_reservation_duration'),
        CheckConstraint('coach_id <> player_id', name='ck_reservation_not_self'),
        ExcludeConstraint(('coach_id', '='), (func.tstzrange(text('starts_at'), text('ends_at'), '[)'), '&&'),
                          where=text("status = 'active'"), name='ex_reservation_coach', using='gist'),
        ExcludeConstraint(('player_id', '='), (func.tstzrange(text('starts_at'), text('ends_at'), '[)'), '&&'),
                          where=text("status = 'active'"), name='ex_reservation_player', using='gist'),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    coach_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    player_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    availability_id: Mapped[str | None] = mapped_column(ForeignKey('availability.id', ondelete='SET NULL'))
    training_type_id: Mapped[str] = mapped_column(ForeignKey('training_types.id'))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default='active', server_default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EquipmentAllocation(Base):
    __tablename__ = 'equipment_allocations'
    __table_args__ = (
        CheckConstraint('ends_at > starts_at', name='ck_allocation_interval'),
        ExcludeConstraint(('equipment_id', '='), (func.tstzrange(text('starts_at'), text('ends_at'), '[)'), '&&'),
                          where=text('active'), name='ex_allocation_equipment', using='gist'),
    )
    reservation_id: Mapped[str] = mapped_column(ForeignKey('reservations.id', ondelete='CASCADE'), primary_key=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey('equipment.id'), primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
