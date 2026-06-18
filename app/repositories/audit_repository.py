from app.repositories.base_repository import BaseRepository
from app.models.audit_log import AuditLog

class AuditRepository(BaseRepository):
    def log_event(self, user_id: int, action: str, ip_address: str, details: str) -> AuditLog:
        log = AuditLog(user_id=user_id, action=action, ip_address=ip_address, details=details)
        self.add(log)
        self.commit()
        return log

    def get_logs(self, limit: int = 100, offset: int = 0):
        return self.session.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    def get_rate_limit_violations(self, limit: int = 100):
        return self.session.query(AuditLog).filter(
            AuditLog.action == "RATE_LIMIT_EXCEEDED"
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()
