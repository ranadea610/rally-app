from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from pydantic import Field, model_validator
from sqlalchemy.engine import make_url
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', hide_input_in_errors=True)
    database_url: str = 'postgresql+psycopg://rally:rally@127.0.0.1:5432/rally'
    club_timezone: str = 'America/Los_Angeles'
    allowed_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']
    cookie_secure: bool = False
    session_hours: int = Field(default=168, ge=1, le=720)
    environment: Literal['development','production'] = 'development'

    @model_validator(mode='after')
    def validate_deployment(self):
        ZoneInfo(self.club_timezone)
        if self.environment == 'production':
            if not self.cookie_secure:
                raise ValueError('Production requires secure cookies.')
            database = make_url(self.database_url)
            if database.get_backend_name() != 'postgresql' or len(database.password or '') < 32:
                raise ValueError('Production requires PostgreSQL with a unique database password of at least 32 characters.')
            if not self.allowed_origins:
                raise ValueError('Production requires an explicit HTTPS origin.')
            for origin in self.allowed_origins:
                parsed=urlsplit(origin)
                if parsed.scheme != 'https' or not parsed.hostname or '*' in origin or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                    raise ValueError('Production origins must be exact HTTPS origins.')
        return self


@lru_cache
def settings():
    return Settings()
