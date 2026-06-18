import datetime
from sqlalchemy import Column, DateTime
from app.database import Base

class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True, default=None)

    def soft_delete(self):
        self.deleted_at = datetime.datetime.utcnow()

    def restore(self):
        self.deleted_at = None
