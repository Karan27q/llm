from flask import Blueprint, jsonify, request
from app.views.auth import login_required
from app.services.audit_service import AuditService

audit_bp = Blueprint("audit", __name__)
audit_service = AuditService()

@audit_bp.route("/api/audit/logs")
@login_required
def get_audit_logs():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    logs = audit_service.get_logs(limit=limit, offset=offset)
    
    logs_list = []
    for log in logs:
        logs_list.append({
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "ip_address": log.ip_address,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None
        })
    return jsonify({"logs": logs_list})
