from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole:
    """Nombres de rol en BD (tabla Rol)."""

    admin = "Admin"
    logistica = "Logistica"
    proveedor = "Proveedor"


class User(Base):
    __tablename__ = "Usuarios"
    __table_args__ = (
        CheckConstraint(
            "\"IdDocumento\" ~ '^[0-9]{7,10}$'",
            name="ChkUsuariosIdDocumentoPorRol",
        ),
    )

    document_id: Mapped[str] = mapped_column("IdDocumento", String(30), primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column("NombreCompleto", String(120), nullable=False)
    credential_id: Mapped[int] = mapped_column(
        "IdCredencial", ForeignKey("Credenciales.IdCredencial"), unique=True, nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column("IdRol", ForeignKey("Rol.Id"), nullable=False, index=True)

    credential = relationship("Credential", back_populates="user", uselist=False)
    role = relationship("Role", back_populates="users")
