from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import Availability, LoginSession, User, Reservation, EquipmentAllocation
from .bookings import router as booking_router, protect_window
from .schemas import AvailabilityInput, AvailabilityOut, Credentials, Registration, UserOut, WeekAvailabilityInput
from .security import (admin_user, coach_user, create_session, current_session,
                       current_user, dummy_hash, hasher, verify_password)

app = FastAPI(title='Rally API', version='0.1.0')
app.include_router(booking_router)
app.add_middleware(CORSMiddleware, allow_origins=settings().allowed_origins,
                   allow_credentials=True, allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
                   allow_headers=['Content-Type', 'X-CSRF-Token'])


@app.middleware('http')
async def browser_origin_guard(request: Request, call_next):
    # Covers login CSRF as well as authenticated writes. Non-browser API clients
    # can omit Origin; cookie-authenticated writes still require the CSRF header.
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in settings().allowed_origins:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail': 'Untrusted request origin.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/health/live')
def live():
    return {'status': 'ok'}


@app.get('/health/ready')
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
        # Readiness also requires migrations, not just a running DB process.
        db.execute(select(User.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(503, 'Database is not ready.') from None
    return {'status': 'ready'}


def auth_response(db: Session, user: User, response: Response):
    token, session = create_session(db, user)
    db.commit()
    response.set_cookie('rally_session', token, httponly=True,
                        secure=settings().cookie_secure, samesite='lax',
                        max_age=settings().session_hours * 3600, path='/')
    return {'user': UserOut.model_validate(user), 'csrf_token': session.csrf_token}


@app.post('/auth/register', status_code=201)
def register(body: Registration, response: Response, db: Session = Depends(get_db)):
    user = User(name=body.name, contact_method=body.contact_method, contact=body.contact,
                requested_role=body.role, password_hash=hasher.hash(body.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account with this contact already exists.') from None
    return auth_response(db, user, response)


@app.post('/auth/login')
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.contact_method == body.contact_method, User.contact == body.contact))
    if not verify_password(body.password, user.password_hash if user else dummy_hash) or not user:
        raise HTTPException(401, 'Invalid contact or password.')
    return auth_response(db, user, response)


@app.get('/auth/me')
def me(user: User = Depends(current_user), session: LoginSession = Depends(current_session)):
    return {'user': UserOut.model_validate(user), 'csrf_token': session.csrf_token}


@app.post('/auth/logout', status_code=204)
def logout(response: Response, session: LoginSession = Depends(current_session), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
    response.delete_cookie('rally_session', path='/', secure=settings().cookie_secure, samesite='lax')


@app.get('/admin/coach-requests', response_model=list[UserOut])
def coach_requests(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.requested_role.in_(['coach', 'both']), User.coach_approved.is_(False))).all()


@app.post('/admin/coaches/{user_id}/approve', response_model=UserOut)
def approve_coach(user_id: str, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')
    if user.requested_role not in ('coach', 'both'):
        raise HTTPException(409, 'This user has not requested coaching access.')
    user.coach_approved = True
    db.commit()
    return user


def practice_interval(body: AvailabilityInput, allow_past: bool = False):
    zone = ZoneInfo(settings().club_timezone)
    start, end = body.starts_at.astimezone(zone), body.ends_at.astimezone(zone)
    if start >= end or start.date() != end.date():
        raise HTTPException(422, 'Availability must be a positive interval on one practice date.')
    if start.weekday() not in (0, 1, 3) or start.time() < time(18, 30) or end.time() > time(21):
        raise HTTPException(422, 'Practice is Monday, Tuesday, and Thursday, 6:30–9 PM in the club timezone.')
    if any(d.minute % 15 or d.second or d.microsecond for d in (start, end)):
        raise HTTPException(422, 'Availability must align to 15-minute boundaries.')
    if not allow_past and start <= datetime.now(zone):
        raise HTTPException(422, 'Availability must start in the future.')
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def lock_coach(db: Session, coach_id: str):
    # All availability mutations lock this row so concurrent writes serialize,
    # including when the coach has no existing windows to lock yet.
    db.execute(select(User).where(User.id == coach_id).with_for_update()).scalar_one()


def check_overlap(db: Session, coach_id: str, start: datetime, end: datetime, exclude: str | None = None):
    query = select(Availability.id).where(Availability.coach_id == coach_id,
                                          Availability.starts_at < end, Availability.ends_at > start)
    if exclude:
        query = query.where(Availability.id != exclude)
    if db.scalar(query.limit(1)):
        raise HTTPException(409, 'This overlaps your existing availability.')


@app.post('/coach/availability', response_model=AvailabilityOut, status_code=201)
def add_availability(body: AvailabilityInput, coach: User = Depends(coach_user), db: Session = Depends(get_db)):
    start, end = practice_interval(body)
    lock_coach(db, coach.id)
    check_overlap(db, coach.id, start, end)
    window = Availability(coach_id=coach.id, starts_at=start, ends_at=end)
    db.add(window)
    db.commit()
    return window


@app.put('/coach/availability/week', response_model=list[AvailabilityOut])
def replace_week(body: WeekAvailabilityInput, coach: User = Depends(coach_user), db: Session = Depends(get_db)):
    if body.week_start.weekday() != 0:
        raise HTTPException(422, 'The week must start on Monday.')
    lower, upper = date_range(body.week_start, body.week_start + timedelta(days=7))
    lock_coach(db, coach.id)
    old = db.scalars(select(Availability).where(Availability.coach_id == coach.id,
        Availability.starts_at >= lower, Availability.starts_at < upper)).all()
    intervals = sorted([practice_interval(w, allow_past=True) for w in body.windows])
    for i, (start, end) in enumerate(intervals):
        if not lower <= start < end <= upper:
            raise HTTPException(422, 'Every window must be within the selected week.')
        if i and intervals[i-1][1] > start:
            raise HTTPException(409, 'Selected availability windows overlap.')
        if start <= datetime.now(timezone.utc) and not any(w.starts_at <= start and w.ends_at >= end for w in old):
            raise HTTPException(422, 'Past availability can only be preserved, not added.')
    booked = db.scalars(select(Reservation).where(Reservation.coach_id == coach.id,
        Reservation.status == 'active', Reservation.starts_at >= lower, Reservation.starts_at < upper)).all()
    for booking in booked:
        if not any(start <= booking.starts_at and end >= booking.ends_at for start, end in intervals):
            raise HTTPException(409, 'Keep all booked slots selected, or cancel the affected sessions first.')
    windows = [Availability(coach_id=coach.id, starts_at=start, ends_at=end) for start,end in intervals]
    db.add_all(windows)
    db.flush()
    for booking in booked:
        booking.availability_id = next(w.id for w in windows if w.starts_at <= booking.starts_at and w.ends_at >= booking.ends_at)
    db.flush()
    for window in old:
        db.delete(window)
    db.commit()
    return windows


@app.put('/coach/availability/{availability_id}', response_model=AvailabilityOut)
def edit_availability(availability_id: str, body: AvailabilityInput, coach: User = Depends(coach_user), db: Session = Depends(get_db)):
    start, end = practice_interval(body)
    lock_coach(db, coach.id)
    window = db.get(Availability, availability_id)
    if not window or window.coach_id != coach.id:
        raise HTTPException(404, 'Availability not found.')
    check_overlap(db, coach.id, start, end, window.id)
    protect_window(db, window, start, end)
    window.starts_at, window.ends_at = start, end
    db.commit()
    return window


@app.delete('/coach/availability/{availability_id}', status_code=204)
def delete_availability(availability_id: str, coach: User = Depends(coach_user), db: Session = Depends(get_db)):
    lock_coach(db, coach.id)
    window = db.get(Availability, availability_id)
    if not window or window.coach_id != coach.id:
        raise HTTPException(404, 'Availability not found.')
    protect_window(db, window)
    db.delete(window)
    db.commit()


def date_range(start: date, end: date):
    if not 0 < (end - start).days <= 93:
        raise HTTPException(422, 'Choose an exclusive end date 1–93 days after start.')
    zone = ZoneInfo(settings().club_timezone)
    return datetime.combine(start, time.min, zone), datetime.combine(end, time.min, zone)


@app.get('/coach/availability', response_model=list[AvailabilityOut])
def own_availability(start: date, end: date, coach: User = Depends(coach_user), db: Session = Depends(get_db)):
    lower, upper = date_range(start, end)
    return db.scalars(select(Availability).where(Availability.coach_id == coach.id,
                     Availability.starts_at >= lower, Availability.starts_at < upper).order_by(Availability.starts_at)).all()


@app.get('/calendar')
def calendar(start: date, end: date, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lower, upper = date_range(start, end)
    rows = db.execute(select(Availability, User.name).join(User, User.id == Availability.coach_id)
                      .where(Availability.starts_at >= lower, Availability.starts_at < upper,
                             User.coach_approved.is_(True))
                      .order_by(Availability.starts_at, User.name)).all()
    result = []
    booked = db.scalars(select(Reservation).where(Reservation.status == 'active',
        Reservation.starts_at < upper, Reservation.ends_at > lower)).all()
    allocations = db.scalars(select(EquipmentAllocation).where(EquipmentAllocation.active.is_(True),
        EquipmentAllocation.starts_at < upper, EquipmentAllocation.ends_at > lower)).all()
    for window, name in rows:
        cursor = window.starts_at
        while cursor + timedelta(minutes=15) <= window.ends_at:
            result.append({'availability_id': window.id, 'coach_id': window.coach_id,
                           'coach_name': name, 'starts_at': cursor,
                           'ends_at': cursor + timedelta(minutes=15),
                           'booked': any(window.coach_id in (b.coach_id,b.player_id) and b.starts_at < cursor+timedelta(minutes=15) and b.ends_at > cursor for b in booked),
                           'equipment_available': not any(a.starts_at < cursor+timedelta(minutes=15) and a.ends_at > cursor for a in allocations)})
            cursor += timedelta(minutes=15)
    return {'timezone': settings().club_timezone, 'slots': result}
