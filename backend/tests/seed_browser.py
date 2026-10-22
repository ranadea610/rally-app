"""Create/remove fixtures for one browser-test run, in a test database only."""
import os
import sys
from pathlib import Path
from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
from uuid import UUID
from sqlalchemy import create_engine,delete,select,or_
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import User,Availability,Reservation
from app.security import hasher

url=os.environ['RALLY_E2E_DATABASE_URL']
parsed=make_url(url)
if parsed.get_backend_name()!='postgresql' or not (parsed.database or '').endswith('_test'):
    raise RuntimeError('Browser tests require a dedicated PostgreSQL database ending in _test.')
tag=str(UUID(os.environ['RALLY_E2E_RUN_ID']))[:8]
prefix=f'e2e_{tag}_'
engine=create_engine(url,connect_args={'connect_timeout':5})
with Session(engine) as db:
    if sys.argv[1]=='cleanup':
        ids=list(db.scalars(select(User.id).where(User.contact.like(prefix.replace('_',r'\_')+'%',escape='\\'))))
        db.execute(delete(Reservation).where(or_(Reservation.coach_id.in_(ids),Reservation.player_id.in_(ids))))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()
    else:
        zone=ZoneInfo('America/Los_Angeles')
        day=datetime.now(zone).date()+timedelta(days=7)
        while day.weekday()!=0:day+=timedelta(days=1)
        start=datetime.combine(day,time(18,30),zone)
        password_hash=hasher.hash('rally-e2e-passphrase')
        for name,role,approved,admin in [('john','both',True,False),('joe','coach',True,False),('player','player',False,False),('other','player',False,False),('officer','player',False,True)]:
            user=User(name=name.title(),contact_method='instagram',contact=prefix+name,password_hash=password_hash,requested_role=role,coach_approved=approved,is_admin=admin)
            db.add(user);db.flush()
            if approved:db.add(Availability(coach_id=user.id,starts_at=start,ends_at=start+timedelta(hours=1)))
        db.commit()
