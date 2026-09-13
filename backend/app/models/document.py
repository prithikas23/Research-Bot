from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=True)
    page_count = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="not_refreshed")
    created_at = Column(DateTime, server_default=func.now(), default=datetime.utcnow)

    # Relationship to message sources
    sources = relationship("MessageSource", back_populates="document", cascade="all, delete-orphan")
