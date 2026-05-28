from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    material_description: str = Field(min_length=5)
    warehouse_id: int = Field(ge=1)
    warehouse_unload_team_id: int = Field(ge=1, description="Muelle/equipo de descarga en la bodega")
    provider_team_index: int = Field(default=1, ge=1, le=20, description="Equipo propio del proveedor (1..N)")
    start_time: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)


class AppointmentUpdateStatus(BaseModel):
    status: AppointmentStatus


class AppointmentExtend(BaseModel):
    extra_minutes: int = Field(ge=15, le=180)


class AppointmentProviderCancel(BaseModel):
    reason: str = Field(min_length=5, max_length=300)


class AppointmentProviderReschedule(BaseModel):
    start_time: datetime
    warehouse_unload_team_id: int | None = Field(default=None, ge=1)
    provider_team_index: int | None = Field(default=None, ge=1, le=20)


class AppointmentOut(BaseModel):
    id: int
    provider_id: str
    provider_name: str
    warehouse_id: int
    warehouse_name: str = ""
    warehouse_unload_team_id: int | None = None
    warehouse_unload_team_name: str = ""
    provider_team_index: int = 1
    title: str
    material_description: str
    start_time: datetime
    duration_minutes: int
    status: AppointmentStatus
    logistics_extend_used: bool = False
    logistics_extend_minutes: int = 0
    total_extend_minutes: int = 0
    original_duration_minutes: int | None = None

    model_config = ConfigDict(from_attributes=True)
