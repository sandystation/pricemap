from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ValuationRequest(Base):
    __tablename__ = "valuation_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"))
    input_json: Mapped[dict] = mapped_column(JSONB)
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    model_version: Mapped[str | None] = mapped_column(String(50))
    confidence_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"))
    version: Mapped[str] = mapped_column(String(50))
    trained_at: Mapped[datetime] = mapped_column(DateTime)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB)  # MAE, RMSE, R2
    model_artifact_path: Mapped[str] = mapped_column(String(500))
    feature_importance_json: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=False)
    sample_count: Mapped[int | None] = mapped_column(Integer)
