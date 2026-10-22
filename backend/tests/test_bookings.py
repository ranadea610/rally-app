from datetime import datetime, timedelta
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from app.models import EquipmentAllocation, Reservation, User
from test_api import approved, register


@pytest.fixture
def booking_setup(client, db, practice):
    coaches = []
    for name in ('john','joe'):
        headers = approved(client, db, name)
        window = client.post('/coach/availability', json=practice, headers=headers).json()
        coaches.append(window['coach_id'])
    player = register(client, 'bookingplayer').json()
    headers = {'X-CSRF-Token':player['csrf_token']}
    body = {'coach_id':coaches[0], 'starts_at':practice['starts_at'], 'training_type_id':'multi-ball'}
    return body, headers, coaches


def test_catalog_and_booking_details(client, db, booking_setup, practice):
    body, headers, coaches = booking_setup
    catalog = client.get('/training-types').json()
    assert len(catalog) == 6
    assert len(client.get('/equipment').json()) == 2
    for training in catalog:
        assert len(training['equipment_ids']) == (0 if training['id'] in ('rally','short-game') else 2)
    assert client.post('/reservations', json=body).status_code == 403
    response = client.post('/reservations', json=body, headers=headers)
    assert response.status_code == 201, response.text
    booking = response.json()
    assert len(booking['equipment']) == 2
    assert booking['training_type_id'] == 'multi-ball'
    assert booking['status'] == 'active'
    assert client.get('/reservations').json()[0]['id'] == booking['id']
    start = datetime.fromisoformat(practice['starts_at']).date()
    slots = client.get('/calendar', params={'start':str(start),'end':str(start+timedelta(days=1))}).json()['slots']
    at_time = [s for s in slots if datetime.fromisoformat(s['starts_at']) == datetime.fromisoformat(body['starts_at'])]
    assert len(at_time) == 2
    assert sum(s['booked'] for s in at_time) == 1
    assert all(not s['equipment_available'] for s in at_time)
    assert all('player_name' not in s for s in slots)


@pytest.mark.parametrize('training', ['multi-ball','serve-practice','receive-practice','serve-receive'])
def test_shared_equipment_blocks_other_coach(client, db, booking_setup, training):
    body, headers, coaches = booking_setup
    assert client.post('/reservations', json=body, headers=headers).status_code == 201
    other = register(client, 'otherplayer').json()
    other_headers = {'X-CSRF-Token':other['csrf_token']}
    second = {**body,'coach_id':coaches[1],'training_type_id':training}
    response = client.post('/reservations', json=second, headers=other_headers)
    assert response.status_code == 409, response.text
    assert db.scalar(select(func.count()).select_from(Reservation)) == 1
    assert db.scalar(select(func.count()).select_from(EquipmentAllocation)) == 2
    options = client.get('/booking-options', params={'coach_id':coaches[1],'starts_at':body['starts_at']}).json()
    assert options['slot_available']
    assert {t['id'] for t in options['training_types'] if t['available']} == {'rally','short-game'}
    second['training_type_id'] = 'rally'
    assert client.post('/reservations', json=second, headers=other_headers).status_code == 201


def test_player_conflict_and_adjacent_booking(client, booking_setup):
    body, headers, coaches = booking_setup
    assert client.post('/reservations', json={**body,'training_type_id':'rally'}, headers=headers).status_code == 201
    assert client.post('/reservations', json={**body,'coach_id':coaches[1]}, headers=headers).status_code == 409
    later = (datetime.fromisoformat(body['starts_at'])+timedelta(minutes=15)).isoformat()
    assert client.post('/reservations', json={**body,'coach_id':coaches[1],'starts_at':later}, headers=headers).status_code == 201


def test_cancellation_authorization_and_release(client, db, booking_setup):
    body, headers, coaches = booking_setup
    booking = client.post('/reservations', json=body, headers=headers).json()
    stranger = register(client, 'stranger').json()
    stranger_headers = {'X-CSRF-Token':stranger['csrf_token']}
    assert client.get('/reservations').json() == []
    assert client.delete('/reservations/'+booking['id'],headers=stranger_headers).status_code == 404
    # Restore the original player's session through login.
    login = client.post('/auth/login',json={'contact_method':'instagram','contact':'bookingplayer','password':'test-password-123'}).json()
    headers = {'X-CSRF-Token':login['csrf_token']}
    canceled = client.delete('/reservations/'+booking['id'],headers=headers)
    assert canceled.status_code == 200
    assert canceled.json()['status'] == 'canceled'
    assert canceled.json()['equipment'] == []
    assert client.delete('/reservations/'+booking['id'],headers=headers).status_code == 200
    assert client.get('/reservations').json() == []
    assert db.scalar(select(func.count()).select_from(EquipmentAllocation).where(EquipmentAllocation.active.is_(True))) == 0
    assert client.post('/reservations',json={**body,'coach_id':coaches[1]},headers=headers).status_code == 201


def test_booked_availability_is_protected(client, db, booking_setup, practice):
    body, headers, coaches = booking_setup
    booking = client.post('/reservations', json=body, headers=headers).json()
    login = client.post('/auth/login', json={'contact_method':'instagram','contact':'john','password':'test-password-123'}).json()
    headers = {'X-CSRF-Token':login['csrf_token']}
    window_id = db.get(Reservation,booking['id']).availability_id
    assert client.delete('/coach/availability/'+window_id, headers=headers).status_code == 409
    shortened = {**practice,'starts_at':(datetime.fromisoformat(practice['starts_at'])+timedelta(minutes=15)).isoformat()}
    assert client.put('/coach/availability/'+window_id,json=shortened,headers=headers).status_code == 409
    assert client.put('/coach/availability/'+window_id,json=practice,headers=headers).status_code == 200
    day = datetime.fromisoformat(practice['starts_at']).date()
    sessions = client.get('/coach/reservations',params={'start':str(day),'end':str(day+timedelta(days=1))}).json()
    assert sessions[0]['player_name'] == 'Alex'
    assert client.delete('/reservations/'+booking['id'],headers=headers).status_code == 200
    assert client.delete('/coach/availability/'+window_id,headers=headers).status_code == 204


def test_invalid_booking_inputs(client, db, booking_setup):
    body, headers, coaches = booking_setup
    for invalid in [
        {**body,'training_type_id':'unknown'},
        {**body,'starts_at':'2020-01-01T19:00:00-08:00'},
        {**body,'starts_at':datetime.fromisoformat(body['starts_at']).replace(tzinfo=None).isoformat()},
        {**body,'starts_at':(datetime.fromisoformat(body['starts_at'])+timedelta(minutes=1)).isoformat()},
    ]:
        assert client.post('/reservations',json=invalid,headers=headers).status_code == 422
    outside = (datetime.fromisoformat(body['starts_at'])+timedelta(hours=1)).isoformat()
    assert client.post('/reservations',json={**body,'starts_at':outside},headers=headers).status_code == 409
    assert client.post('/reservations',json={**body,'coach_id':'missing'},headers=headers).status_code == 404
    coach_headers = approved(client, db, 'selfcoach')
    coach_id = client.get('/auth/me').json()['user']['id']
    assert client.post('/reservations',json={**body,'coach_id':coach_id},headers=coach_headers).status_code == 422


def test_database_exclusion_rejects_double_booking(client, db, booking_setup):
    body, headers, coaches = booking_setup
    data = client.post('/reservations',json=body,headers=headers).json()
    original = db.get(Reservation,data['id'])
    # Bypass the API to verify PostgreSQL itself rejects overlapping bookings.
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Reservation(coach_id=original.coach_id, player_id=original.player_id,
                availability_id=original.availability_id, training_type_id='rally',
                starts_at=original.starts_at, ends_at=original.ends_at))
            db.flush()


def test_partial_equipment_conflict_and_database_guard(client, db, booking_setup):
    body, headers, coaches = booking_setup
    first = client.post('/reservations',json={**body,'training_type_id':'rally'},headers=headers).json()
    start = datetime.fromisoformat(first['starts_at'])
    end = datetime.fromisoformat(first['ends_at'])
    db.add(EquipmentAllocation(reservation_id=first['id'],equipment_id='ball-catcher',starts_at=start,ends_at=end))
    db.commit()
    other = register(client, 'equipmentplayer').json()
    other_headers = {'X-CSRF-Token':other['csrf_token']}
    second_body = {**body,'coach_id':coaches[1]}
    assert client.post('/reservations',json=second_body,headers=other_headers).status_code == 409
    assert db.scalar(select(func.count()).select_from(EquipmentAllocation)) == 1
    second = client.post('/reservations',json={**second_body,'training_type_id':'short-game'},headers=other_headers).json()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(EquipmentAllocation(reservation_id=second['id'],equipment_id='ball-catcher',starts_at=start,ends_at=end))
            db.flush()


def test_coach_cannot_play_and_coach_simultaneously(client, db, booking_setup, practice):
    body, headers, coaches = booking_setup
    john = client.post('/auth/login',json={'contact_method':'instagram','contact':'john','password':'test-password-123'}).json()
    john_headers = {'X-CSRF-Token':john['csrf_token']}
    assert client.post('/reservations',json={**body,'coach_id':coaches[1],'training_type_id':'rally'},headers=john_headers).status_code == 201
    player = client.post('/auth/login',json={'contact_method':'instagram','contact':'bookingplayer','password':'test-password-123'}).json()
    assert client.post('/reservations',json={**body,'training_type_id':'short-game'},headers={'X-CSRF-Token':player['csrf_token']}).status_code == 409


def test_coach_only_role_cannot_book_as_player(client, db, booking_setup):
    body, headers, coaches = booking_setup
    coach = register(client, 'coachonly','coach').json()
    assert client.post('/reservations',json=body,headers={'X-CSRF-Token':coach['csrf_token']}).status_code == 403
