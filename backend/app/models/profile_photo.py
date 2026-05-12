from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProfilePhoto(Base):
    __tablename__ = "PerfilFoto"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    credential_id: Mapped[int] = mapped_column(
        "IdCredencial",
        ForeignKey("Credenciales.IdCredencial"),
        unique=True,
        nullable=False,
        index=True,
    )
    photo_url: Mapped[str | None] = mapped_column("FotoUrl", String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        "ActualizadoEn",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    credential = relationship("Credential", back_populates="profile_photo")
