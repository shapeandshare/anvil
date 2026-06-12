"""SQLAlchemy models for the model registry."""

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from microgpt.db.base import Base, TimestampMixin


class RegisteredModel(Base, TimestampMixin):
    __tablename__ = "registered_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    versions: Mapped[list["ModelVersion"]] = relationship(
        "ModelVersion", back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("registered_models.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    experiment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experiments.id"), nullable=False
    )
    dataset_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    final_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    hyperparameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    model: Mapped["RegisteredModel"] = relationship(
        "RegisteredModel", back_populates="versions"
    )
