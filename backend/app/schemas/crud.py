from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.appointment import AppointmentStatus


class RoleIn(BaseModel):
    name: str = Field(min_length=3, max_length=40)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserIn(BaseModel):
    document_id: str = Field(min_length=7, max_length=10)
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=100)
    role_id: int
    warehouse_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    password: str | None = Field(default=None, min_length=6, max_length=100)
    role_id: int | None = None
    warehouse_ids: list[int] | None = None


class UserCrudOut(BaseModel):
    document_id: str
    email: EmailStr
    full_name: str
    role_id: int
    role_name: str
    warehouse_ids: list[int] = Field(default_factory=list)


class ProviderIn(BaseModel):
    nit: int = Field(ge=1000000000, le=9999999999)
    verification_digit: str = Field(min_length=1, max_length=1)
    company_name: str = Field(min_length=3, max_length=160)
    company_email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    contact_name: str = Field(min_length=3, max_length=160)
    contact_document: str = Field(min_length=7, max_length=10)


class ProviderUpdate(BaseModel):
    verification_digit: str | None = Field(default=None, min_length=1, max_length=1)
    company_name: str | None = Field(default=None, min_length=3, max_length=160)
    company_email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=100)
    contact_name: str | None = Field(default=None, min_length=3, max_length=160)
    contact_document: str | None = Field(default=None, min_length=7, max_length=10)
    unload_teams: int | None = Field(default=None, ge=1, le=20)


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nit: int
    verification_digit: str
    company_name: str
    company_email: EmailStr
    contact_name: str
    contact_document: str
    status: str = "activo"
    suspended_at: datetime | None = None
    suspension_reason: str | None = None
    purge_scheduled_at: datetime | None = None
    appointments_count: int = 0
    last_login_at: datetime | None = None
    unload_teams: int = 1


class ProviderSuspendIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AppointmentIn(BaseModel):
    provider_id: int = Field(ge=1000000000, le=9999999999)
    warehouse_id: int = Field(ge=1)
    warehouse_unload_team_id: int | None = Field(default=None, ge=1)
    provider_team_index: int = Field(default=1, ge=1, le=20)
    material_description: str = Field(min_length=5)
    start_time: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    status: AppointmentStatus = AppointmentStatus.sin_revision


class AppointmentUpdate(BaseModel):
    provider_id: int | None = Field(default=None, ge=1000000000, le=9999999999)
    warehouse_id: int | None = Field(default=None, ge=1)
    warehouse_unload_team_id: int | None = Field(default=None, ge=1)
    material_description: str | None = Field(default=None, min_length=5)
    start_time: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    status: AppointmentStatus | None = None
    confirm_non_standard_slot: bool = False
    staff_change_reason: str | None = Field(default=None, max_length=500)


class AppointmentCrudOut(BaseModel):
    id: int
    provider_id: int
    provider_name: str = ""
    warehouse_id: int
    warehouse_name: str = ""
    warehouse_unload_team_id: int | None = None
    warehouse_unload_team_name: str = ""
    material_description: str
    start_time: datetime
    duration_minutes: int
    status: AppointmentStatus
    logistics_extend_used: bool = False
    logistics_extend_minutes: int = 0
    total_extend_minutes: int = 0
    original_duration_minutes: int | None = None


class WarehouseIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    active: bool = True
    sort_order: int = Field(default=0, ge=0, le=9999)
    unload_teams: int = Field(default=1, ge=1, le=20)


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    unload_teams: int | None = Field(default=None, ge=1, le=20)


class WarehouseOut(BaseModel):
    id: int
    name: str
    address: str | None = None
    active: bool
    sort_order: int
    unload_teams: int = 1


class UnloadTeamNameIn(BaseModel):
    id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)


class WarehouseUnloadTeamsNamesIn(BaseModel):
    teams: list[UnloadTeamNameIn] = Field(min_length=1)


class ChangeLogIn(BaseModel):
    actor_id: str = Field(min_length=1, max_length=30)
    appointment_id: int
    action: str = Field(min_length=3, max_length=80)
    description: str = Field(min_length=3)
    created_at: datetime


class ChangeLogUpdate(BaseModel):
    actor_id: str | None = Field(default=None, min_length=1, max_length=30)
    appointment_id: int | None = None
    action: str | None = Field(default=None, min_length=3, max_length=80)
    description: str | None = Field(default=None, min_length=3)
    created_at: datetime | None = None


class ChangeLogOut(BaseModel):
    id: int
    actor_id: str
    appointment_id: int | None = None
    action: str
    description: str
    created_at: datetime
    actor_name: str = ""
    actor_role: str = ""
    warehouse_id: int | None = None
    warehouse_name: str = ""
    critical_field: str | None = None
    old_value: str | None = None
    new_value: str | None = None


class AppointmentWindowItem(BaseModel):
    start_local: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM en 24 h")
    end_local: str = Field(pattern=r"^\d{2}:\d{2}$")


class AppointmentWindowsReplace(BaseModel):
    warehouse_id: int = Field(ge=1)
    unload_team_id: int | None = Field(default=None, ge=1)
    franjas: list[AppointmentWindowItem] = Field(min_length=1, max_length=32)


class AppointmentWindowOut(BaseModel):
    id: int
    start_local: str
    end_local: str
    duration_minutes: int
    sort_order: int


class AppointmentDateWindowReplace(BaseModel):
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha local YYYY-MM-DD")
    warehouse_id: int = Field(ge=1)
    unload_team_id: int | None = Field(default=None, ge=1)
    franjas: list[AppointmentWindowItem] = Field(min_length=1, max_length=32)


class AppointmentDateWindowBulkReplace(BaseModel):
    warehouse_id: int = Field(ge=1)
    unload_team_id: int | None = Field(default=None, ge=1)
    start_day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha inicial YYYY-MM-DD")
    end_day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="Fecha final YYYY-MM-DD")
    iso_weekdays: list[int] = Field(min_length=1, max_length=7, description="Dias ISO a aplicar: 1..7")
    franjas: list[AppointmentWindowItem] = Field(min_length=1, max_length=32)


class AnalyticsSummaryOut(BaseModel):
    totales_por_estado: dict[str, int]
    totales_por_estado_hoy: dict[str, int]
    citas_ultimos_30_dias: list[dict[str, Any]]
    citas_por_dia_semana: list[dict[str, Any]]
    top_proveedores: list[dict[str, Any]]
    total_citas: int


class ProfileMeOut(BaseModel):
    document_id: str
    role_name: str
    full_name: str
    email: EmailStr
    photo_url: str | None = None
    unload_teams: int | None = None


class ProfileMeUpdate(BaseModel):
    full_name: str = Field(min_length=3, max_length=160)
    email: EmailStr
    unload_teams: int | None = Field(default=None, ge=1, le=20)


class ProfilePasswordChange(BaseModel):
    current_password: str = Field(min_length=6, max_length=100)
    new_password: str = Field(min_length=6, max_length=100)
