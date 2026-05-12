from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RefreshSession(Base):
    __tablename__ = "SesionesRefresh"

    id: Mapped[int] = mapped_column("Id", primary_key=True, autoincrement=True)
    credential_id: Mapped[int] = mapped_column(
        "IdCredencial", ForeignKey("Credenciales.IdCredencial", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[UUID] = mapped_column("Jti", PG_UUID(as_uuid=True), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column("CreadoEn", DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column("ExpiraEn", DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column("RevocadoEn", DateTime(timezone=True), nullable=True)

    credential = relationship("Credential", back_populates="refresh_sessions")

