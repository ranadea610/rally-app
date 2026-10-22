import os
from datetime import datetime, timedelta, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from app.database import get_db
from app.main import app


@pytest.fixture(scope='session')
def test_engine():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to a migrated disposable PostgreSQL database ending in _test.')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql' or not (parsed.database or '').endswith('_test'):
        raise RuntimeError('Tests require a dedicated PostgreSQL database whose name ends in _test.')
    engine = create_engine(url, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT version_num FROM alembic_version')) == '0002', 'Run alembic upgrade head on the test database first.'
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine):
    # SAVEPOINT joining lets API handlers commit without escaping test rollback.
    connection = test_engine.connect()
    transaction = connection.begin()
    factory = sessionmaker(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False)
    with factory() as session:
        yield session
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def practice():
    from zoneinfo import ZoneInfo
    day = datetime.now(ZoneInfo('America/Los_Angeles')).date() + timedelta(days=7)
    while day.weekday() != 0:
        day += timedelta(days=1)
    start = datetime.combine(day, time(18,30), ZoneInfo('America/Los_Angeles'))
    return {'starts_at': start.isoformat(), 'ends_at': (start+timedelta(hours=1)).isoformat()}
