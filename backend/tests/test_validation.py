from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.main import practice_interval, date_range
from app.schemas import Registration, AvailabilityInput
from app.config import Settings


def test_normalize_phone():
    data = Registration(name=' Alex ', contact_method='phone', contact='+1 (415) 555-1234', password='long-password')
    assert data.contact == '+14155551234'
    assert data.name == 'Alex'


def test_reject_naive_timestamps():
    with pytest.raises(ValidationError):
        AvailabilityInput(starts_at='2030-01-01T18:30:00', ends_at='2030-01-01T19:00:00')


def test_practice_windows_use_club_timezone():
    zone = ZoneInfo('America/Los_Angeles')
    day = datetime.now(zone).date() + timedelta(days=7)
    while day.weekday() != 0:
        day += timedelta(days=1)
    start = datetime.combine(day, time(18,30), zone)
    lower, upper = practice_interval(AvailabilityInput(starts_at=start, ends_at=start+timedelta(hours=1)))
    assert lower.hour in (1,2)
    assert (upper-lower).total_seconds() == 3600
    with pytest.raises(HTTPException):
        practice_interval(AvailabilityInput(starts_at=start, ends_at=start+timedelta(hours=3)))


def test_date_range_is_bounded():
    today = datetime.now().date()
    with pytest.raises(HTTPException):
        date_range(today, today)
    with pytest.raises(HTTPException):
        date_range(today, today+timedelta(days=94))


def test_production_settings_require_secure_explicit_configuration():
    valid={'environment':'production','cookie_secure':True,
           'database_url':'postgresql+psycopg://rally:'+'0123456789abcdef'*4+'@db/rally',
           'allowed_origins':['https://rally.university.edu']}
    assert Settings(_env_file=None,**valid).cookie_secure
    for change in [{'cookie_secure':False},{'database_url':'postgresql+psycopg://rally:rally@db/rally'},
                   {'allowed_origins':['http://rally.university.edu']},{'allowed_origins':['https://*.university.edu']},
                   {'allowed_origins':[]},{'session_hours':0}]:
        with pytest.raises(ValidationError) as error:
            Settings(_env_file=None,**{**valid,**change})
        assert '0123456789abcdef'*4 not in str(error.value)
