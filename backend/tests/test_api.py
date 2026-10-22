from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models import Availability, LoginSession, User
from app.security import digest, hasher


def register(client, contact='alex', role='player'):
    return client.post('/auth/register', json={'name': 'Alex', 'contact_method': 'instagram',
                       'contact': contact, 'password': 'test-password-123', 'role': role})


def approved(client, db, contact='coach'):
    result = register(client, contact, 'both').json()
    user = db.get(User, result['user']['id'])
    user.coach_approved = True
    db.commit()
    return {'X-CSRF-Token': result['csrf_token']}


def test_health(client):
    assert client.get('/health/live').status_code == 200
    assert client.get('/health/ready').status_code == 200


def test_authentication_and_logout(client, db):
    response = register(client, '@Alex')
    assert response.status_code == 201
    data = response.json()
    assert data['user']['contact'] == 'alex'
    assert 'password_hash' not in data['user']
    assert 'HttpOnly' in response.headers['set-cookie']
    user = db.get(User, data['user']['id'])
    assert user.password_hash != 'test-password-123'
    assert hasher.verify(user.password_hash, 'test-password-123')
    assert db.get(LoginSession, digest(client.cookies['rally_session'])) is not None
    assert client.get('/auth/me').json()['user']['id'] == user.id
    assert client.post('/auth/logout').status_code == 403
    assert client.post('/auth/logout', headers={'X-CSRF-Token': data['csrf_token']}).status_code == 204
    assert client.get('/auth/me').status_code == 401
    assert client.post('/auth/login', json={'contact_method':'instagram','contact':'alex','password':'wrong-password'}).status_code == 401
    assert client.post('/auth/login', json={'contact_method':'instagram','contact':'@ALEX','password':'test-password-123'}).status_code == 200


def test_registration_validation_and_duplicate(client):
    assert register(client).status_code == 201
    assert register(client, '@ALEX').status_code == 409
    assert register(client, 'bad handle').status_code == 422
    assert client.post('/auth/register', json={'name':' ', 'contact_method':'phone','contact':'555','password':'short'}).status_code == 422


def test_expired_session_and_untrusted_origin(client, db):
    register(client)
    session = db.get(LoginSession, digest(client.cookies['rally_session']))
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert client.get('/auth/me').status_code == 401
    assert client.post('/auth/login', headers={'Origin':'https://untrusted.example'}, json={}).status_code == 403


def test_coach_approval_and_admin_permissions(client, db, practice):
    result = register(client, 'coach', 'coach').json()
    headers = {'X-CSRF-Token': result['csrf_token']}
    assert client.post('/coach/availability', json=practice, headers=headers).status_code == 403
    assert client.post(f"/admin/coaches/{result['user']['id']}/approve", headers=headers).status_code == 403
    user = db.get(User, result['user']['id'])
    user.is_admin = True
    db.commit()
    assert len(client.get('/admin/coach-requests').json()) == 1
    assert client.post(f'/admin/coaches/{user.id}/approve', headers=headers).json()['coach_approved'] is True
    assert client.post('/coach/availability', json=practice, headers=headers).status_code == 201


def test_availability_crud_calendar_and_overlap(client, db, practice):
    headers = approved(client, db)
    assert client.post('/coach/availability', json=practice).status_code == 403
    response = client.post('/coach/availability', json=practice, headers=headers)
    assert response.status_code == 201
    window = response.json()
    assert client.post('/coach/availability', json=practice, headers=headers).status_code == 409
    start = datetime.fromisoformat(practice['starts_at'])
    query = {'start': str(start.date()), 'end': str(start.date()+timedelta(days=1))}
    assert len(client.get('/coach/availability', params=query).json()) == 1
    slots = client.get('/calendar', params=query).json()['slots']
    assert len(slots) == 4
    assert 'contact' not in slots[0]
    assert datetime.fromisoformat(slots[0]['ends_at'])-datetime.fromisoformat(slots[0]['starts_at']) == timedelta(minutes=15)
    adjacent = {'starts_at': practice['ends_at'], 'ends_at': (start+timedelta(hours=2)).isoformat()}
    assert client.post('/coach/availability', json=adjacent, headers=headers).status_code == 201
    shorter = {**practice, 'ends_at': (start+timedelta(minutes=30)).isoformat()}
    assert client.put(f"/coach/availability/{window['id']}", json=shorter, headers=headers).status_code == 200
    assert client.delete(f"/coach/availability/{window['id']}", headers=headers).status_code == 204
    assert len(client.get('/calendar', params=query).json()['slots']) == 4


def test_availability_ownership_and_player_access(client, db, practice):
    headers = approved(client, db)
    window = client.post('/coach/availability', json=practice, headers=headers).json()
    other_headers = approved(client, db, 'othercoach')
    assert client.put(f"/coach/availability/{window['id']}", json=practice, headers=other_headers).status_code == 404
    assert client.delete(f"/coach/availability/{window['id']}", headers=other_headers).status_code == 404
    player = register(client, 'player').json()
    player_headers = {'X-CSRF-Token': player['csrf_token']}
    assert client.post('/coach/availability', json=practice, headers=player_headers).status_code == 403
    assert client.get('/coach/availability', params={'start':'2030-01-01','end':'2030-01-03'}).status_code == 403
    assert client.get('/calendar', params={'start':'2030-01-01','end':'2031-01-01'}).status_code == 422


def test_invalid_practice_intervals(client, db, practice):
    headers = approved(client, db)
    start = datetime.fromisoformat(practice['starts_at'])
    invalid = [
        {**practice, 'starts_at': start.replace(tzinfo=None).isoformat()},
        {**practice, 'ends_at': practice['starts_at']},
        {**practice, 'starts_at': (start+timedelta(minutes=1)).isoformat()},
        {**practice, 'starts_at': (start-timedelta(minutes=15)).isoformat()},
        {'starts_at': (start+timedelta(days=2)).isoformat(), 'ends_at': (start+timedelta(days=2,hours=1)).isoformat()},
        {'starts_at':'2020-01-06T18:30:00-08:00','ends_at':'2020-01-06T19:30:00-08:00'},
    ]
    for body in invalid:
        assert client.post('/coach/availability', json=body, headers=headers).status_code == 422


def test_anonymous_cannot_read_calendar(client):
    assert client.get('/calendar', params={'start':'2030-01-01','end':'2030-02-01'}).status_code == 401
