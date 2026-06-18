from app.repositories.audit_repository import AuditRepository

class AuditService:
    def __init__(self):
        self.repository = AuditRepository()

    def log_event(self, user_id: int, action: str, ip_address: str, details: str):
        return self.repository.log_event(user_id, action, ip_address, details)

    def get_logs(self, limit: int = 100, offset: int = 0):
        return self.repository.get_logs(limit, offset)

    def get_rate_limit_violations(self, limit: int = 100):
        return self.repository.get_rate_limit_violations(limit)
