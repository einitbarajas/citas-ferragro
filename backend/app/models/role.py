from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "Rol"

    id: Mapped[int] = mapped_column("Id", primary_key=True, index=True)
    name: Mapped[str] = mapped_column("Nombre", String(40), unique=True, nullable=False)

    users = relationship("User", back_populates="role")
