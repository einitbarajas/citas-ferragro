from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    document_id: str
    email: EmailStr
    full_name: str
    password: str
    role_name: str = Field(default="Logistica", min_length=3, max_length=40)
    digito_verificacion: str | None = None
    nombre_persona_responsable: str | None = None
    documento_persona_responsable: str | None = None

    @field_validator("document_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("El identificador no puede estar vacío")
        if not clean.isdigit():
            raise ValueError("El documento debe contener solo números")
        return clean

    @field_validator("role_name")
    @classmethod
    def normalize_role_name(cls, value: str) -> str:
        clean = value.strip()
        if clean.lower() in {"proveedor", "proveedores"}:
            return "Proveedor"
        if clean.lower() in {"logistica", "logística"}:
            return "Logistica"
        if clean.lower() == "admin":
            return "Admin"
        return clean


class UserOut(BaseModel):
    document_id: str
    email: EmailStr
    full_name: str
    role_name: str

    model_config = ConfigDict(from_attributes=True)
