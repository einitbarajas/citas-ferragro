from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Provider(Base):
    __tablename__ = "Proveedores"
    __table_args__ = (
        CheckConstraint(
            "\"DocumentoPersonaResponsable\" ~ '^[0-9]{7,10}$'",
            name="ChkProveedoresDocumentoPersonaResponsable",
        ),
        CheckConstraint(
            "\"DigitoVerificacion\" ~ '^[0-9]{1}$'",
            name="ChkProveedoresDigitoVerificacion",
        ),
    )

    nit: Mapped[int] = mapped_column("IdNit", Numeric(10, 0), primary_key=True, index=True)
    verification_digit: Mapped[str] = mapped_column("DigitoVerificacion", String(1), nullable=False)
    company_name: Mapped[str] = mapped_column("NombreEmpresa", String(160), nullable=False)
    company_email: Mapped[str] = mapped_column("CorreoEmpresa", String(255), unique=True, nullable=False)
    credential_id: Mapped[int] = mapped_column(
        "IdCredencial", ForeignKey("Credenciales.IdCredencial"), unique=True, nullable=False, index=True
    )
    contact_name: Mapped[str] = mapped_column("NombrePersonaResponsable", String(160), nullable=False)
    contact_document: Mapped[str] = mapped_column("DocumentoPersonaResponsable", String(30), nullable=False)

    credential = relationship("Credential", back_populates="provider", uselist=False)
    appointments = relationship("Appointment", back_populates="provider")

    @property
    def full_name(self) -> str:
        return self.company_name
