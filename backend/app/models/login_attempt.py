from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LoginAttempt(Base):
    __tablename__ = "IntentosLogin"

    credential_id: Mapped[int] = mapped_column(
        "IdCredencial", ForeignKey("Credenciales.IdCredencial", ondelete="CASCADE"), primary_key=True
    )
    consecutive_failures: Mapped[int] = mapped_column("FallosConsecutivos", Integer, nullable=False, default=0)
    blocked_until: Mapped[datetime | None] = mapped_column("BloqueadoHasta", DateTime(timezone=True), nullable=True)

    credential = relationship("Credential", back_populates="login_attempt")

