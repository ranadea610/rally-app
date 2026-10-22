from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker
from app.database import get_db
from app.main import app
from app.models import Availability, User, Reservation, EquipmentAllocation
from app.security import create_session, dummy_hash


def test_simultaneous_overlapping_availability_has_one_winner(test_engine, practice):
    """Real independent PostgreSQL transactions, not savepoints on one connection."""
    factory = sessionmaker(test_engine, expire_on_commit=False)
    with factory() as db:
        user = User(name='Concurrency test', contact_method='discord', contact=str(uuid4())[:32],
                    requested_role='coach', coach_approved=True, password_hash=dummy_hash)
        db.add(user)
        db.flush()
        token, session = create_session(db, user)
        db.commit()
        user_id, csrf = user.id, session.csrf_token

    def request_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = request_db
    barrier = Barrier(2)

    def publish():
        with TestClient(app) as client:
            client.cookies.set('rally_session', token)
            barrier.wait(timeout=10)
            return client.post('/coach/availability', json=practice, headers={'X-CSRF-Token': csrf}).status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: publish(), range(2)))
        assert sorted(results) == [201, 409]
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(Availability).where(Availability.coach_id == user_id)) == 1
    finally:
        app.dependency_overrides.clear()
        with factory() as db:
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


@pytest.mark.parametrize('scenario', ['same-coach','same-player','equipment','rally','adjacent'])
def test_simultaneous_bookings(test_engine, practice, scenario):
    factory = sessionmaker(test_engine, expire_on_commit=False)
    with factory() as db:
        users = [User(name=f'Race {i}', contact_method='discord', contact=str(uuid4())[:32],
            requested_role='both' if i < 2 else 'player', coach_approved=i < 2,
            password_hash=dummy_hash) for i in range(4)]
        db.add_all(users)
        db.flush()
        user_ids = [u.id for u in users]
        start = datetime.fromisoformat(practice['starts_at'])
        for coach in users[:2]:
            db.add(Availability(coach_id=coach.id, starts_at=start, ends_at=start+timedelta(hours=1)))
        credentials = []
        for player in users[2:]:
            token, session = create_session(db, player)
            credentials.append((token, session.csrf_token))
        db.commit()

    def request_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = request_db
    barrier = Barrier(2)

    def publish(i):
        player_index = 0 if scenario == 'same-player' else i
        coach_index = 0 if scenario == 'same-coach' else i
        token, csrf = credentials[player_index]
        body = {'coach_id':user_ids[coach_index], 'starts_at':(start+timedelta(minutes=15 if scenario=='adjacent' and i else 0)).isoformat(),
                'training_type_id':'rally' if scenario in ('rally','same-player','same-coach') else 'multi-ball'}
        with TestClient(app) as client:
            client.cookies.set('rally_session', token)
            barrier.wait(timeout=10)
            response = client.post('/reservations', json=body, headers={'X-CSRF-Token':csrf})
            return response.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(publish, range(2)))
        assert sorted(results) == ([201,201] if scenario in ('rally','adjacent') else [201,409])
        with factory() as db:
            bookings = db.scalars(select(Reservation).where(Reservation.player_id.in_(user_ids))).all()
            assert len(bookings) == results.count(201)
            count = db.scalar(select(func.count()).select_from(EquipmentAllocation).where(EquipmentAllocation.reservation_id.in_([b.id for b in bookings])))
            assert count == (2*len(bookings) if scenario in ('equipment','adjacent') else 0)
    finally:
        app.dependency_overrides.clear()
        with factory() as db:
            db.execute(delete(Reservation).where(Reservation.player_id.in_(user_ids)))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()
