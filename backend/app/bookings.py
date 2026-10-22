"""Booking writes use one transaction and a consistent user/resource lock order."""
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import (Availability, Equipment, EquipmentAllocation, Reservation,
                     TrainingRequirement, TrainingType, User)
from .schemas import BookingInput, ReservationOut
from .security import coach_user, current_user

router = APIRouter()


def active_overlaps(start, end):
    return (Reservation.status == 'active', Reservation.starts_at < end, Reservation.ends_at > start)


def equipment_busy(db: Session, equipment_ids: list[str], start, end):
    return db.scalar(select(EquipmentAllocation.equipment_id).where(
        EquipmentAllocation.equipment_id.in_(equipment_ids), EquipmentAllocation.active.is_(True),
        EquipmentAllocation.starts_at < end, EquipmentAllocation.ends_at > start).limit(1)) is not None


def protect_window(db: Session, window: Availability, start=None, end=None):
    """Availability edits must preserve coverage of existing active bookings."""
    query = select(Reservation.id).where(Reservation.availability_id == window.id, Reservation.status == 'active')
    if start is not None:
        query = query.where(or_(Reservation.starts_at < start, Reservation.ends_at > end))
    if db.scalar(query.limit(1)):
        raise HTTPException(409, 'Cancel the affected bookings before removing their availability.')


def reservation_out(db: Session, booking: Reservation):
    coach = db.get(User, booking.coach_id)
    player = db.get(User, booking.player_id)
    training = db.get(TrainingType, booking.training_type_id)
    resources = db.execute(select(Equipment.id, Equipment.name).join(
        EquipmentAllocation, EquipmentAllocation.equipment_id == Equipment.id).where(
        EquipmentAllocation.reservation_id == booking.id, EquipmentAllocation.active.is_(True))
        .order_by(Equipment.id)).all()
    return {'id': booking.id, 'coach_id': coach.id, 'coach_name': coach.name,
            'player_id': player.id, 'player_name': player.name,
            'training_type_id': training.id, 'training_type': training.name,
            'starts_at': booking.starts_at, 'ends_at': booking.ends_at, 'status': booking.status,
            'equipment': [{'id':r.id, 'name':r.name} for r in resources]}


@router.get('/training-types')
def training_types(user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = []
    for training in db.scalars(select(TrainingType).order_by(TrainingType.id)):
        resources = db.scalars(select(TrainingRequirement.equipment_id).where(
            TrainingRequirement.training_type_id == training.id).order_by(TrainingRequirement.equipment_id)).all()
        result.append({'id': training.id, 'name': training.name, 'equipment_ids': resources})
    return result


@router.get('/equipment')
def equipment(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{'id': e.id, 'name': e.name, 'capacity': 1} for e in db.scalars(select(Equipment).order_by(Equipment.id))]


@router.post('/reservations', status_code=201, response_model=ReservationOut)
def book(body: BookingInput, player: User = Depends(current_user), db: Session = Depends(get_db)):
    if player.requested_role not in ('player', 'both'):
        raise HTTPException(403, 'A player role is required to book coaching.')
    if player.id == body.coach_id:
        raise HTTPException(422, 'You cannot book yourself as a coach.')
    start = body.starts_at.astimezone(timezone.utc)
    end = start + timedelta(minutes=15)
    if start <= datetime.now(timezone.utc) or start.minute % 15 or start.second or start.microsecond:
        raise HTTPException(422, 'Choose a future time on a 15-minute boundary.')
    training = db.get(TrainingType, body.training_type_id)
    if not training:
        raise HTTPException(422, 'Unknown training type.')
    # Lock coach and player together, sorted, to prevent both same-person
    # bookings and cross-role coaching/playing conflicts without deadlocks.
    people = db.scalars(select(User).where(User.id.in_([player.id, body.coach_id]))
        .order_by(User.id).with_for_update().execution_options(populate_existing=True)).all()
    coach = next((u for u in people if u.id == body.coach_id), None)
    if not coach or not coach.coach_approved or coach.requested_role not in ('coach', 'both'):
        raise HTTPException(404, 'Approved coach not found.')
    window = db.scalar(select(Availability).where(Availability.coach_id == coach.id,
        Availability.starts_at <= start, Availability.ends_at >= end).limit(1))
    if not window:
        raise HTTPException(409, 'This time is no longer within the coach’s availability.')
    people_ids = [coach.id, player.id]
    if db.scalar(select(Reservation.id).where(*active_overlaps(start,end), or_(
        Reservation.coach_id.in_(people_ids), Reservation.player_id.in_(people_ids))).limit(1)):
        raise HTTPException(409, 'The coach or player already has a session at this time.')
    resource_ids = list(db.scalars(select(TrainingRequirement.equipment_id).where(
        TrainingRequirement.training_type_id == training.id).order_by(TrainingRequirement.equipment_id)))
    if resource_ids:
        db.scalars(select(Equipment).where(Equipment.id.in_(resource_ids)).order_by(Equipment.id).with_for_update()).all()
        if equipment_busy(db, resource_ids, start, end):
            raise HTTPException(409, 'The training balls and ball catcher are reserved at this time. Choose rally, short game, or another time.')
    booking = Reservation(coach_id=coach.id, player_id=player.id, availability_id=window.id,
                          training_type_id=training.id, starts_at=start, ends_at=end)
    db.add(booking)
    try:
        db.flush()
        for equipment_id in resource_ids:
            db.add(EquipmentAllocation(reservation_id=booking.id, equipment_id=equipment_id, starts_at=start, ends_at=end))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'The session or equipment was just reserved. Refresh and choose another time.') from None
    return reservation_out(db, booking)


@router.get('/booking-options')
def booking_options(coach_id: str, starts_at: datetime, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise HTTPException(422, 'Include a timezone offset.')
    start, end = starts_at.astimezone(timezone.utc), starts_at.astimezone(timezone.utc)+timedelta(minutes=15)
    coach = db.get(User, coach_id)
    if not coach or not coach.coach_approved or coach.requested_role not in ('coach', 'both'):
        raise HTTPException(404, 'Approved coach not found.')
    valid_time = start > datetime.now(timezone.utc) and not (start.minute % 15 or start.second or start.microsecond)
    window = db.scalar(select(Availability.id).where(Availability.coach_id == coach_id,
        Availability.starts_at <= start, Availability.ends_at >= end).limit(1))
    occupied = db.scalar(select(Reservation.id).where(*active_overlaps(start,end), or_(
        Reservation.coach_id.in_([coach_id,user.id]), Reservation.player_id.in_([coach_id,user.id]))).limit(1))
    available = bool(valid_time and window and not occupied and user.id != coach_id and user.requested_role in ('player','both'))
    options = training_types(user, db)
    for option in options:
        resources_free = not equipment_busy(db, option['equipment_ids'], start, end)
        option['available'] = available and resources_free
        option['reason'] = None if option['available'] else 'slot_unavailable' if not available else 'equipment_reserved'
    return {'slot_available': available, 'training_types': options}


@router.get('/reservations', response_model=list[ReservationOut])
def upcoming(user: User = Depends(current_user), db: Session = Depends(get_db)):
    bookings = db.scalars(select(Reservation).where(Reservation.player_id == user.id,
        Reservation.status == 'active', Reservation.ends_at > datetime.now(timezone.utc))
        .order_by(Reservation.starts_at)).all()
    return [reservation_out(db, b) for b in bookings]


@router.get('/coach/reservations', response_model=list[ReservationOut])
def coach_bookings(start: date, end: date, coach: User = Depends(coach_user), db: Session = Depends(get_db)):
    from .main import date_range
    lower, upper = date_range(start, end)
    bookings = db.scalars(select(Reservation).where(Reservation.coach_id == coach.id,
        Reservation.status == 'active', Reservation.starts_at >= lower, Reservation.starts_at < upper)
        .order_by(Reservation.starts_at)).all()
    return [reservation_out(db, b) for b in bookings]


@router.delete('/reservations/{reservation_id}', response_model=ReservationOut)
def cancel(reservation_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking = db.get(Reservation, reservation_id)
    if not booking or user.id not in (booking.player_id, booking.coach_id):
        raise HTTPException(404, 'Reservation not found.')
    db.scalars(select(User).where(User.id.in_([booking.player_id, booking.coach_id])).order_by(User.id).with_for_update()).all()
    booking = db.scalar(select(Reservation).where(Reservation.id == reservation_id)
        .with_for_update().execution_options(populate_existing=True))
    if booking.status == 'active':
        if booking.starts_at <= datetime.now(timezone.utc):
            raise HTTPException(409, 'A session cannot be canceled after it starts.')
        booking.status = 'canceled'
        for allocation in db.scalars(select(EquipmentAllocation).where(EquipmentAllocation.reservation_id == booking.id)):
            allocation.active = False
        db.commit()
    return reservation_out(db, booking)
