from datetime import date, datetime
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal['player', 'coach', 'both']
ContactMethod = Literal['instagram', 'discord', 'phone']


class Credentials(BaseModel):
    contact_method: ContactMethod
    contact: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode='after')
    def normalize_contact(self):
        self.contact = self.contact.strip().casefold()
        if self.contact_method == 'phone':
            value = re.sub(r'[\s().-]', '', self.contact)
            if not re.fullmatch(r'\+[1-9]\d{7,14}', value):
                raise ValueError('Use an international phone number, for example +14155551234.')
            self.contact = value
        elif self.contact_method == 'instagram':
            self.contact = self.contact.removeprefix('@')
            if not re.fullmatch(r'[a-z0-9._]{1,30}', self.contact):
                raise ValueError('Enter a valid Instagram handle.')
        elif not self.contact or len(self.contact) > 32:
            raise ValueError('Enter a Discord username of at most 32 characters.')
        return self


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=60)
    role: Role = 'player'

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Name cannot be blank.')
        return value.strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    contact_method: ContactMethod
    contact: str
    requested_role: Role
    coach_approved: bool
    is_admin: bool


class AvailabilityInput(BaseModel):
    starts_at: datetime
    ends_at: datetime

    @field_validator('starts_at', 'ends_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Include a timezone offset in each timestamp.')
        return value


class AvailabilityOut(AvailabilityInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    coach_id: str


class WeekAvailabilityInput(BaseModel):
    week_start: date
    windows: list[AvailabilityInput] = Field(max_length=30)


class BookingInput(BaseModel):
    coach_id: str = Field(min_length=1, max_length=36)
    starts_at: datetime
    training_type_id: str = Field(min_length=1, max_length=32)

    @field_validator('starts_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Include a timezone offset.')
        return value


class EquipmentOut(BaseModel):
    id: str
    name: str


class ReservationOut(BaseModel):
    id: str
    coach_id: str
    coach_name: str
    player_id: str
    player_name: str
    training_type_id: str
    training_type: str
    starts_at: datetime
    ends_at: datetime
    status: Literal['active', 'canceled']
    equipment: list[EquipmentOut]
