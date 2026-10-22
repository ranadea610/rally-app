from datetime import datetime,timedelta
from sqlalchemy import select
from app.models import Availability,Reservation
from test_api import approved,register


def test_week_replace_is_atomic_and_preserves_bookings(client,db,practice):
    headers=approved(client,db)
    original=client.post('/coach/availability',json=practice,headers=headers).json()
    monday=datetime.fromisoformat(practice['starts_at']).date().isoformat()
    player=register(client,'weekplayer').json()
    booking=client.post('/reservations',json={'coach_id':original['coach_id'],'starts_at':practice['starts_at'],'training_type_id':'rally'},headers={'X-CSRF-Token':player['csrf_token']}).json()
    auth=client.post('/auth/login',json={'contact_method':'instagram','contact':'coach','password':'test-password-123'}).json()
    headers={'X-CSRF-Token':auth['csrf_token']}
    assert client.put('/coach/availability/week',json={'week_start':monday,'windows':[]},headers=headers).status_code==409
    assert db.get(Availability,original['id']) is not None
    assert db.get(Reservation,booking['id']).availability_id==original['id']
    start=datetime.fromisoformat(practice['starts_at'])
    windows=[{'starts_at':(start+timedelta(minutes=15*i)).isoformat(),'ends_at':(start+timedelta(minutes=15*(i+1))).isoformat()} for i in range(4)]
    saved=client.put('/coach/availability/week',json={'week_start':monday,'windows':windows},headers=headers)
    assert saved.status_code==200,saved.text
    assert len(saved.json())==4
    db.expire_all()
    assert db.get(Availability,original['id']) is None
    assert db.get(Reservation,booking['id']).availability_id in [w['id'] for w in saved.json()]
    assert client.delete('/reservations/'+booking['id'],headers=headers).status_code==200
    assert client.put('/coach/availability/week',json={'week_start':monday,'windows':[]},headers=headers).status_code==200


def test_week_validation_and_permissions(client,db,practice):
    headers=approved(client,db)
    monday=datetime.fromisoformat(practice['starts_at']).date()
    for body,code in [
        ({'week_start':str(monday+timedelta(days=1)),'windows':[]},422),
        ({'week_start':str(monday),'windows':[practice,practice]},409),
        ({'week_start':str(monday+timedelta(days=7)),'windows':[practice]},422),
        ({'week_start':'2020-01-06','windows':[{'starts_at':'2020-01-06T18:30:00-08:00','ends_at':'2020-01-06T18:45:00-08:00'}]},422),
    ]:
        response=client.put('/coach/availability/week',json=body,headers=headers)
        assert response.status_code==code,response.text
    assert list(db.scalars(select(Availability)))==[]
    player=register(client,'weekstranger').json()
    assert client.put('/coach/availability/week',json={'week_start':str(monday),'windows':[]},headers={'X-CSRF-Token':player['csrf_token']}).status_code==403
