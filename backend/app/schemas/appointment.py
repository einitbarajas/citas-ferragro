from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    material_description: str = Field(min_length=5)
    start_time: datetime
    duration_minutes: int = Field(default=60, ge=30, le=240)


class AppointmentUpdateStatus(BaseModel):
    status: AppointmentStatus


class AppointmentExtend(BaseModel):
    extra_minutes: int = Field(ge=15, le=180)


class AppointmentProviderCancel(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class AppointmentProviderReschedule(BaseModel):
    start_time: datetime


class AppointmentOut(BaseModel):
    id: int
    provider_id: str
    provider_name: str
    title: str
    material_description: str
    start_time: datetime
    duration_minutes: int
    status: AppointmentStatus

    model_config = ConfigDict(from_attributes=True)
